from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from openai import OpenAI

from .audit import build_review_template, sign_audit_review


REVIEW_INSTRUCTIONS = """You are an independent dataset auditor. Review only the supplied
blinded synthetic rows. Do not infer labels from IDs, row ordering, tag frequencies, or
template correlations. Choose exactly one listed choice using these semantic rules:

- operation: REJECT when evidence has an unresolved direct contradiction, regardless of the
  proposed mutation; otherwise ADD when no prior record exists and new supported evidence should be stored;
  UPDATE when a later correction changes an active record; SUPERSEDE when evidence explicitly
  replaces an obsolete value; NOOP when duplicate evidence repeats the already-active value;
  REJECT when the proposal is non-memory, hypothetical, unverified, or explicitly must not be stored.
- memory_class: durable_fact for a stable stated fact; temporary_state for a value explicitly
  bounded in time; episode for an observed event; procedure for ordered steps; non_memory for
  a greeting or other content explicitly unrelated to durable state.
- evidence_support: UNSUPPORTED for an unverified hypothetical draft; AMBIGUOUS when authorized
  evidence contains conflicting claims; SUPPORTED otherwise.
- target_selection means selection of an existing canonical record to mutate. REVIEW for
  conflicting evidence; otherwise target:none for every ADD with an empty initial_state and for
  REJECT; target:active only for UPDATE, SUPERSEDE, or duplicate-memory NOOP when target:active
  exists in initial_state. Never choose target:active merely because new ADD content should become
  active after admission.
- retrieval_usefulness: INSUFFICIENT_EVIDENCE for REJECT or conflicting evidence; NOT_USEFUL
  for a duplicate NOOP; USEFUL otherwise.

Each question is independent. Expected synthetic challenge conditions are not defects: unresolved
contradictions, AMBIGUOUS/REVIEW/INSUFFICIENT_EVIDENCE outcomes, rejected non-memory, rejected
hypothetical content, and a rejected candidate with a recognizable memory class must all have an
empty critical_findings list when they follow this rubric. Record a concise critical finding only
for an actual generator defect that prevents consistent assignment, a real credential/private-data
leak, incompatible licensing, an invalid scope/target, or a label-semantic inconsistency. A note
that a credential-shaped field was withheld is safe synthetic metadata, not a leaked credential.
Return every supplied example exactly once and do not add commentary outside the schema."""


def _output_schema(choice_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "example_id": {"type": "string"},
                        "selected_choice_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": choice_ids},
                            "minItems": 1,
                            "maxItems": 1,
                        },
                        "critical_findings": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["example_id", "selected_choice_ids", "critical_findings"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["rows"],
        "additionalProperties": False,
    }


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _env_value(path: Path, name: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
                value = value[1:-1]
            if value:
                return value
    raise RuntimeError(f"{name} is not configured in {path}")


def review_packet(
    packet: dict[str, Any], *, client: OpenAI, model: str, chunk_size: int = 40
) -> dict[str, Any]:
    template = build_review_template(packet)
    expected_ids = [row["example_id"] for row in packet["rows"]]
    reviewed_by_id: dict[str, dict[str, Any]] = {}
    response_ids: list[str] = []
    usage: list[dict[str, Any]] = []
    question_ids = list(dict.fromkeys(row["question_id"] for row in packet["rows"]))
    for question_id in question_ids:
        question_rows = [row for row in packet["rows"] if row["question_id"] == question_id]
        choice_ids = question_rows[0]["choice_ids"]
        if any(row["choice_ids"] != choice_ids for row in question_rows):
            raise ValueError(f"choice set varies within question {question_id}")
        for start in range(0, len(question_rows), chunk_size):
            rows = question_rows[start : start + chunk_size]
            request = {
                "model": model,
                "instructions": REVIEW_INSTRUCTIONS,
                "input": json.dumps({"rows": rows}, sort_keys=True, separators=(",", ":")),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "atmem_laya_audit_chunk",
                        "strict": True,
                        "schema": _output_schema(choice_ids),
                    }
                },
                "max_output_tokens": 8_000,
                "store": False,
            }
            # GPT-5 reasoning models reject the legacy sampling-temperature
            # parameter; GPT-4.x reviewers retain the deterministic setting.
            if not model.startswith("gpt-5"):
                request["temperature"] = 0
            response = client.responses.create(**request)
            if response.status != "completed":
                raise RuntimeError(f"review response {response.id} ended with status {response.status}")
            value = json.loads(response.output_text)
            chunk_rows = value.get("rows")
            if not isinstance(chunk_rows, list) or len(chunk_rows) != len(rows):
                raise ValueError(f"review response {response.id} returned incomplete membership")
            expected_chunk_ids = [row["example_id"] for row in rows]
            if [row.get("example_id") for row in chunk_rows] != expected_chunk_ids:
                raise ValueError(f"review response {response.id} returned different membership or order")
            for row in chunk_rows:
                selected = row.get("selected_choice_ids")
                if not isinstance(selected, list) or len(selected) != 1 or selected[0] not in choice_ids:
                    raise ValueError(f"review response {response.id} selected an unknown choice")
                reviewed_by_id[row["example_id"]] = row
            response_ids.append(response.id)
            usage.append(response.usage.to_dict() if response.usage is not None else {})
    if set(reviewed_by_id) != set(expected_ids):
        raise ValueError("review response membership differs from the blinded packet")
    reviewed = [reviewed_by_id[example_id] for example_id in expected_ids]
    template["reviewer"] = {
        "id": f"openai:{model}:independent-audit-v1",
        "kind": "independent-model",
        "model": model,
        "method": "responses-structured-output-chunks",
        "response_ids": response_ids,
        "usage": usage,
        "independent_attestation": True,
        "answer_key_accessed": False,
    }
    template["signed_at"] = datetime.now(timezone.utc).isoformat()
    template["rows"] = reviewed
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return sign_audit_review(template, private_pem)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a firewalled OpenAI review of a blinded Spec 041 audit packet")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--chunk-size", type=int, default=40)
    args = parser.parse_args()
    if args.chunk_size < 1 or args.chunk_size > 100:
        raise ValueError("chunk size must be between 1 and 100")
    api_key = _env_value(args.env_file, "OPENAI_API_KEY")
    model = args.model or _env_value(args.env_file, "OPENAI_DEEP_MODEL")
    result = review_packet(
        _read_object(args.packet),
        client=OpenAI(api_key=api_key),
        model=model,
        chunk_size=args.chunk_size,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"model": model, "reviewed": len(result["rows"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
