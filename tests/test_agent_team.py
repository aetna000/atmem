from dataclasses import replace
from types import SimpleNamespace

import pytest

from atmem import Memory
from atmem.agent_team import run_agent_team
from atmem.agent_team.local import AgentReply, LocalModelError
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.control.agent_team import execute
from atmem.control.models import ControlMode
from atmem.core.canonical import sha256_hex

SCOPE = AuthorityScope("test-person", "worker", "test-workspace")
QUESTION = "What is my favorite city?"


def add(memory, text, scope=SCOPE):
    item = "source-" + sha256_hex(text)[:12]
    part = EpisodePart(part_id=item, ordinal=0, kind="text", source_type="user_message",
                       content=text, content_sha256="sha256:" + sha256_hex(text))
    memory.form_episode(EpisodeIngestRequest(item, item, scope, (part,)))


@pytest.fixture
def memory(tmp_path):
    db = Memory(tmp_path / "test.db", auto_vectors=False, allow_insecure_typed_development=True)
    try:
        add(db, "My favorite city is Tallinn.")
        yield db
    finally:
        db.close()


class Agents:
    model = "test-reader"

    def __init__(self, quote="Tallinn"):
        self.quote = quote
        self.inputs = []

    def ensure_available(self):
        pass

    def invoke(self, role, question, evidence):
        self.inputs.append((role, evidence))
        return AgentReply(self.quote, 24, 3)


def test_adaptive_direct_then_crowded_review_then_budget_stop(memory):
    agents = Agents()
    direct = run_agent_team(memory, SCOPE, QUESTION, agents=agents)
    assert direct["answer"] == "Tallinn" and direct["model_calls"] == 1 and direct["lookups"] == 1
    for text in ("My favorite food is soba.", "My favorite color is lilac.",
                 "My favorite animal is rabbit.", "My favorite sport is tennis."):
        add(memory, text)
    agents.inputs.clear()
    reviewed = run_agent_team(memory, SCOPE, QUESTION, agents=agents)
    assert [s["role"] for s in reviewed["steps"]] == ["lookup", "expanded_lookup", "reviewer", "reader"]
    assert agents.inputs[1] == ("reader", "Tallinn") and reviewed["answer"] == "Tallinn"
    assert reviewed["source_ids"] and reviewed["steps"][2]["receipt_id"]
    assert reviewed["input_tokens"] == 48 and reviewed["output_tokens"] == 6
    stopped = run_agent_team(memory, SCOPE, QUESTION, max_calls=1, agents=agents)
    assert stopped["outcome"] == "abstained" and stopped["model_calls"] == 0
    assert len(agents.inputs) == 2


def test_scope_and_quote_boundaries(memory):
    for scope in (replace(SCOPE, subject_id="other-person"), replace(SCOPE, workspace_id="other-space")):
        agent = Agents()
        report = run_agent_team(memory, scope, QUESTION, agents=agent)
        assert report["outcome"] == "abstained" and not agent.inputs
    for quote in ("source ID never stored", "atmem-context"):
        report = run_agent_team(memory, SCOPE, QUESTION, agents=Agents(quote))
        assert report["outcome"] == "abstained" and report["source_ids"] == []


def test_reader_must_quote_reviewer_handoff(memory):
    class Disagreeing(Agents):
        def invoke(self, role, question, evidence):
            return AgentReply("Tallinn" if role == "reviewer" else "favorite", 12, 2)
    report = run_agent_team(memory, SCOPE, QUESTION, policy="fixed", agents=Disagreeing())
    assert report["outcome"] == "abstained" and report["steps"][-1]["status"] == "withheld"


def test_provider_failure_counts_attempt_and_unknown_usage(memory):
    class Offline(Agents):
        def invoke(self, role, question, evidence):
            raise LocalModelError("Disconnected.")
    report = run_agent_team(memory, SCOPE, QUESTION, agents=Offline())
    assert report["model_calls"] == 1 and not report["usage_complete"]
    assert report["outcome"] == "failed" and not report["source_ids"]


def test_malformed_reply_is_a_metered_failure(memory):
    report = run_agent_team(memory, SCOPE, QUESTION, agents=Agents(quote=None))
    assert report["outcome"] == "failed" and report["steps"][-1]["status"] == "invalid"
    assert report["usage_complete"] and report["input_tokens"] == 24
    assert report["steps"][-1]["receipt_id"]


def test_change_during_model_call_withholds_previous_evidence(memory):
    class Correction(Agents):
        def invoke(self, role, question, evidence):
            add(memory, "My favorite city is Lima.")
            return AgentReply("Tallinn", 12, 2)
    report = run_agent_team(memory, SCOPE, QUESTION, agents=Correction(), policy="fixed")
    assert report["outcome"] == "abstained" and report["model_calls"] == 1
    assert "Tallinn" not in str(report)


def test_dashboard_uses_account_scope_and_active_authority():
    account = {"username":"alice","role":"investigator","scope":{"subject_id":SCOPE.subject_id}}
    session = lambda: {"account":account}
    active = SimpleNamespace(mode=ControlMode.ACTIVE)
    manager = SimpleNamespace(effective_state=lambda:(active,None),
        _memory_authority_scope=lambda *args, **kwargs:(SCOPE,None),
        delegated_context_applies=lambda **kwargs:False)
    with pytest.raises(ValueError):
        execute(manager, session, {"subject_id":"someone-else"})
    for role, scope, mode in (("viewer",{},ControlMode.ACTIVE), ("investigator",{"run_id":"r"},ControlMode.ACTIVE),
                              ("investigator",{"workspace_id":"other"},ControlMode.ACTIVE), ("investigator",{},ControlMode.SHADOW)):
        account.update(role=role, scope={"subject_id":SCOPE.subject_id, **scope})
        active.mode = mode
        with pytest.raises(PermissionError):
            execute(manager, session, {"question":QUESTION})
    active.mode = ControlMode.ACTIVE
    manager.delegated_context_applies = lambda **kwargs:True
    with pytest.raises(PermissionError, match="delegated"):
        execute(manager, session, {"question":QUESTION})
