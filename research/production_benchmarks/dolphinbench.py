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
from importlib import import_module
import inspect
import json
from pathlib import Path
import time
import uuid

from atmem import Memory
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


def prepare_persona_households(work_dir: str | Path, *, backend: str = "file") -> list[dict]:
    """Explicit no-model preflight; constructors remain side-effect free."""
    root = Path(work_dir).expanduser().resolve() / "atmem-personas"
    root.mkdir(parents=True, exist_ok=True)
    return [
        HouseholdApplication.initialize(root / f"{persona}.db", encrypted=True, backend=backend)
        for persona in PERSONAS
    ]


class AtMemDolphinAdapter:
    def __init__(self, options: dict, work_dir: Path) -> None:
        self.options = dict(options)
        self.work_dir = Path(work_dir).resolve()
        self.root = self.work_dir / "atmem-personas"
        self.driver_target = str(self.options.get("agent_driver") or "")
        if not self.driver_target:
            raise ValueError("options.agent_driver is required")
        self.driver = _target(self.driver_target)
        self.model = str(self.options.get("model") or "")
        if not self.model:
            raise ValueError("options.model is required")
        self.cost_cap_usd = float(self.options.get("cost_cap_usd") or 0.0)
        self.max_interaction_cost_usd = float(
            self.options.get("max_interaction_cost_usd") or 0.0
        )
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
        self._reserve_interaction_cost(
            request.phase, request.persona, request.interaction_id
        )
        memory = Memory(self._path(request.persona), retain_query_text=False, auto_vectors=False)
        try:
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
            if request.phase == "ingestion":
                self._ingest(memory, request)
            elif request.phase != "tests":
                raise ValueError(f"unsupported DolphinBench phase: {request.phase}")
            self._record_cost(
                request.phase, request.persona, request.interaction_id, result
            )
            result.duration_ms = result.duration_ms or (time.monotonic() - started) * 1000
            result.settings = {
                **dict(result.settings),
                "atmem": {
                    "scope": request.persona,
                    "context_sha256": "sha256:" + hashlib.sha256(context.encode()).hexdigest(),
                    "context_injected": bool(context),
                    "writes_allowed": request.phase == "ingestion",
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

    def _ingest(self, memory: Memory, request) -> None:
        text = request.dated_message
        memory.form_episode(EpisodeIngestRequest(
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
        ))

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
