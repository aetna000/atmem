#!/usr/bin/env python3
"""Exercise a verified Laya artifact through an installed AtMem wheel."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
from time import perf_counter

from atmem.contracts.models import AuthorityScope
from atmem.laya_formation.artifacts import LayaArtifactResolver
from atmem.laya_formation.contracts import FormationDecisionRequest, QuestionDefinitionV1
from atmem.laya_formation.packing import AuthorizedRange, pack_authorized_ranges
from atmem.laya_formation.runtime import LayaDecisionEngine


EXPECTED_VERSION = "2.3.9b1"
TOKENIZER_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    args = parser.parse_args()

    if metadata.version("atmem") != EXPECTED_VERSION:
        raise RuntimeError("compatibility smoke must use the exact candidate wheel")
    bundle = LayaArtifactResolver().resolve(local_dir=args.model_dir)
    started = perf_counter()
    engine = LayaDecisionEngine(bundle, device=args.device, max_inference_ms=120_000)
    source = "The customer explicitly asked to remember the blue workspace theme."
    question_value = bundle.questions["operation"]
    question = QuestionDefinitionV1(
        question_id="operation", semantic_version="1.0.0", kind="choice",
        instructions=question_value["instructions"],
        choice_ids=tuple(question_value["choice_ids"]), allow_abstain=True,
        tokenizer_revision=TOKENIZER_REVISION, max_len=512, head_max_len=192,
        closing_tokens_reserved=1,
        overflow_policy="whole-authorized-ranges-or-review",
    )
    packed = pack_authorized_ranges(
        adapter=engine.packing_adapter, question=question.to_laya_internal(),
        ranges=[AuthorizedRange("range-1", "source-1", 0, len(source), source)],
    )
    request = FormationDecisionRequest(
        request_id="installed-device-smoke", scope=AuthorityScope(
            subject_id="compatibility-user", agent_id="compatibility-agent",
            workspace_id="isolated-test",
        ),
        generation_id="compatibility-generation", canonical_generation=1,
        question=question, calibration=bundle.calibration, packed_input=packed,
        authorized_range_digests={
            "range-1": "sha256:" + hashlib.sha256(source.encode()).hexdigest()
        },
        candidate_digests={},
    )
    response = engine(request)
    diagnostics = engine.diagnostics()
    engine.close()
    print(json.dumps({
        "format": "atmem-installed-laya-profile-smoke-v1",
        "result": "pass", "atmem": metadata.version("atmem"),
        "laya": metadata.version("laya"), "device": diagnostics["device"],
        "model_revision": diagnostics["model_revision"],
        "questions_digest": diagnostics["questions_digest"],
        "calibration_digest": diagnostics["calibration_digest"],
        "response_valid": response.reason_code in {
            "laya_calibrated_choice", "calibrated_low_confidence"
        },
        "inference_ms": diagnostics["latency_ms"],
        "total_load_and_inference_ms": (perf_counter() - started) * 1000,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
