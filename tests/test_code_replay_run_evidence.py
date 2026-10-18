import pytest

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.run_evidence import RunReplayEvidence


def test_per_run_topology_preserves_normal_protection_authority_and_legacy_reads(tmp_path):
    scope = EvidenceScope("benchmark", "operator", "fixture")
    principal = EvidencePrincipal("operator", EvidenceRole.ADMINISTRATOR, scope)
    root = tmp_path / "legacy" / "vault"
    original = ReplayEvidence(root, vault_id="legacy", scope=scope)
    original.capture(run_id="old-run", kind="fixture", principal=principal, payload={"secret": "old"})
    scoped = RunReplayEvidence(root, vault_id="legacy", scope=scope, writing_run="fresh-run")
    assert scoped.inspect(principal, "fresh-run") == []
    scoped.capture(run_id="fresh-run", kind="fixture", principal=principal, payload={"secret": "new"})
    assert scoped.inspect(principal, "fresh-run")[0]["envelope"]["payload"] == {"secret": "new"}
    assert scoped.inspect(principal, "old-run")[0]["envelope"]["payload"] == {"secret": "old"}
    assert scoped.for_run("fresh-run").service.protection_status()["at_rest_state"] == "encrypted"
    assert original.inspect(principal, "fresh-run") == []
    with pytest.raises(PermissionError):
        scoped.capture(run_id="old-run", kind="fixture", principal=principal, payload={})
    outsider = EvidencePrincipal("other", EvidenceRole.ADMINISTRATOR, EvidenceScope("other", "operator", "fixture"))
    with pytest.raises(PermissionError):
        scoped.inspect(outsider, "fresh-run")
