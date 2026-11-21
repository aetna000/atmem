"""Adversarial offline input checks, not a task-quality benchmark."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from atmem.feedback.baseline import BaselineError, validate_baseline


FIXTURES = Path(__file__).parent / "fixtures" / "feedback"


@pytest.fixture
def manifest():
    return json.loads((FIXTURES / "baseline-manifest.json").read_text())


def test_frozen_fixture_cannot_claim_success_or_authorize_spending(manifest):
    corpus = (FIXTURES / "contract-corpus.json").read_bytes()
    assert sha256(corpus).hexdigest() == manifest["corpus"]["sha256"]
    assert json.loads(corpus) == manifest["tasks"]
    result = validate_baseline(manifest)
    assert result.task_count == 6
    assert result.claim == "contract_only"
    assert result.qualification == "not_evaluated"
    assert result.paid_calls_authorized is False
    assert result == validate_baseline(deepcopy(manifest))
    manifest["candidate"]["id"] = "different-candidate"
    assert validate_baseline(manifest).digest != result.digest


@pytest.mark.parametrize("change", [
    lambda m: m["baselines"].pop("native"),
    lambda m: m["baselines"]["atmem"].update(observations="passed"),
    lambda m: m["baselines"]["atmem"].update(source_commit="main"),
    lambda m: m["baselines"]["atmem"].update(source_commit="a" * 40),
    lambda m: m["candidate"].update(memory_sha256="b" * 64),
    lambda m: m["candidate"].update(max_attempts=4),
    lambda m: m["candidate"].update(max_attempts=True),
    lambda m: m["budget"].update(usd=1),
    lambda m: m["budget"].update(model_calls=1),
    lambda m: m["budget"].update(tokens=1),
    lambda m: m["budget"].update(seconds=float("inf")),
    lambda m: m["budget"].update(disk_bytes=0),
    lambda m: m["budget"].update(tasks=5),
    lambda m: m["budget"].update(tokens=False),
    lambda m: m["gates"].update(false_denial_rate_max=1),
    lambda m: m["gates"].update(unauthorized_admissions_max=False),
    lambda m: m["gates"].pop("coverage_loss_pp_max"),
    lambda m: m.update(approved=True),
    lambda m: m["corpus"].update(kind="held_out"),
    lambda m: m["corpus"].update(egress="provider"),
    lambda m: m["tasks"][0].update(evidence_time=1700000001),
    lambda m: m["tasks"][1].update(episode="episode-0"),
    lambda m: m["tasks"][1].update(paraphrase_group="group-0"),
    lambda m: m["tasks"][1].update(id=m["tasks"][0]["id"]),
    lambda m: m["tasks"][0]["actions"][0].update(checks=[]),
    lambda m: m["tasks"][0]["actions"][0].update(checks=["x", "x"]),
    lambda m: m["tasks"][0]["actions"][1].update(id="read"),
    lambda m: m["tasks"][0]["verification"].update(method="model_judgement"),
    lambda m: m["tasks"][0]["verification"].update(method="host_report"),
])
def test_preflight_rejects_unsafe_or_misleading_evaluations(manifest, change):
    change(manifest)
    with pytest.raises(BaselineError):
        validate_baseline(manifest)


def test_missing_capture_is_not_backfilled_into_a_result(manifest):
    # A schema for prospective inputs cannot accept a caller's asserted results.
    manifest["tasks"][0]["verified_success"] = True
    with pytest.raises(BaselineError):
        validate_baseline(manifest)
