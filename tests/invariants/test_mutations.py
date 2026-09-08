from atmem.invariants import AssertionResult,evaluate_registry,load_registry
def test_each_seeded_violation_fails_only_its_invariant():
    registry=load_registry()
    for selected in registry.invariants:
        results=[AssertionResult(i.assertions[0],"base",True,i is not selected,"synthetic") for i in registry.invariants]
        failed=[v.invariant_id for v in evaluate_registry(registry,results) if v.status.value=="unproven"]
        assert failed==[selected.invariant_id]
