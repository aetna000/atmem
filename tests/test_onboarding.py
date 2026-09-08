from atmem.control.explain import explain
from atmem.onboarding import OnboardingService
def test_discovery_is_redacted_and_explanation_never_invents_proof(tmp_path):
    state=OnboardingService(tmp_path/"s.json",{"host":lambda:("ok","ready")}).discover()
    assert "secret" not in str(state).lower()
    value=explain({"record_id":"r"}); assert value["reason_codes"]==["insufficient_evidence"] and not value["evidence_complete"]
