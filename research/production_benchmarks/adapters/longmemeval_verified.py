"""Evaluator-only verified-evidence control for LongMemEval-V2.

This adapter is not a product memory implementation.  It exposes only the
frozen evaluator evidence for the current question so the same official reader
can distinguish memory-pipeline failures from reader failures.
"""

from __future__ import annotations

import json
from pathlib import Path

from memory_modules.memory import Memory, register_memory


@register_memory
class VerifiedEvidenceMemory(Memory):
    memory_type = "atmem_verified_evidence"

    def __init__(self, memory_params: dict[str, object]) -> None:
        super().__init__(memory_params)
        manifest_path = Path(
            str(memory_params.get("requirement_manifest_path") or "")
        ).expanduser().resolve()
        if not manifest_path.is_file():
            raise RuntimeError("verified-evidence adapter requires its frozen manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("visibility") != "evaluator_only"
            or manifest.get("available_to_product") is not False
            or manifest.get("benchmark") != "longmemeval-v2"
        ):
            raise RuntimeError("verified-evidence adapter rejected an unsafe manifest")
        self._by_question: dict[str, str] = {}
        for case in manifest.get("cases") or ():
            question = str(case.get("question_text") or "").strip()
            requirements = case.get("requirements") or ()
            evidence = "\n".join(
                str(row.get("verified_evidence_text") or "").strip()
                for row in requirements
                if str(row.get("verified_evidence_text") or "").strip()
            )
            if not question or not evidence or question in self._by_question:
                raise RuntimeError("verified-evidence manifest has an invalid question map")
            self._by_question[question] = evidence

    def insert(self, trajectory: dict[str, object]) -> None:
        # The control must be independent of memory formation.  Official
        # trajectories are intentionally ignored.
        del trajectory

    def query(self, query: str, query_image: str | None = None) -> list[dict[str, str]]:
        del query_image
        evidence = self._by_question.get(query)
        if evidence is None:
            raise RuntimeError("question is absent from the frozen evaluator manifest")
        return [{"type": "text", "value": evidence}]

    @classmethod
    def reconcile_loaded_memory_config(cls, saved_config, requested_config):
        # The manifest path is host-local but must otherwise remain identical.
        if requested_config is None:
            return saved_config
        if saved_config.get("memory_type") != cls.memory_type:
            raise RuntimeError("saved verified-evidence memory type differs")
        if requested_config.get("memory_type") != cls.memory_type:
            raise RuntimeError("requested verified-evidence memory type differs")
        return requested_config
