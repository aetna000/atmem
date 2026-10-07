"""Official DolphinBench adapter with AtMem as the memory authority.

The adapter is intentionally an orchestration shim: history enters the normal
episode API, test retrieval uses the normal Context Package V2 API, and the
configured agent driver retains responsibility for model calls and app tools.
No dataset labels, gold answers, graders, or benchmark-specific extraction are
available to AtMem.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
from importlib import import_module
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from atmem import Memory
from atmem.benchmark.contracts import (
    DOLPHIN_DEVELOPMENT_PROFILE_FORMAT,
    validate_dolphin_development_selection,
)
from atmem.contracts import (
    AuthorityScope,
    ContextRequestV2,
    EpisodeIngestRequest,
    EpisodePart,
    RecallRequest,
    RetrievalBudget,
)
from atmem.service.household import HouseholdApplication
from research.production_benchmarks.cost_ledger import DurableCostLedger


PERSONAS = ("alex", "morgan", "riley")
PINNED_COMMIT = "81cb6f8405b40a9e76089cef650806a80af06ea2"
PINNED_SPLIT_SHA256 = "882a9e1cbd70862fa35172b806c0a0a48b39d0056cff89e68d870ca58a48fe34"
PINNED_DEVELOPMENT_PROFILE_SHA256 = "60c681f8e7ce0796ec0209294c885abe7dc0fe5a594226aa1035c401535658de"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bounded_text_parts(text: str, *, limit: int = 1_800) -> tuple[str, ...]:
    """Split source text below the memory-unit fact ceiling without data loss."""
    if limit < 1:
        raise ValueError("text part limit must be positive")
    parts: list[str] = []
    position = 0
    while position < len(text):
        end = min(len(text), position + limit)
        if end < len(text):
            boundary = text.rfind(" ", position, end)
            if boundary > position:
                end = boundary + 1
        parts.append(text[position:end])
        position = end
    return tuple(parts) or ("",)


def _target(value: str):
    module, separator, name = value.partition(":")
    if not separator or not module or not name:
        raise ValueError("agent_driver must be a module:callable import path")
    return getattr(import_module(module), name)


def _driver_artifact_sha256(driver) -> str:
    path_value = inspect.getsourcefile(driver) or inspect.getfile(driver)
    path = Path(path_value).resolve()
    if not path.is_file():
        raise RuntimeError("agent_driver must come from a hashable source file")
    return "sha256:" + _sha256(path)


def build_pre_action_gate_receipt(request, package) -> dict:
    """Return the product's fail-closed decision before any model/tool call."""
    decision = package.sufficiency
    missing = [str(item) for item in decision.missing_slots]
    gate_open = decision.status == "sufficient" and not missing
    return {
        "format": "atmem-dolphin-pre-action-gate-v1",
        "case_id": f"{request.persona}:{str(request.interaction_id).zfill(3)}",
        "decision_id": decision.decision_id,
        "outcome": "gate_open" if gate_open else "blocked_missing_requirement",
        "required_requirement_ids": list(decision.required_slots),
        "covered_requirement_ids": list(decision.covered_slots),
        "missing_requirement_ids": missing or (
            [] if gate_open else ["atmem:sufficiency:not_sufficient"]
        ),
        "actual_reason": "complete_evidence" if gate_open else "missing_requirement",
        "model_invoked": False,
        "tool_calls": 0,
        "error_type": None,
    }


def _require_completed_interaction(result) -> None:
    final = result.messages[-1] if result.messages else {}
    attempts = list(getattr(result, "attempts", None) or [])
    driver_completed = bool(attempts and (
        attempts[-1].get("driver_ok") is True
        or attempts[-1].get("gate_blocked") is True
    ))
    legacy_completed = str(final.get("finish_reason") or "") == "stop"
    if (final.get("role") != "assistant"
            or not str(final.get("content") or "").strip()
            or not (driver_completed or legacy_completed)):
        raise RuntimeError("DolphinBench agent did not produce a complete final answer")


def require_completed_provider_response(response: object, *, role: str) -> dict:
    """Reject incomplete paid model output before it can affect a score."""
    if not isinstance(response, dict):
        raise RuntimeError(f"DolphinBench {role} returned a non-object response")
    choices = response.get("choices") or []
    if len(choices) != 1 or not isinstance(choices[0], dict):
        raise RuntimeError(f"DolphinBench {role} must return exactly one choice")
    choice = choices[0]
    message = choice.get("message") or {}
    usage = response.get("usage") or {}
    if (choice.get("finish_reason") != "stop"
            or not str(message.get("content") or "").strip()
            or int(usage.get("prompt_tokens") or 0) <= 0
            or int(usage.get("completion_tokens") or 0) <= 0):
        raise RuntimeError(f"DolphinBench {role} did not produce a complete final answer")
    return response


def verify_official_checkout(checkout: str | Path, split: dict) -> dict:
    """Verify the official source pin and re-derive the frozen test partition."""
    split = validate_dolphin_development_selection(split)
    root = Path(checkout).expanduser().resolve()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if head != PINNED_COMMIT:
        raise RuntimeError(
            f"DolphinBench checkout must be {PINNED_COMMIT}; found {head}"
        )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("DolphinBench checkout has unreviewed working-tree changes")
    if split.get("source_commit") != PINNED_COMMIT:
        raise RuntimeError("DolphinBench split source commit differs from the checkout")
    expected_digest = (
        PINNED_DEVELOPMENT_PROFILE_SHA256
        if split.get("format") == DOLPHIN_DEVELOPMENT_PROFILE_FORMAT
        else PINNED_SPLIT_SHA256
    )
    actual_digest = split.get(
        "profile_sha256" if split.get("format") == DOLPHIN_DEVELOPMENT_PROFILE_FORMAT
        else "split_sha256"
    )
    if actual_digest != expected_digest:
        raise RuntimeError("DolphinBench development split differs from the frozen pin")
    salt = str(split.get("salt") or "")
    if not salt:
        raise RuntimeError("DolphinBench development split is missing its salt")
    development = {str(value) for value in split.get("development_ids", [])}
    held_out = {str(value) for value in split.get("confirmation_ids", [])}
    available_all: set[str] = set()
    for persona in PERSONAS:
        available = {
            f"{persona}:{path.stem}"
            for path in (root / "tests" / persona).glob("[0-9][0-9][0-9].yaml")
        }
        available_all.update(available)
        selected = {value for value in development if value.startswith(f"{persona}:")}
        confirmation = {value for value in held_out if value.startswith(f"{persona}:")}
        counts = dict(split.get("personas", {}).get(persona) or {})
        if (
            len(selected) != int(counts.get("development", -1))
            or len(confirmation) != int(counts.get("confirmation", -1))
            or selected & confirmation
            or selected | confirmation != available
        ):
            raise RuntimeError(f"DolphinBench split does not partition {persona}")
        derived = {
            f"{persona}:{value}"
            for value in sorted(
                (path.stem for path in (root / "tests" / persona).glob("[0-9][0-9][0-9].yaml")),
                key=lambda value: (
                    hashlib.sha256(
                        salt.encode() + b"\0" + f"{persona}:{value}".encode()
                    ).hexdigest(),
                    value,
                ),
            )[: int(counts["development"])]
        }
        historical = set(split.get("historical_development_ids") or ())
        if split.get("format") == DOLPHIN_DEVELOPMENT_PROFILE_FORMAT:
            historical_persona = {value for value in historical if value.startswith(f"{persona}:")}
            remainder = sorted(
                available - historical_persona,
                key=lambda value: (
                    hashlib.sha256(salt.encode() + b"\0" + value.encode()).hexdigest(),
                    value,
                ),
            )[:4]
            derived = historical_persona | set(remainder)
        if selected != derived:
            raise RuntimeError(
                f"DolphinBench development IDs do not match the frozen selection rule: {persona}"
            )
    if development | held_out != available_all:
        raise RuntimeError("DolphinBench split contains unknown test identifiers")
    return {
        "format": "atmem-dolphinbench-official-preflight-v1",
        "source_commit": head,
        "development_profile_sha256": actual_digest,
        "development_count": len(development),
        "held_out_count": len(held_out),
        "development_ids": sorted(development),
        "content_retained": False,
    }


def _frozen_development_split(checkout: str | Path) -> tuple[dict, dict[str, set[str]]]:
    split_path = (
        Path(__file__).resolve().parents[2]
        / "benchmarks/retrieval_quality/protocols/dolphinbench-development-5pct-v1.json"
    )
    split = json.loads(split_path.read_text(encoding="utf-8"))
    verification = verify_official_checkout(checkout, split)
    selected = {
        persona: {
            value.partition(":")[2]
            for value in split["development_ids"]
            if value.startswith(f"{persona}:")
        }
        for persona in PERSONAS
    }
    return verification, selected


def evaluate_development(runner, checkout: str | Path) -> dict:
    """Run only the frozen 30 tasks through the official execute/grade path.

    This produces development evidence, never an official 600-task package.
    The official release loader, interaction executor, and grader remain the
    authorities; this function only selects the precommitted task IDs before
    `_execute` can create an inflight marker.
    """
    from harness.durable_json import save_json

    verification, selected = _frozen_development_split(checkout)
    if set(runner.release) != set(PERSONAS):
        raise RuntimeError("official DolphinBench release must contain three personas")
    if not all(callable(getattr(runner.adapter, name, None)) for name in (
        "identity", "verify_checkpoint", "run_interaction", "total_cost_usd"
    )):
        raise RuntimeError("development runner requires a benchmark memory adapter")
    if runner.adapter.allowed_test_ids != selected:
        raise RuntimeError("adapter task allowance differs from the frozen development split")

    chosen_specs: dict[str, list[dict]] = {}
    for persona in PERSONAS:
        checkpoint = runner.directory / "checkpoints" / f"{persona}.json"
        if not checkpoint.is_file():
            raise RuntimeError(f"complete official ingestion first: {persona}")
        runner.adapter.verify_checkpoint(
            persona, json.loads(checkpoint.read_text(encoding="utf-8"))
        )
        specs = [
            spec
            for spec in runner.release[persona]["tests"]
            if str(spec["id"]).zfill(3) in selected[persona]
        ]
        found = {str(spec["id"]).zfill(3) for spec in specs}
        if found != selected[persona] or len(specs) != 10:
            raise RuntimeError(f"official release is missing frozen development tasks: {persona}")
        chosen_specs[persona] = specs
    runner._saved_cost("ingestion")

    checks = 0
    checks_passed = 0
    tasks_passed = 0
    system_failures = []
    for persona in PERSONAS:
        for spec in chosen_specs[persona]:
            item_id = str(spec["id"]).zfill(3)
            grade_path = runner._path("grades", persona, item_id)
            try:
                evidence = runner._execute("tests", persona, spec)
                if not grade_path.exists():
                    save_json(grade_path, runner._grade(spec, evidence))
            except Exception as exc:
                lowered = str(exc).casefold()
                if isinstance(exc, TimeoutError) or "timeout" in lowered:
                    failure_type = "timeout"
                elif any(token in lowered for token in ("parse", "malformed", "json")):
                    failure_type = "parse_error"
                else:
                    failure_type = "provider_error"
                failure = {
                    "case_id": f"{persona}:{item_id}",
                    "outcome": "system_failure",
                    "error_type": failure_type,
                    "error_class": type(exc).__name__,
                    "error_message": str(exc),
                    "model_invoked": None,
                    "tool_calls": None,
                    "retained_in_denominator": True,
                }
                system_failures.append(failure)
                save_json(
                    runner._path("system-failures", persona, item_id), failure
                )
                assertions = list(
                    dict(dict(spec.get("grade") or {}).get("config") or {}).get("assertions")
                    or ()
                )
                save_json(grade_path, {
                    "checks": [
                        {"check": index, "passed": False, "system_failure": failure_type}
                        for index in range(max(1, len(assertions)))
                    ],
                    "settings": {"not_invoked": "system failure before/during grading"},
                })
            grade = json.loads(grade_path.read_text(encoding="utf-8"))
            checks += len(grade["checks"])
            passed = sum(row.get("passed") is True for row in grade["checks"])
            checks_passed += passed
            tasks_passed += bool(grade["checks"]) and passed == len(grade["checks"])
    test_cost = runner._collect_cost("tests")
    result = {
        "format": "atmem-dolphinbench-development-evaluation-v1",
        "claim": "development-30-of-600-not-an-official-score",
        "system": runner.adapter.identity()["format"],
        "source_commit": verification["source_commit"],
        "split_sha256": verification["development_profile_sha256"],
        "development_ids": verification["development_ids"],
        "tests": 30,
        "checks": checks,
        "checks_passed": checks_passed,
        "tasks_passed": tasks_passed,
        "system_failure_count": len(system_failures),
        "system_failures": system_failures,
        "all_failures_retained": True,
        "test_cost_usd": test_cost,
        "content_retained": False,
    }
    save_json(runner.directory / "development-evaluation.json", result)
    return result


def prepare_persona_households(
    work_dir: str | Path,
    *,
    backend: str = "file",
    household_root: str | Path | None = None,
) -> list[dict]:
    """Explicit no-model preflight; constructors remain side-effect free."""
    root = (
        Path(household_root).expanduser().resolve()
        if household_root is not None
        else Path(work_dir).expanduser().resolve() / "atmem-personas"
    )
    root.mkdir(parents=True, exist_ok=True)
    return [
        HouseholdApplication.initialize(root / f"{persona}.db", encrypted=True, backend=backend)
        for persona in PERSONAS
    ]


class AtMemDolphinAdapter:
    provider_name = "atmem"
    def __init__(self, options: dict, work_dir: Path) -> None:
        self.options = dict(options)
        self.work_dir = Path(work_dir).resolve()
        self._memories: dict[str, Memory] = {}
        configured_root = self.options.get("household_root")
        self.root = (
            Path(str(configured_root)).expanduser().resolve()
            if configured_root
            else self.work_dir / "atmem-personas"
        )
        self.driver_target = str(self.options.get("agent_driver") or "")
        if not self.driver_target:
            raise ValueError("options.agent_driver is required")
        self.driver = _target(self.driver_target)
        expected_target = os.environ.get("ATMEM_DOLPHIN_DRIVER_TARGET", "").strip()
        expected_digest = os.environ.get("ATMEM_DOLPHIN_DRIVER_SHA256", "").strip()
        if expected_target or expected_digest:
            if expected_target != self.driver_target:
                raise RuntimeError("agent_driver target differs from finalization identity")
            if expected_digest != _driver_artifact_sha256(self.driver):
                raise RuntimeError("agent_driver artifact differs from finalization identity")
        self.model = str(self.options.get("model") or "")
        if not self.model:
            raise ValueError("options.model is required")
        self.authorized_history_import = bool(
            self.options.get("authorized_history_import", False)
        )
        self.cost_cap_usd = float(self.options.get("cost_cap_usd") or 0.0)
        self.max_interaction_cost_usd = float(
            self.options.get("max_interaction_cost_usd") or 0.0
        )
        allowed = self.options.get("allowed_test_ids")
        self.allowed_test_ids = (
            {
                persona: {str(value).zfill(3) for value in values}
                for persona, values in dict(allowed).items()
            }
            if allowed is not None else None
        )
        if self.allowed_test_ids is not None and set(self.allowed_test_ids) != set(PERSONAS):
            raise ValueError("allowed_test_ids must contain exactly the three personas")
        if (
            self.cost_cap_usd <= 0
            or self.max_interaction_cost_usd <= 0
            or self.max_interaction_cost_usd > self.cost_cap_usd
        ):
            raise ValueError(
                "positive cost_cap_usd and max_interaction_cost_usd <= cap are required"
            )
        for persona in PERSONAS:
            status = HouseholdApplication.status(self._path(persona))
            if status["state"] != "encrypted" or not status["encrypted_header"]:
                raise RuntimeError(
                    f"encrypted AtMem household for {persona} is not ready; "
                    "run prepare_persona_households during benchmark setup"
                )

    def identity(self) -> dict:
        from importlib.metadata import version
        return {
            "format": "atmem-dolphinbench-adapter-v1",
            "atmem_version": version("atmem"),
            "driver": self.driver_target,
            "model": self.model,
            "personas": list(PERSONAS),
            "memory_scope": "one encrypted household per persona",
            "household_root_sha256": "sha256:" + hashlib.sha256(
                str(self.root).encode("utf-8")
            ).hexdigest(),
            "test_phase_writes": False,
            "authorized_history_import": self.authorized_history_import,
            "cost_cap_usd": self.cost_cap_usd,
            "max_interaction_cost_usd": self.max_interaction_cost_usd,
        }

    def run_interaction(self, request):
        if request.persona not in PERSONAS:
            raise ValueError(f"unknown persona: {request.persona}")
        return asyncio.run(self._run(request))

    async def _run(self, request):
        from examples.mcp_connection import connect_apps
        from harness.adapter import InteractionRecord

        started = time.monotonic()
        if (
            request.phase == "tests"
            and self.allowed_test_ids is not None
            and str(request.interaction_id).zfill(3)
            not in self.allowed_test_ids[request.persona]
        ):
            raise ValueError("test interaction is outside the frozen allowed split")
        memory = self._memory(request.persona)
        try:
            formation_receipt = None
            if request.phase == "ingestion":
                context = ""
                result = InteractionRecord(
                    settings={
                        "model": "atmem-local-history-ingestion",
                    },
                    messages=[
                        {"role": "user", "content": request.dated_message},
                        {
                            "role": "assistant",
                            "content": "History recorded.",
                            "usage": {"input_tokens": 0, "output_tokens": 0},
                        },
                    ],
                    duration_ms=0.0,
                    attempts=[{
                        "driver_ok": True,
                        "error": None,
                        "cost_usd": 0.0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                    }],
                    app_calls=[],
                )
            else:
                self._reserve_interaction_cost(
                    request.phase, request.persona, request.interaction_id
                )
                package = self._recall(memory, request.persona, request.dated_message)
                context = package.context
                gate = self._pre_action_gate_receipt(request, package)
                self._write_gate_receipt(request, gate)
                if gate["outcome"] == "blocked_missing_requirement":
                    result = InteractionRecord(
                        settings={"model": self.model, "model_invoked": False},
                        messages=[
                            {"role": "user", "content": request.dated_message},
                            {
                                "role": "assistant",
                                "content": (
                                    "Blocked before model invocation: missing memory "
                                    "requirement " + gate["missing_requirement_ids"][0]
                                ),
                            },
                        ],
                        duration_ms=(time.monotonic() - started) * 1000,
                        attempts=[{
                            "cost_usd": 0.0,
                            "driver_ok": False,
                            "gate_blocked": True,
                            "error": None,
                        }],
                        app_calls=[],
                    )
                else:
                    async with connect_apps(request.apps) as apps:
                        tools = (await apps.list_tools()).tools
                        result = self.driver(
                            request=request,
                            tools=tools,
                            call_app=apps.call_tool,
                            memory_context=context,
                            model=self.model,
                            max_cost_usd=self.max_interaction_cost_usd,
                        )
                        if inspect.isawaitable(result):
                            result = await result
                    gate = {
                        **gate,
                        "model_invoked": True,
                        "tool_calls": len(result.app_calls or ()),
                        "observed_tool_names": [
                            str(call.get("tool") or call.get("name") or "")
                            for call in (result.app_calls or ())
                            if isinstance(call, dict)
                        ],
                    }
                    self._write_gate_receipt(request, gate)
            if not isinstance(result, InteractionRecord):
                raise TypeError("agent_driver must return harness.adapter.InteractionRecord")
            _require_completed_interaction(result)
            if request.phase == "ingestion":
                formation_receipt = self._ingest(memory, request)
            elif request.phase != "tests":
                raise ValueError(f"unsupported DolphinBench phase: {request.phase}")
            if request.phase != "ingestion":
                self._record_cost(
                    request.phase, request.persona, request.interaction_id, result
                )
            result.duration_ms = result.duration_ms or (time.monotonic() - started) * 1000
            result.attempts = list(result.attempts or [])
            if result.attempts:
                result.attempts[-1] = {
                    **dict(result.attempts[-1]),
                    self.provider_name: {
                        "scope": request.persona,
                        "context_sha256": "sha256:" + hashlib.sha256(
                            context.encode()
                        ).hexdigest(),
                        "context_injected": bool(context),
                        "writes_allowed": request.phase == "ingestion",
                        "formation": ({
                            "processing_complete": bool(
                                formation_receipt.get("processing_complete")
                            ),
                            "representation_complete": bool(
                                formation_receipt.get("representation_complete")
                            ),
                            "retrieval_ready": bool(
                                formation_receipt.get("retrieval_ready")
                            ),
                            "admitted": int(formation_receipt.get("admitted") or 0),
                            "withheld": int(formation_receipt.get("withheld") or 0),
                            "rejected": int(formation_receipt.get("rejected") or 0),
                        } if formation_receipt is not None else None),
                    },
                }
            return result
        except BaseException:
            self._close_memory(request.persona)
            raise

    def freeze(self, persona: str) -> dict:
        path = self._path(persona)
        self._close_memory(persona)
        status = HouseholdApplication.status(path)
        if status["state"] != "encrypted":
            raise RuntimeError(f"persona household is not encrypted: {persona}")
        memory = Memory(path, retain_query_text=False, auto_vectors=False)
        try:
            canonical = memory.memory_checkpoint(self._scope(persona))
        finally:
            memory.close()
        return {
            "format": "atmem-dolphinbench-checkpoint-v1",
            "persona": persona,
            "canonical": canonical,
            "database_sha256": _sha256(path),
            "policy_sha256": _sha256(Path(f"{path}.encryption.json")),
            "size_bytes": path.stat().st_size,
        }

    def verify_checkpoint(self, persona: str, checkpoint: dict) -> None:
        current = self.freeze(persona)
        for key in ("persona", "policy_sha256", "canonical"):
            if current[key] != checkpoint.get(key):
                raise RuntimeError(f"AtMem checkpoint changed for {persona}: {key}")

    def total_cost_usd(self, phase: str) -> float:
        ledger = self._read_ledger()
        rows = [row for row in ledger if row.get("phase") == phase]
        if phase == "ingestion" and any(
            row.get("state") != "completed" or row.get("cost_usd") is None
            for row in rows
        ):
            raise RuntimeError("missing durable cost for DolphinBench ingestion")
        # A failed paid test may leave an intentionally unreconciled
        # reservation. Count its full reserved maximum rather than dropping it
        # or retrying blindly; this is conservative financial evidence.
        return float(sum(
            float(row["cost_usd"])
            if row.get("state") == "completed" and row.get("cost_usd") is not None
            else float(row.get("reserved_max_usd") or 0)
            for row in rows
        ))

    def _path(self, persona: str) -> Path:
        return self.root / f"{persona}.db"

    def _memory(self, persona: str) -> Memory:
        memory = self._memories.get(persona)
        if memory is None:
            scope = self._scope(persona)
            authorities = ()
            if self.authorized_history_import:
                authorities = ({
                    "principal_id": f"benchmark-history-import:{persona}",
                    "subject_id": scope.subject_id,
                    "agent_id": scope.agent_id,
                    "workspace_id": scope.workspace_id,
                    "scopes": ("history_import:review", "procedure:review"),
                    "assurance": "explicit_benchmark_operator_configuration",
                },)
            memory = Memory(
                self._path(persona), retain_query_text=False, auto_vectors=False,
                review_authorities=authorities,
            )
            self._memories[persona] = memory
        return memory

    def _close_memory(self, persona: str) -> None:
        memory = self._memories.pop(persona, None)
        if memory is not None:
            memory.close()

    def _scope(self, persona: str) -> AuthorityScope:
        return AuthorityScope(
            subject_id=f"dolphin:{persona}",
            agent_id="dolphin-agent",
            workspace_id=f"dolphin:{persona}",
        )

    def _ingest(self, memory: Memory, request) -> dict:
        text = request.dated_message
        chunks = _bounded_text_parts(text)
        episode_request = EpisodeIngestRequest(
            episode_id=f"dolphin-{request.persona}-{request.interaction_id}",
            idempotency_key=f"dolphin-{request.persona}-{request.interaction_id}",
            scope=self._scope(request.persona),
            parts=tuple(
                EpisodePart(
                    part_id=f"dated-message-{index:04d}",
                    ordinal=index,
                    kind="text",
                    source_type="user_message",
                    content=chunk,
                    content_sha256="sha256:" + hashlib.sha256(
                        chunk.encode()
                    ).hexdigest(),
                )
                for index, chunk in enumerate(chunks)
            ),
            binding_method="host_asserted",
            binding_assurance="host_asserted",
            session_id=request.interaction_id,
            retain_body=True,
            source_observation_granularity=(
                "sentence" if self.authorized_history_import else "none"
            ),
        )
        budget = RetrievalBudget(
            proposals=256,
            source_bytes=max(262_144, len(text.encode())),
            wall_time_ms=120_000,
        )
        import_principal = (
            f"benchmark-history-import:{request.persona}"
            if self.authorized_history_import else None
        )
        formed = memory.form_episode(
            episode_request, budget=budget,
            history_import_principal=import_principal,
        )
        for _ in range(1_023):
            if not formed["receipt"].get("next_positions"):
                break
            formed = memory.form_episode(
                episode_request, budget=budget,
                history_import_principal=import_principal,
            )
        receipt = formed["receipt"]
        if not (
            receipt.get("processing_complete")
            and not receipt.get("next_positions")
            and int(receipt.get("source_events_observed") or 0) >= 1
        ):
            raise RuntimeError(
                "DolphinBench history processing did not complete; refusing checkpoint"
            )
        return receipt

    def _recall(self, memory: Memory, persona: str, query: str):
        scope = self._scope(persona)
        request_id = f"dolphin-{uuid.uuid4().hex}"
        candidates = memory.eligible_candidates(RecallRequest(
            request_id=request_id, scope=scope, query=query,
            limit=int(self.options.get("memory_limit", 20)),
            candidate_limit=int(self.options.get("candidate_limit", 200)),
            retrieval_strategy="core-rrf-v1",
        ))
        package = memory.prepare_context_v2(ContextRequestV2(
            context_id=f"context-{request_id}",
            candidate_set_id=candidates.candidate_set_id,
            scope=scope,
            query=query,
            budget=RetrievalBudget(
                context_bytes=int(self.options.get("context_bytes", 32_000))
            ),
        ))
        return package

    def _pre_action_gate_receipt(self, request, package) -> dict:
        """Fail closed before the model when named memory obligations are missing."""
        return build_pre_action_gate_receipt(request, package)

    def _write_gate_receipt(self, request, receipt: dict) -> None:
        target = (
            self.work_dir / "atmem-gates" / request.persona
            / f"{str(request.interaction_id).zfill(3)}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(target)

    def _ledger_path(self) -> Path:
        return self.work_dir / "atmem-cost-ledger.json"

    def _read_ledger(self) -> list[dict]:
        rows = DurableCostLedger(
            self._ledger_path(), total_cap_usd=self.cost_cap_usd
        ).rows()
        return [
            {
                **row,
                "interaction_key": row["key"],
                **dict(row.get("metadata") or {}),
            }
            for row in rows
        ]

    def _interaction_key(self, phase: str, persona: str, interaction_id: str) -> str:
        return f"{phase}:{persona}:{interaction_id}"

    def _reserve_interaction_cost(
        self, phase: str, persona: str, interaction_id: str
    ) -> None:
        key = self._interaction_key(phase, persona, interaction_id)
        ledger = DurableCostLedger(
            self._ledger_path(), total_cap_usd=self.cost_cap_usd
        )
        ledger.reserve(
            key, provider="dolphin-agent-driver",
            maximum_usd=self.max_interaction_cost_usd,
            metadata={
                "phase": phase, "persona": persona,
                "interaction_id": interaction_id,
            },
        )

    def _record_cost(
        self, phase: str, persona: str, interaction_id: str, record
    ) -> None:
        attempts = list(record.attempts or [])
        missing = [index for index, attempt in enumerate(attempts) if attempt.get("cost_usd") is None]
        if missing:
            raise RuntimeError(
                f"DolphinBench interaction has attempts without cost evidence: {missing}"
            )
        cost = record.settings.get("cost_usd")
        attempt_costs = [float(attempt["cost_usd"]) for attempt in attempts]
        if any(value < 0 for value in attempt_costs):
            raise RuntimeError("DolphinBench attempt costs cannot be negative")
        attempt_cost = sum(attempt_costs)
        if cost is None:
            if not attempts:
                raise RuntimeError(
                    "DolphinBench interaction has neither aggregate nor attempt cost evidence"
                )
            cost = attempt_cost
        elif attempts and abs(float(cost) - attempt_cost) > 1e-9:
            raise RuntimeError("DolphinBench aggregate and attempt costs disagree")
        key = self._interaction_key(phase, persona, interaction_id)
        if cost is None or float(cost) > self.max_interaction_cost_usd:
            raise RuntimeError(
                f"DolphinBench interaction {key} lacks bounded cost evidence"
            )
        DurableCostLedger(
            self._ledger_path(), total_cap_usd=self.cost_cap_usd
        ).complete(key, cost_usd=float(cost))

def create(options: dict, work_dir: Path) -> AtMemDolphinAdapter:
    return AtMemDolphinAdapter(options, work_dir)


def create_development(options: dict, work_dir: Path) -> AtMemDolphinAdapter:
    """Create the 5% adapter only after re-deriving its official frozen split."""
    configured = dict(options)
    if "allowed_test_ids" in configured:
        raise ValueError("development allowed_test_ids are supplied by the frozen split")
    checkout = configured.pop("official_checkout", None)
    if not checkout:
        raise ValueError("official_checkout is required for the development adapter")
    _, selected = _frozen_development_split(checkout)
    configured["allowed_test_ids"] = {
        persona: sorted(selected[persona])
        for persona in PERSONAS
    }
    return AtMemDolphinAdapter(configured, work_dir)


class Mem0DolphinAdapter(AtMemDolphinAdapter):
    """Matched open-source Mem0 arm using the same driver, tasks and budgets."""

    provider_name = "mem0"

    def __init__(self, options: dict, work_dir: Path) -> None:
        self.options = dict(options)
        self.work_dir = Path(work_dir).resolve()
        self._memories: dict[str, object] = {}
        self.root = Path(str(
            self.options.get("memory_root") or self.work_dir / "mem0-personas"
        )).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.driver_target = str(self.options.get("agent_driver") or "")
        if not self.driver_target:
            raise ValueError("options.agent_driver is required")
        self.driver = _target(self.driver_target)
        expected_target = os.environ.get("ATMEM_DOLPHIN_DRIVER_TARGET", "").strip()
        expected_digest = os.environ.get("ATMEM_DOLPHIN_DRIVER_SHA256", "").strip()
        if expected_target or expected_digest:
            if expected_target != self.driver_target:
                raise RuntimeError("agent_driver target differs from finalization identity")
            if expected_digest != _driver_artifact_sha256(self.driver):
                raise RuntimeError("agent_driver artifact differs from finalization identity")
        self.model = str(self.options.get("model") or "")
        checkout = Path(str(self.options.get("mem0_checkout") or "")).expanduser().resolve()
        if not self.model or not checkout.is_dir():
            raise ValueError("options.model and a pinned mem0_checkout are required")
        checkout_text = str(checkout)
        if checkout_text in sys.path:
            sys.path.remove(checkout_text)
        sys.path.insert(0, checkout_text)
        os.environ.setdefault("MEM0_TELEMETRY", "False")
        from mem0 import Memory as Mem0
        from mem0.utils.factory import EmbedderFactory
        from research.reference_parity.adapters.mem0 import HashEmbedding

        imported = Path(sys.modules[Mem0.__module__].__file__).resolve()
        if checkout not in imported.parents:
            raise RuntimeError(f"Mem0 imported from unpinned path: {imported}")
        EmbedderFactory.provider_to_class["fastembed"] = (
            "research.reference_parity.adapters.mem0.HashEmbedding"
        )
        self._Mem0 = Mem0
        self._HashEmbedding = HashEmbedding
        self.mem0_checkout = checkout
        self.cost_cap_usd = float(self.options.get("cost_cap_usd") or 0.0)
        self.max_interaction_cost_usd = float(
            self.options.get("max_interaction_cost_usd") or 0.0
        )
        allowed = self.options.get("allowed_test_ids")
        self.allowed_test_ids = {
            persona: {str(value).zfill(3) for value in values}
            for persona, values in dict(allowed or {}).items()
        }
        if set(self.allowed_test_ids) != set(PERSONAS):
            raise ValueError("allowed_test_ids must contain exactly the three personas")
        if self.cost_cap_usd <= 0 or not 0 < self.max_interaction_cost_usd <= self.cost_cap_usd:
            raise ValueError("positive bounded interaction costs are required")

    def identity(self) -> dict:
        return {
            "format": "mem0-oss-dolphinbench-adapter-v1",
            "mem0_commit": "d3891e48baa2c6e769f9cfa4003873bd6a85bc07",
            "driver": self.driver_target,
            "model": self.model,
            "personas": list(PERSONAS),
            "memory_scope": "one local Qdrant collection per persona",
            "formation": "infer=false raw dated messages",
            "embedding": "hash-bow-256-v1",
            "test_phase_writes": False,
            "cost_cap_usd": self.cost_cap_usd,
            "max_interaction_cost_usd": self.max_interaction_cost_usd,
        }

    def _persona_root(self, persona: str) -> Path:
        return self.root / persona

    def _memory(self, persona: str):
        memory = self._memories.get(persona)
        if memory is not None:
            return memory
        root = self._persona_root(persona)
        root.mkdir(parents=True, exist_ok=True)
        memory = self._Mem0.from_config({
            "vector_store": {"provider": "qdrant", "config": {
                "collection_name": f"dolphin_{persona}",
                "path": str(root / "qdrant"), "embedding_model_dims": 256,
            }},
            "llm": {"provider": "openai", "config": {
                "api_key": "unused", "model": "unused-infer-false",
            }},
            "embedder": {"provider": "fastembed", "config": {
                "embedding_dims": 256,
            }},
            "history_db_path": str(root / "history.db"),
        })
        self._memories[persona] = memory
        return memory

    def _close_memory(self, persona: str) -> None:
        memory = self._memories.pop(persona, None)
        client = getattr(getattr(memory, "vector_store", None), "client", None)
        if client is not None and hasattr(client, "close"):
            client.close()

    def _ingest(self, memory, request) -> dict:
        record_path = self._persona_root(request.persona) / "records.jsonl"
        text = request.dated_message
        memory.add(
            text, user_id=f"dolphin:{request.persona}",
            metadata={"interaction_id": str(request.interaction_id)}, infer=False,
        )
        with record_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical({
                "interaction_id": str(request.interaction_id), "text": text,
            }) + "\n")
        return {
            "processing_complete": True, "representation_complete": True,
            "retrieval_ready": True, "source_events_observed": 1,
            "admitted": 1, "withheld": 0, "rejected": 0,
        }

    def _recall(self, memory, persona: str, query: str) -> str:
        result = memory.search(
            query, filters={"user_id": f"dolphin:{persona}"},
            top_k=int(self.options.get("memory_limit", 20)), threshold=0.0,
        )
        return "\n\n".join(
            str(row.get("memory") or "")
            for row in result.get("results", [])
            if str(row.get("memory") or "").strip()
        )

    def freeze(self, persona: str) -> dict:
        self._close_memory(persona)
        records = self._persona_root(persona) / "records.jsonl"
        if not records.is_file():
            raise RuntimeError(f"Mem0 persona has no durable history: {persona}")
        lines = [line for line in records.read_text(encoding="utf-8").splitlines() if line]
        return {
            "format": "mem0-oss-dolphinbench-checkpoint-v1",
            "persona": persona,
            "records": len(lines),
            "records_sha256": _sha256(records),
        }

    def verify_checkpoint(self, persona: str, checkpoint: dict) -> None:
        if self.freeze(persona) != checkpoint:
            raise RuntimeError(f"Mem0 checkpoint changed for {persona}")


def create_mem0_development(options: dict, work_dir: Path) -> Mem0DolphinAdapter:
    configured = dict(options)
    if "allowed_test_ids" in configured:
        raise ValueError("development allowed_test_ids are supplied by the frozen split")
    checkout = configured.pop("official_checkout", None)
    if not checkout:
        raise ValueError("official_checkout is required for the development adapter")
    _, selected = _frozen_development_split(checkout)
    configured["allowed_test_ids"] = {
        persona: sorted(selected[persona]) for persona in PERSONAS
    }
    return Mem0DolphinAdapter(configured, work_dir)
