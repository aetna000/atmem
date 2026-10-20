"""Opt-in inspection of a retained real-agent diagnostic, never a fake run."""
import base64
import json
import os
from pathlib import Path

import pytest


def test_retained_real_agent_attempt_forms_and_revalidates_experience_without_graph():
    root = os.environ.get("ATMEM_REAL_EXPERIENCE_QUALIFICATION_ROOT")
    session = os.environ.get("ATMEM_REAL_EXPERIENCE_QUALIFICATION_SESSION")
    if not root or not session:
        pytest.skip("requires explicitly selected retained real-agent evidence")
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    from benchmarks.code_replay.atmem_bridge import ReplayEvidence
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(Path(root), vault_id="click-20261017", scope=scope)
    agent = evidence.inspect(principal, session)[-1]["envelope"]["payload"]
    assert agent["Click_target_trial"] is False
    assert agent["exit_code"] == 0 and agent["tool_calls"] > 0
    observed = evidence.inspect(principal, "disjoint-product-" + session)[-1]["envelope"]["payload"]
    assert observed["verification_exit_code"] == 0
    assert observed["graph_enabled"] is False
    assert observed["candidate_count"] == observed["admitted_count"] == 1
    assert observed["initial_recalled"] == observed["unrelated_change_recalled"] == 1
    assert observed["changed_anchor_recalled"] == 0
    assert observed["formed"]["review_state"] == "committed"
    assert observed["proposal"]["snapshot_id"] == observed["receipt"]["snapshot_id"]
    outcome = json.loads(base64.b64decode(observed["execution_result_base64"]))
    assert outcome["exit_code"] == 0
    assert b"62 passed" in base64.b64decode(outcome["stdout_base64"])
