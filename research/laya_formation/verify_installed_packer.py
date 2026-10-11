"""Verify the frozen tokenizer packer through an installed AtMem wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

from atmem.laya_formation.contracts import QuestionDefinitionV1
from atmem.laya_formation.packing import (
    AuthorizedRange,
    LayaPackingAdapter,
    pack_authorized_ranges,
    structural_parity_bytes,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument(
        "--fixture", type=Path,
        default=Path(__file__).parent / "fixtures" / "packer-parity-v1.json",
    )
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    source = fixture["question"]
    question = QuestionDefinitionV1(
        question_id=source["question_id"], semantic_version="1.0.0", kind="choice",
        instructions=source["instructions"], choice_ids=tuple(source["choice_ids"]),
        allow_abstain=True, tokenizer_revision=fixture["tokenizer_revision"],
        max_len=512, head_max_len=192, closing_tokens_reserved=1,
        overflow_policy="whole-authorized-ranges-or-review",
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir / "tokenizer")
    packed = pack_authorized_ranges(
        adapter=LayaPackingAdapter(tokenizer, revision=question.tokenizer_revision),
        question=question.to_laya_internal(),
        ranges=[AuthorizedRange(**row) for row in fixture["ranges"]],
    )
    actual = {
        "head_tokens": packed.head_tokens,
        "state_tokens": packed.state_tokens,
        "total_tokens": packed.total_tokens,
        "overflow": packed.overflow,
        "state_digest": packed.state_digest,
        "structural_sha256": hashlib.sha256(structural_parity_bytes(packed)).hexdigest(),
    }
    if actual != fixture["expected"]:
        raise SystemExit("installed packer differs from the frozen parity fixture")
    print(json.dumps({"result": "pass", **actual}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
