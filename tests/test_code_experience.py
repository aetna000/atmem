from dataclasses import replace
from hashlib import sha256
import hmac

import pytest

from atmem.code.experience import CodeExperience
from atmem.core.canonical import canonical_json
from atmem.knowledge.contracts import ExecutionReceipt, ExperienceProposal, SourceAnchor
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.environment import environment_digest
from tests.test_knowledge_lifecycle import init_repository

KEY = b"x" * 32


def sign(value):
    return hmac.new(KEY, canonical_json(value.to_dict()).encode(), sha256).hexdigest()


def scenario(env, *, outcome="observed_pass", exit_code=0):
    init_repository(env)
    source = CodeKnowledge(env.app, env.scope)
    snapshot, _, _ = source.capture(str(env.root), environment_digest())
    result = b"1 passed in 0.01s"
    receipt = ExecutionReceipt("receipt", env.scope, "producer", "attempt", snapshot.snapshot_id, snapshot.configuration_sha256,
                               ("python", "-m", "pytest"), exit_code, sha256(result).hexdigest(), "evidence")
    proposal = ExperienceProposal("proposal", env.scope, snapshot.snapshot_id, "Check main function behavior",
                                 "The command reported the captured test result.", outcome,
                                 (SourceAnchor("main.py", dict(snapshot.files)["main.py"], 1, 2),), ("receipt",))
    service = CodeExperience(env.app, env.scope, producer_keys={"producer": KEY})
    return service, snapshot, receipt, result, proposal


def test_receipt_authentication_and_exact_result_binding(code_env):
    service, snapshot, receipt, result, _ = scenario(code_env)
    with pytest.raises(PermissionError):
        service.receipt(receipt, snapshot, result, "forged")
    with pytest.raises(ValueError, match="digest"):
        service.receipt(receipt, snapshot, b"other", sign(receipt))
    assert service.receipt(receipt, snapshot, result, sign(receipt))["assurance"] == "authenticated_producer_report"
    altered = replace(receipt, exit_code=1)
    with pytest.raises(ValueError, match="identity conflict"):
        service.receipt(altered, snapshot, result, sign(altered))


def test_no_self_asserted_or_wrong_target_execution_outcome(code_env):
    service, snapshot, receipt, result, proposal = scenario(code_env)
    with pytest.raises(ValueError, match="uncaptured"):
        service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    failed = replace(receipt, exit_code=1)
    service.receipt(failed, snapshot, result, sign(failed))
    with pytest.raises(ValueError, match="pass not supported"):
        service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))


def test_observation_uses_existing_typed_admission_not_user_fact(code_env):
    env = code_env
    # Ephemeral unit fixture only. Installed-product runs require encryption.
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env)
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    assert formed["formed"], formed
    from atmem.code.formation import memory_subject_id
    record = env.memory.store.get_record(memory_subject_id(env.scope), formed["record_ids"][0])
    assert record["source_type"] == "tool_output"
    assert record["trust_tier"] == "host_asserted_observation"
    assert record["raw"]["typed_unit"]["kind"] == "environment_state"
    assert "verified_fix" not in record["content"]
    assert service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))["replayed"]


def test_cross_revision_applicability_without_graph(code_env):
    from atmem.code.context import source_current
    from atmem.code.contracts import CodeContextRequest
    from atmem.code.formation import memory_subject_id
    env = code_env
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env)
    env.app.settings(env.project, {"graph_enabled": False})
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    assert formed["formed"], formed
    record = env.memory.store.get_record(memory_subject_id(env.scope), formed["record_ids"][0])
    request = CodeContextRequest("request", "session", "turn", "main function", 4096, env.scope)
    assert not source_current(env.memory.store, request, record, None)
    assert source_current(env.memory.store, request, record, str(env.root))
    (env.root / "unrelated.py").write_text("x = 1\n")
    assert source_current(env.memory.store, request, record, str(env.root))
    (env.root / "pyproject.toml").write_text('[project]\nname="changed"\n')
    assert not source_current(env.memory.store, request, record, str(env.root))
    (env.root / "pyproject.toml").unlink()
    (env.root / "main.py").write_text("def main(): return 2\n")
    assert not source_current(env.memory.store, request, record, str(env.root))


@pytest.mark.parametrize("outcome,exit_code", [("observed_failure", 1), ("unknown", None)])
def test_failed_and_unknown_attempts_remain_attributed_observations(code_env, outcome, exit_code):
    env = code_env
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env, outcome=outcome, exit_code=exit_code)
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    assert formed["formed"], formed
    assert formed["assurance"] == "authenticated_attempt_observation_not_verified_fix"


def test_foreign_scope_and_environment_receipts_rejected(code_env):
    service, snapshot, receipt, result, proposal = scenario(code_env)
    foreign = replace(receipt, scope=replace(receipt.scope, profile_id="private"))
    with pytest.raises(PermissionError):
        service.receipt(foreign, snapshot, result, sign(foreign))
    changed = replace(receipt, environment_sha256="b" * 64)
    with pytest.raises(ValueError, match="environment"):
        service.receipt(changed, snapshot, result, sign(changed))
    altered = replace(proposal, scope=replace(proposal.scope, project_id="foreign"))
    with pytest.raises(PermissionError):
        service.form(altered, snapshot, producer_id="producer", signature=sign(altered))


def test_negative_words_in_attributed_report_are_not_a_false_polarity_claim(code_env):
    env = code_env
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env)
    proposal = replace(proposal, observation="Updated source_path to reject controls. Secret screening and traversal checks remain in place. No user files changed.")
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    assert formed["formed"], formed
