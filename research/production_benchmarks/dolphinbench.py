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
import time
import uuid

from atmem import Memory
from atmem.benchmark.contracts import validate_dolphin_split
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


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _require_completed_interaction(result) -> None:
    final = result.messages[-1] if result.messages else {}
    attempts = list(getattr(result, "attempts", None) or [])
    driver_completed = bool(attempts and attempts[-1].get("driver_ok") is True)
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
    split = validate_dolphin_split(split)
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
    if split.get("split_sha256") != PINNED_SPLIT_SHA256:
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
            )[:6]
        }
        if selected != derived:
            raise RuntimeError(
                f"DolphinBench development IDs do not match the frozen selection rule: {persona}"
            )
    if development | held_out != available_all:
        raise RuntimeError("DolphinBench split contains unknown test identifiers")
    return {
        "format": "atmem-dolphinbench-official-preflight-v1",
        "source_commit": head,
        "development_count": len(development),
        "held_out_count": len(held_out),
        "development_ids": sorted(development),
        "content_retained": False,
    }


def _frozen_development_split(checkout: str | Path) -> tuple[dict, dict[str, set[str]]]:
    split_path = (
        Path(__file__).resolve().parents[2]
        / "benchmarks/retrieval_quality/protocols/dolphinbench-task-split-v1.json"
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
    """Run only the frozen 18 tasks through the official execute/grade path.

    This produces development evidence, never an official 600-task package.
    The official release loader, interaction executor, and grader remain the
    authorities; this function only selects the precommitted task IDs before
    `_execute` can create an inflight marker.
    """
    from harness.durable_json import save_json

    verification, selected = _frozen_development_split(checkout)
    if set(runner.release) != set(PERSONAS):
        raise RuntimeError("official DolphinBench release must contain three personas")
    if not isinstance(runner.adapter, AtMemDolphinAdapter):
        raise RuntimeError("development runner requires the AtMem DolphinBench adapter")
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
        if found != selected[persona] or len(specs) != 6:
            raise RuntimeError(f"official release is missing frozen development tasks: {persona}")
        chosen_specs[persona] = specs
    runner._saved_cost("ingestion")

    checks = 0
    for persona in PERSONAS:
        for spec in chosen_specs[persona]:
            evidence = runner._execute("tests", persona, spec)
            item_id = str(spec["id"]).zfill(3)
            grade_path = runner._path("grades", persona, item_id)
            if not grade_path.exists():
                save_json(grade_path, runner._grade(spec, evidence))
            grade = json.loads(grade_path.read_text(encoding="utf-8"))
            checks += len(grade["checks"])
    test_cost = runner._collect_cost("tests")
    result = {
        "format": "atmem-dolphinbench-development-evaluation-v1",
        "claim": "development-18-of-600-not-an-official-score",
        "source_commit": verification["source_commit"],
        "split_sha256": PINNED_SPLIT_SHA256,
        "development_ids": verification["development_ids"],
        "tests": 18,
        "checks": checks,
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
    def __init__(self, options: dict, work_dir: Path) -> None:
        self.options = dict(options)
        self.work_dir = Path(work_dir).resolve()
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
        memory = Memory(self._path(request.persona), retain_query_text=False, auto_vectors=False)
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
                context = self._recall(memory, request.persona, request.dated_message)
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
                    "atmem": {
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
        finally:
            memory.close()

    def freeze(self, persona: str) -> dict:
        path = self._path(persona)
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
        if any(
            row.get("state") != "completed" or row.get("cost_usd") is None
            for row in rows
        ):
            raise RuntimeError(f"missing durable cost for DolphinBench {phase}")
        return float(sum(float(row["cost_usd"]) for row in rows))

    def _path(self, persona: str) -> Path:
        return self.root / f"{persona}.db"

    def _scope(self, persona: str) -> AuthorityScope:
        return AuthorityScope(
            subject_id=f"dolphin:{persona}",
            agent_id="dolphin-agent",
            workspace_id=f"dolphin:{persona}",
        )

    def _ingest(self, memory: Memory, request) -> dict:
        text = request.dated_message
        episode_request = EpisodeIngestRequest(
            episode_id=f"dolphin-{request.persona}-{request.interaction_id}",
            idempotency_key=f"dolphin-{request.persona}-{request.interaction_id}",
            scope=self._scope(request.persona),
            parts=(EpisodePart(
                part_id="dated-message", ordinal=0, kind="text",
                source_type="user_message", content=text,
                content_sha256="sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            ),),
            binding_method="host_asserted",
            binding_assurance="host_asserted",
            session_id=request.interaction_id,
            retain_body=True,
        )
        budget = RetrievalBudget(proposals=256, source_bytes=max(262_144, len(text.encode())))
        formed = memory.form_episode(episode_request, budget=budget)
        for _ in range(31):
            if not formed["receipt"].get("next_positions"):
                break
            formed = memory.form_episode(episode_request, budget=budget)
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

    def _recall(self, memory: Memory, persona: str, query: str) -> str:
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
        return package.context

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
    """Create the 3% adapter only after re-deriving its official frozen split."""
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
