"""Read-only phase-0 tools. There is deliberately no agent dispatch command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmarks.code_replay.contracts import (
    ProtocolManifest, StructureExperienceProtocol, StructureExperienceRun, RunManifest, TaskManifest, TrialResult, closed, parse_json,
)
from benchmarks.code_replay.select import SelectionCandidate, SelectionLedger, select_candidates


_TYPES = {"protocol": ProtocolManifest, "structure-experience-protocol": StructureExperienceProtocol,
          "structure-experience-run": StructureExperienceRun, "task": TaskManifest, "run": RunManifest,
          "result": TrialResult, "selection": SelectionLedger}
_MAX_BYTES = 2_000_000


def _read(path: str) -> str:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("input must be a regular metadata file, not a symlink")
    with source.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("input exceeds manifest byte budget")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("input must be UTF-8 JSON") from exc


def preflight(protocol: ProtocolManifest) -> dict:
    """Report absent integrations without trusting user-authored ready flags.

    Future product capability and authorization verifiers must replace these
    explicit blockers. Merely referencing a qualification digest is not proof.
    This phase cannot start a process, spend credit, contact a provider or enroll
    a host. Never call the adapter factory here: it can write credentials.
    """
    if not isinstance(protocol, ProtocolManifest):
        raise ValueError("validated protocol required")
    row = protocol.to_dict()
    return {
        "format": "atmem-click-preflight-v1", "protocol_sha256": protocol.sha256,
        "metadata_valid": True, "ready": False, "can_dispatch": False,
        "expected_sessions": len(row["tasks"]) * len(row["arms"]) * row["repetitions"],
        "blockers": [
            {"code": "execution_authorization_not_integrated", "tasks": ["043:T003"]},
            {"code": "product_capability_verification_not_integrated", "tasks": ["042:T060", "043:T010"]},
            {"code": "experience_applicability_not_qualified", "tasks": ["042:T049", "042:T050", "042:T051"]},
            {"code": "rich_structure_not_qualified", "tasks": ["042:T046", "042:T047", "042:T053", "042:T054"]},
            {"code": "agent_sandbox_not_qualified", "tasks": ["042:T019", "043:T007", "043:T018"]},
            {"code": "sealed_task_artifacts_not_verified", "tasks": ["043:T004", "043:T005", "043:T006"]},
            {"code": "protected_evidence_not_qualified", "tasks": ["043:T008", "043:T009"]},
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate metadata only; does not verify referenced evidence")
    validate.add_argument("kind", choices=sorted(_TYPES))
    validate.add_argument("path")
    select = commands.add_parser("select", help="Apply frozen selection rule to evaluator-supplied discovery metadata")
    select.add_argument("path")
    check = commands.add_parser("preflight", help="Show readiness blockers without dispatch or host changes")
    check.add_argument("path", help="Frozen protocol metadata")
    args = parser.parse_args(argv)
    try:
        raw = _read(args.path)
        if args.command == "validate":
            manifest = _TYPES[args.kind].from_json(raw)
            result = {"format": "atmem-click-validation-v1", "metadata_valid": True,
                      "manifest_sha256": manifest.sha256, "evidence_verified": False, "authorized": False}
            status = 0
        elif args.command == "select":
            row = closed(parse_json(raw), {"format", "anchor_commit", "candidates"}, "discovery input")
            if row["format"] != "atmem-click-discovery-input-v1" or type(row["candidates"]) is not list:
                raise ValueError("unsupported discovery input")
            if len(row["candidates"]) > 100:
                raise ValueError("discovery exceeds frozen horizon")
            ledger = select_candidates(row["anchor_commit"], [SelectionCandidate.from_dict(r) for r in row["candidates"]])
            result = ledger.to_dict()
            status = 0 if result["status"] == "selected" else 2
        else:
            kind = parse_json(raw).get("format")
            protocol_type = StructureExperienceProtocol if kind == StructureExperienceProtocol.format else ProtocolManifest
            result = preflight(protocol_type.from_json(raw))
            status = 2
    except (OSError, ValueError):
        # Never echo raw source, malformed JSON, credentials or arbitrary field
        # values. Detailed internal exception strings are not a log destination.
        result = {"format": "atmem-click-error-v1", "code": "invalid_metadata_input"}
        status = 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return status


if __name__ == "__main__":
    sys.exit(main())
