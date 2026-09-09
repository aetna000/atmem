import pytest
from atmem.onboarding import OnboardingService
def test_onboarding_resume_activation_and_rollback(tmp_path):
    service=OnboardingService(tmp_path/"state.json",{"store":lambda:("failed","not configured")}); state=service.plan(service.discover()); assert state.plan
    calls=[]
    with pytest.raises(PermissionError): service.apply({},consent=False)
    service.apply({"configure:store":lambda:calls.append("apply") or {"ok":True}},consent=True)
    service.apply({"configure:store":lambda:calls.append("duplicate")},consent=True); assert calls==["apply"]
    with pytest.raises(RuntimeError): service.activate(lambda:{})
    service.activate(lambda:{x:True for x in ("capture","paraphrase","context","evidence","restore")})
    service.rollback({"configure:store":lambda:calls.append("rollback")}); assert service.load().phase=="rolled_back"
