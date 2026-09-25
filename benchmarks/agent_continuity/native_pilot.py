"""One public pilot task using upstream text orchestration, no injected faults.

Not a four-arm continuity benchmark. Full task labels stay evaluator-side and are
never passed to LLMAgent; user scenario goes only to the simulator. Dry-run is the
default. Explicit --execute uses the one shared USD20 authorization ledger.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import uuid

from .live_transport import LoggedTransport, MODEL, PRICE, save_json
from .manifest import digest, file_digest
from .retail import dependency_versions, pilot_task, verify_checkout
from .spend import BudgetStop, SpendLedger

HERE = Path(__file__).resolve().parent
AUTH = HERE / "pilot-authorization.json"
# Shared across every role/trial under this authorization; not caller selectable.
LEDGER_ROOT = HERE / "results" / "pilot-usd20-20260925"
LEDGER_CONFIG = dict(authorization_id="continuity-pilot-usd20-20260925",
                    protocol_sha256=digest({"authorization": json.loads(AUTH.read_text()), "price": PRICE}),
                    cap_micro_usd=20_000_000)


def initialize_budget():
    # Exclusive directory prevents a missing/deleted DB being silently recreated.
    LEDGER_ROOT.mkdir(mode=0o700)
    SpendLedger.create(LEDGER_ROOT / "spend.db", **LEDGER_CONFIG)
    save_json(LEDGER_ROOT / "authorization.json", {**LEDGER_CONFIG, "authorization": json.loads(AUTH.read_text()), "price": PRICE})


def run(root: Path, output: Path, task_id: str, *, execute=False, env_file: Path | None = None):
    # Capture credentials before importing upstream; never accept an implicitly
    # loaded upstream dotenv credential. Dry runs do not read any key file.
    key = None
    if execute:
        from dotenv import dotenv_values
        key = os.environ.get("OPENAI_API_KEY")
        if env_file is not None:
            key = dotenv_values(env_file, interpolate=False).get("OPENAI_API_KEY") or key
    task_data = pilot_task(root, task_id)  # Explicit split check before exposing task.
    stamp = verify_checkout(root)
    dependencies = dependency_versions(root)
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED="1", LITELLM_LOCAL_MODEL_COST_MAP="True",
                      TAU2_DATA_DIR=str(root.resolve() / "data"), LANGSMITH_TRACING="false",
                      LANGCHAIN_TRACING_V2="false")
    sys.path.insert(0, str(root.resolve() / "src"))
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory(prefix="continuity-native-pycache-") as cache:
        sys.pycache_prefix = cache
        from loguru import logger
        logger.remove()
        from tau2.agent.llm_agent import LLMAgent
        from tau2.user.user_simulator import UserSimulator
        from tau2.domains.retail.environment import get_environment
        from tau2.data_model.tasks import Task
        from tau2.orchestrator.orchestrator import Orchestrator
        from tau2.evaluator.evaluator_env import EnvironmentEvaluator
        from tau2.evaluator import evaluator_nl_assertions as nl
        from tau2.utils import llm_utils
        from litellm import ModelResponse

    environment = get_environment()
    task = Task.model_validate(task_data)
    if set(str(v.value) for v in task.evaluation_criteria.reward_basis) != {"DB", "NL_ASSERTION"}:
        raise ValueError("unsupported reward basis; fail before spend")
    if nl.DEFAULT_LLM_NL_ASSERTIONS != MODEL:
        raise ValueError("upstream grader model differs; fail before spend")
    args = {"temperature": 0, "num_retries": 0, "max_tokens": 2048}
    agent = LLMAgent(tools=environment.get_tools(), domain_policy=environment.get_policy(), llm=MODEL, llm_args=args)
    user = UserSimulator(llm=MODEL, instructions=str(task.user_scenario), tools=None, llm_args=args)
    if environment.user_tools is not None or task.user_tools:
        raise ValueError("this first pilot only supports tool-free retail simulator")
    manifest = {"evidence_level": "engineering-native-pilot", "production_claims_allowed": False,
                "task_id": task_id, "arm": "native-no-fault", "fault": None,
                "trial_id": "native-" + str(uuid.uuid4()), "source": stamp,
                "authorization": json.loads(AUTH.read_text()), "price": PRICE,
                "seed": 20260925, "model_args": args, "max_steps": 58, "max_errors": 5,
                "trial_timeout_seconds": 600, "request_timeout_seconds": 90,
                "python": platform.python_version(), "platform": platform.platform(),
                "dependencies": dependencies, "agent_prompt": agent.system_prompt,
                "simulator_prompt": user.system_prompt,
                "harness": {p.name: file_digest(p) for p in HERE.glob("*.py")},
                "limitation": "One development task, native orchestration with logged direct transport; not restart recovery, four-arm comparison or official upstream submission."}
    manifest["protocol_sha256"] = digest(manifest)
    save_json(output / "manifest.json", manifest)
    if not execute:
        save_json(output / "status.json", {"disposition": "dry_run", "paid_calls": 0})
        return {"disposition": "dry_run", "paid_calls": 0}

    ledger = SpendLedger(LEDGER_ROOT / "spend.db", **LEDGER_CONFIG)
    # Parse ONLY explicit key, no shell sourcing or interpolation, never print it.
    if not key:
        save_json(output / "status.json", {"disposition": "missing_credential", "paid_calls": 0})
        return {"disposition": "missing_credential", "paid_calls": 0}
    transport = LoggedTransport(ledger, output, key, manifest["trial_id"])
    def completion(**kwargs):
        return ModelResponse(**transport.complete(**kwargs))
    llm_utils.completion = completion
    # Force grader through the SAME reservation boundary and model settings.
    nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = args
    for participant, role in ((agent, "agent"), (user, "simulator")):
        original = participant.generate_next_message
        def generate(*values, _original=original, _role=role, **options):
            transport.role = _role
            try:
                return _original(*values, **options)
            finally:
                transport.role = None
        participant.generate_next_message = generate
    class LoggedOrchestrator(Orchestrator):
        def step(self):
            super().step()
            save_json(output / f"step-{self.step_count:04}.json", {
                "messages": [m.model_dump(mode="json") for m in self.get_messages()],
                "agent_state": self.agent_state.model_dump(mode="json"),
                "simulator_state": self.user_state.model_dump(mode="json")})
    orchestrator = LoggedOrchestrator(domain="retail", agent=agent, user=user,
        environment=environment, task=task, max_steps=58, max_errors=5,
        seed=20260925, simulation_id=manifest["trial_id"], timeout=600)
    started = time.monotonic()
    result = {"disposition": "infrastructure_failure", "production_claims_allowed": False}
    try:
        simulation = orchestrator.run()
        save_json(output / "trajectory.json", simulation.model_dump(mode="json"))
        if transport.halted or ledger.snapshot()["summary"]["unknown_attempts"]:
            raise RuntimeError("transport/accounting halted before grading")
        db_score = EnvironmentEvaluator.calculate_reward(get_environment, task, simulation.messages)
        transport.role = "grader"
        nl_score = nl.NLAssertionsEvaluator.calculate_reward(task, simulation.messages)
        expected = task.evaluation_criteria.nl_assertions or []
        checked = [check.nl_assertion for check in nl_score.nl_assertions or []]
        if sorted(checked) != sorted(expected):
            raise ValueError("grader did not cover exact assertion set")
        normal = simulation.termination_reason.value in {"agent_stop", "user_stop"}
        result.update(disposition="completed" if normal else "premature_termination",
            termination_reason=simulation.termination_reason.value,
            db_score=db_score.model_dump(mode="json"), nl_score=nl_score.model_dump(mode="json"),
            local_task_reward=db_score.reward * nl_score.reward if normal else 0,
            messages=len(simulation.messages))
    except BaseException as error:
        result.update(disposition="budget_stopped" if transport.halted in {"budget_stopped", "call_limit"} or isinstance(error, BudgetStop) else "infrastructure_failure",
                      error_type=type(error).__name__)
        # Partial native trajectory retained; no exception/header strings exported.
        save_json(output / "partial-trajectory.json", [m.model_dump(mode="json") for m in orchestrator.get_messages()])
    finally:
        result.update(elapsed_ms=(time.monotonic()-started)*1000, dispatched_attempts=transport.calls,
                      transport_halted=transport.halted)
        try:
            if verify_checkout(root) != stamp:
                result["disposition"] = "source_changed"
        except Exception as error:
            result.update(disposition="finalization_failure", finalization_error_type=type(error).__name__)
        try:
            ledger.export(output / "accounting.json")
        except Exception as error:
            result.update(disposition="finalization_failure", accounting_error_type=type(error).__name__)
        save_json(output / "status.json", result)
        save_json(output / "SHA256SUMS.json", {p.name: file_digest(p) for p in output.iterdir() if p.is_file()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--task-id", default="0")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--initialize-budget", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.initialize_budget:
        initialize_budget()
        print("Initialized shared USD20 ledger; no API calls.")
        return
    if args.upstream is None or args.output is None:
        parser.error("--upstream and --output required")
    result = run(args.upstream, args.output, args.task_id, execute=args.execute, env_file=args.env_file)
    print(json.dumps(result, indent=2))
    if result["disposition"] not in {"completed", "dry_run"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
