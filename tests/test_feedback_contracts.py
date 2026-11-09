"""Wire validation cannot confer authority or erase action/provenance boundaries."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import jsonschema
import pytest

from atmem.contracts.feedback import (
    ActivationReceipt, ActionCheck, ActionObservation, ActionRequirement, CONTRACTS,
    ExampleExport, FeedbackScope, MCPInvocation, OutcomeRecord, QualificationReceipt,
    RuleCandidate, RulePredicate, RetrievalProfileCandidate, SourceRevision, VerificationReceipt, json_schema,
)
from atmem.knowledge.rag.contracts import RagHit, RagQuery, RagSource


SCOPE = FeedbackScope("local", "alice", "writer", "project")
CHECK = ActionCheck("required_fact", "mechanical", "pass", "exact fixture readback")
SOURCE = SourceRevision("source", 1, "a" * 64)
HIT = RagHit("law", SCOPE, "edition-1", "doc-1", "section-1", "Synthetic law",
             "urn:fixture:law", "section 1", "A fictional filing deadline is ten days.",
             sha256(b"A fictional filing deadline is ten days.").hexdigest(),
             "XX", "2025-01-01", "2026-01-01")
OUTCOME = OutcomeRecord("outcome", SCOPE, "run", "turn",
    (ActionRequirement("write", "fixture.write", "v1", "write", ("required_fact",)),),
    (ActionObservation("write", "call", "fixture.write", "v1", {"body": "ten days"},
                       {"accepted": True}, (CHECK,)),))
SAMPLES = (
    RetrievalProfileCandidate("profile", SCOPE, (SOURCE,)),
    SCOPE, SOURCE, OUTCOME.required[0], CHECK, OUTCOME.observations[0], OUTCOME,
    VerificationReceipt("verification", SCOPE, "outcome", OUTCOME.content_digest,
                        "call", "reader", "v1", "evidence", (CHECK,), "independent_readback"),
    RulePredicate("equals", ("target",), "staging"),
    RuleCandidate("rule", SCOPE, "fixture.write", "v1", (SOURCE,),
                  (RulePredicate("present", ("target",)),), "review required"),
    QualificationReceipt("qualification", SCOPE, "a" * 64, "b" * 64, {"adapter": "v1"},
                         "inconclusive", 1, 100, {"n": 0}),
    ActivationReceipt("activation", SCOPE, "a" * 64, "qualification", "owner", 1, "shadow"),
    ExampleExport("export", SCOPE, "consent", 1, "fixture only", "recipient", ("outcome",), "a" * 64),
    MCPInvocation("fixture.write", "v1", {"target": "staging"}, "retry-1"),
    RagSource("law", SCOPE, "sqlite", "law", "edition-1", "none"), RagQuery("law", "deadline"), HIT,
)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda v: v.format)
def test_every_contract_roundtrips_under_its_shipped_closed_schema(sample):
    assert {type(s) for s in SAMPLES} == set(CONTRACTS) | {RagSource, RagQuery, RagHit}
    cls = type(sample)
    wire = json.loads(json.dumps(sample.to_dict()))
    restored = cls.from_dict(wire)
    assert restored == sample
    assert restored.content_digest == sample.content_digest
    name = cls.format.removeprefix("atmem-") + ".json"
    if not name.startswith("feedback-"):
        name = "feedback-" + name
    schema = json.loads((Path(__file__).parents[1] / "atmem/schemas/v1" / name).read_text())
    assert schema == json_schema(cls)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(wire, schema)
    wire["role"] = "administrator"
    with pytest.raises(ValueError):
        cls.from_dict(wire)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wire, schema)


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(verified_success=True),
    lambda v: v["scope"].update(role="administrator"),
    lambda v: v.update(revision=True),
    lambda v: v.update(revision=0),
    lambda v: v.update(delivery="delivered"),
    lambda v: v["required"].append(deepcopy(v["required"][0])),
    lambda v: v["observations"].append(deepcopy(v["observations"][0])),
    lambda v: v["observations"][0].update(action_id="unknown"),
    lambda v: v["observations"][0].update(assurance="independent_readback"),
    lambda v: v["observations"][0]["checks"].append(deepcopy(v["observations"][0]["checks"][0])),
    lambda v: v["observations"][0].update(result=float("nan")),
    lambda v: v["observations"][0].update(arguments={"body": "x" * 70_000}),
])
def test_outcome_rejects_forged_authority_and_invented_completion(mutate):
    value = deepcopy(OUTCOME.to_dict())
    mutate(value)
    with pytest.raises(ValueError):
        OutcomeRecord.from_dict(value)


def test_host_neutral_scope_reuses_existing_authority_and_evidence_contracts():
    assert SCOPE.authority_scope().subject_id == SCOPE.evidence_scope().subject_id == "alice"
    other = FeedbackScope("local", "alice", "reader", "project")
    assert SCOPE.partition != other.partition
    for subject in ("", " alice", "alice\n", "../alice"):
        with pytest.raises(ValueError):
            FeedbackScope("local", subject, "writer", "project")


@pytest.mark.parametrize("operator,value", [("exec", "print(1)"), ("present", True), ("equals", {}), ("equals", [])])
def test_rule_language_is_data_only(operator, value):
    with pytest.raises(ValueError):
        RulePredicate(operator, ("target",), value)


def test_document_filters_are_explicit_and_half_open():
    assert HIT.matches(RagQuery("law", "deadline", jurisdiction="XX", as_of="2025-01-01"))
    assert not HIT.matches(RagQuery("law", "deadline", as_of="2026-01-01"))
    assert not HIT.matches(RagQuery("law", "deadline", jurisdiction="YY"))
    unknown = HIT.to_dict()
    unknown.update(effective_from=None, effective_to=None, jurisdiction=None)
    hit = RagHit.from_dict(unknown)
    assert hit.matches(RagQuery("law", "deadline"))
    assert not hit.matches(RagQuery("law", "deadline", as_of="2025-01-01"))
    assert not hit.matches(RagQuery("law", "deadline", jurisdiction="XX"))


@pytest.mark.parametrize("patch", [
    {"text": "tampered"}, {"text_sha256": "b" * 64}, {"citation": "https://user:password@example.test/doc"},
    {"citation": ""}, {"effective_to": "2024-01-01"}, {"effective_from": "2025-02-30"},
    {"revision": ""}, {"text": "x" * 33_000},
])
def test_document_provenance_rejects_tampering_and_unsafe_metadata(patch):
    value = HIT.to_dict()
    value.update(patch)
    with pytest.raises(ValueError):
        RagHit.from_dict(value)


def test_qualification_cannot_have_unbounded_lifetime():
    sample = next(s for s in SAMPLES if isinstance(s, QualificationReceipt)).to_dict()
    sample["expires_at"] = sample["issued_at"] + 604801
    with pytest.raises(ValueError):
        QualificationReceipt.from_dict(sample)


def test_wire_copies_nested_arrays_before_the_caller_can_change_them():
    wire = OUTCOME.to_dict()
    wire["observations"][0]["result"] = {"parts": [{"text": "original returned bytes"}]}
    restored = OutcomeRecord.from_dict(wire)
    wire["observations"][0]["result"]["parts"][0]["text"] = "late caller mutation"
    assert restored.observations[0].result["parts"][0]["text"] == "original returned bytes"
    exported = restored.to_dict()
    exported["observations"][0]["result"]["parts"][0]["text"] = "mutated serialization"
    assert restored.observations[0].result["parts"][0]["text"] == "original returned bytes"
