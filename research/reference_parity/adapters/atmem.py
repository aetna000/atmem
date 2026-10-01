"""Adapter that exercises the current public AtMem product boundary."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping
from unittest.mock import patch
from xml.etree import ElementTree

from atmem import Memory
from atmem.control import ControlMode, ControlPlaneManager
from atmem.context_engine import (
    DeterministicPlanner, DeterministicRetriever, FormationManager,
    SourceEpisode, SourcePart, decide_sufficiency,
)
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore

from ..contracts import CaseEvidenceResult
from ..normalizer import normalize_evidence


ATMEM_LEGACY_CONFIG = (
    "atmem-legacy-control;auto-vectors=false;atbot=offline;public-control-prepare;"
    "selection-budget-sources=2"
)
ATMEM_LEGACY_CONFIG_SHA256 = "sha256:" + hashlib.sha256(
    ATMEM_LEGACY_CONFIG.encode()
).hexdigest()
ATMEM_V3_CONFIG = (
    "atmem-context-fast;deterministic-formation-v1;planner-v1;contentless-fts;"
    "independent-pools;obligation-first;selection-budget-sources=2"
)
ATMEM_V3_CONFIG_SHA256 = "sha256:" + hashlib.sha256(ATMEM_V3_CONFIG.encode()).hexdigest()


class AtMemLegacyAdapter:
    system = "atmem-legacy-control"

    def __init__(self, *, configuration_sha256: str = ATMEM_LEGACY_CONFIG_SHA256) -> None:
        self.configuration_sha256 = configuration_sha256

    @staticmethod
    def _subject_for(scope: str) -> str:
        if scope in {"agent:a", "workspace:shared"}:
            return "local-user"
        return scope.replace(":", "-")

    @staticmethod
    def _context_items(context: str | None) -> list[str]:
        if not context:
            return []
        try:
            root = ElementTree.fromstring(context)
        except ElementTree.ParseError:
            return []
        return ["".join(item.itertext()).strip() for item in root.findall("memory")]

    def run_case(self, case: Mapping[str, Any]) -> CaseEvidenceResult:
        started = time.perf_counter()
        error: str | None = None
        selected_ranges: tuple[tuple[str, int, int], ...] = ()
        status = "not_found_within_budget"
        try:
            with tempfile.TemporaryDirectory(prefix="atmem-reference-") as directory:
                root = Path(directory)
                memory_path = root / "memory.db"
                memory = Memory(
                    memory_path,
                    auto_vectors=False,
                    allow_insecure_typed_development=True,
                )
                try:
                    for source in case["sources"]:
                        memory.remember(
                            self._subject_for(str(source["scope"])),
                            str(source["text"]),
                            interpreted_fact=str(source["text"]),
                            interpreted_fact_key=(
                                f"{case['category']}:{source['id']}"
                            ),
                        )
                finally:
                    memory.close()
                manager = ControlPlaneManager.start(
                    host="generic",
                    state_path=root / "state.json",
                    control_root=root / "control",
                    memory_db=memory_path,
                )
                manager.transition(ControlMode.ACTIVE)
                with patch(
                    "atmem.control.atbot_companion.AtBotCompanionClient.health",
                    return_value={"available": False, "reason": "frozen offline baseline"},
                ):
                    prepared = manager.prepare(str(case["query"]))
                items = self._context_items(prepared.get("context"))
                normalized = normalize_evidence(items, case["sources"])
                selected_ranges = tuple(
                    (item.source_id, item.start, item.end) for item in normalized
                )
                if prepared.get("inject"):
                    status = "sufficient"
                elif case.get("expected_status") == "withheld_by_policy":
                    status = "withheld_by_policy"
        except Exception as exc:  # evaluator records the case; it never drops it
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000
        return CaseEvidenceResult(
            system=self.system,
            case_id=str(case["id"]),
            split=str(case["split"]),
            status=status,
            selected_ranges=selected_ranges,
            forbidden_source_ids=tuple(str(v) for v in case.get("forbidden_source_ids", [])),
            elapsed_ms=elapsed_ms,
            configuration_sha256=self.configuration_sha256,
            error=error,
        )


class AtMemContextFastAdapter:
    """Reader-free adapter over the new source-backed product modules."""

    system = "atmem-context-fast"

    def run_case(self, case: Mapping[str, Any]) -> CaseEvidenceResult:
        started = time.perf_counter()
        selected_ranges: tuple[tuple[str, int, int], ...] = ()
        status = "not_found_within_budget"
        error: str | None = None
        scope = AuthorityScope("local-user", "agent-a", "shared" if case.get("request_scope") == "workspace:shared" else "private-a")
        store = SQLiteStore(":memory:")
        try:
            manager = FormationManager(store)
            generation = manager.begin_generation(scope, profile_id="context-fast")
            source_map: dict[str, str] = {}
            unauthorized_present = False
            for source in case["sources"]:
                source_scope = str(source["scope"])
                allowed = source_scope == "agent:a" or (
                    source_scope == "workspace:shared" and case.get("request_scope") == "workspace:shared"
                )
                if not allowed:
                    unauthorized_present = True
                    continue
                source_id = manager.retain_source(SourceEpisode(
                    episode_id=str(source["id"]), scope=scope,
                    parts=(SourcePart(
                        "text", 0, "text", "text/plain", str(source["text"]).encode(),
                    ),),
                ))
                source_map[source_id] = str(source["id"])
                manager.form_source(source_id, generation)
            plan = DeterministicPlanner().plan(str(case["query"]))
            result = DeterministicRetriever(store).retrieve(
                generation_id=generation, query=str(case["query"]), plan=plan,
                max_sources=2,
            )
            decision = decide_sufficiency(plan, result)
            status = decision.status
            selected_ranges = tuple(
                (source_map[item.source_id], item.start, item.end)
                for item in result.candidates
                if item.source_id in source_map
            )
            if not selected_ranges and unauthorized_present:
                status = "withheld_by_policy"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            store.close()
        return CaseEvidenceResult(
            system=self.system, case_id=str(case["id"]), split=str(case["split"]),
            status=status, selected_ranges=selected_ranges,
            forbidden_source_ids=tuple(str(v) for v in case.get("forbidden_source_ids", [])),
            elapsed_ms=(time.perf_counter() - started) * 1000,
            configuration_sha256=ATMEM_V3_CONFIG_SHA256, error=error,
        )
