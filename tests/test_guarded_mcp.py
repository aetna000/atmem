"""Real local effects, native denials and crash ambiguity; no production claims."""
from dataclasses import replace
import threading

import pytest

from atmem import Memory
from atmem.contracts.feedback import MCPInvocation
from atmem.feedback.store import FeedbackError
from atmem.mcp.guarded import GuardedDispatcher
from test_feedback_actions import actions_fixture


SCHEMA = {"type": "object", "properties": {"body": {"type": "string", "maxLength": 100}},
          "required": ["body"], "additionalProperties": False}


def dispatcher_fixture(tmp_path):
    f, _ = actions_fixture(tmp_path)
    f.feedback.memory = Memory(":memory:", auto_vectors=False)
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                           operations=("read", "execute"), expires_at=1_700_010_000)
    dispatcher = GuardedDispatcher(f.feedback, versions={"adapter": "local-fixture-v1"})
    path = tmp_path / "effects.txt"
    def write(arguments):
        with path.open("a") as stream:
            stream.write(arguments["body"]+"\n")
        return {"accepted": True}
    dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                        invoke=write, native_guard=lambda args: args["body"] != "forbidden")
    return f, dispatcher, path


def test_real_write_once_and_native_denial_even_when_client_wants_it(tmp_path):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    try:
        blocked = dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"body": "forbidden"}, "blocked"))
        assert blocked["status"] == "blocked" and not path.exists()
        invocation = MCPInvocation("fixture.write", "v1", {"body": "allowed"}, "allowed")
        result = dispatcher.execute(f.session, invocation)
        assert result["status"] == "reported_complete" and path.read_text() == "allowed\n"
        retry = dispatcher.execute(f.session, invocation)
        assert retry["receipt_id"] == result["receipt_id"]
        assert path.read_text() == "allowed\n"
        assert dispatcher.inspect(f.session, result["receipt_id"])["status"] == "reported_complete"
        with pytest.raises(FeedbackError, match="conflicting_retry"):
            dispatcher.execute(f.session, replace(invocation, arguments={"body": "different"}))
        for changed in (replace(invocation, schema_version="v2"),
                        replace(invocation, tool="arbitrary.wrapper"),
                        replace(invocation, idempotency_key="injected", arguments={"body": "safe", "endpoint": "untrusted"})):
            with pytest.raises(FeedbackError):
                dispatcher.execute(f.session, changed)
        assert path.read_text() == "allowed\n"
    finally:
        f.feedback.memory.close()


def test_handler_error_after_effect_is_uncertain_and_never_retried(tmp_path):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    try:
        def write_then_disconnect(arguments):
            path.write_text("already written")
            raise TimeoutError("PRIVATE provider token and content must not escape")
        dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                            invoke=write_then_disconnect, native_guard=lambda args: True)
        call = MCPInvocation("fixture.write", "v1", {"body": "first"}, "uncertain")
        receipt = dispatcher.execute(f.session, call)
        assert receipt["status"] == "uncertain" and "PRIVATE" not in str(receipt)
        path.write_text("owner inspected")
        assert dispatcher.execute(f.session, call) == receipt
        assert path.read_text() == "owner inspected"
        with pytest.raises(FeedbackError, match="uncertain_effect_requires_reconciliation"):
            dispatcher.execute(f.session, replace(call, idempotency_key="new-key"))
        # Reattaching a handler after a process restart must not bypass the hold.
        restarted = GuardedDispatcher(f.feedback, versions=dispatcher.versions)
        restarted.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                           invoke=lambda args: path.write_text("duplicate"), native_guard=lambda args: True)
        with pytest.raises(FeedbackError, match="uncertain_effect_requires_reconciliation"):
            restarted.execute(f.session, replace(call, idempotency_key="after-restart"))
        assert path.read_text() == "owner inspected"
    finally:
        f.feedback.memory.close()


def test_guard_argument_mutation_and_errors_never_bypass_policy(tmp_path):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    try:
        def mutating_guard(args):
            args["body"] = "not the final value"
            return True
        dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                            invoke=lambda args: path.write_text(args["body"]), native_guard=mutating_guard)
        assert dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"body": "original"}, "mutation"))["status"] == "blocked"
        assert not path.exists()
        def broken_guard(args):
            raise RuntimeError("PRIVATE")
        dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                            invoke=lambda args: path.write_text("must not occur"), native_guard=broken_guard)
        assert dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"body": "new"}, "denied"))["status"] == "blocked"
        assert not path.exists()
    finally:
        f.feedback.memory.close()


@pytest.mark.parametrize("schema", [
    {"type":"object", "properties":{"body":{"type":"array"}}, "additionalProperties":False},
    {"type":"object", "properties":{"body":{"type":"string", "minimum":1}}, "additionalProperties":False},
    {"type":"object", "properties":{"body":{"type":"integer", "minimum":True}}, "additionalProperties":False},
    {"type":"object", "properties":{}, "required":["missing"], "additionalProperties":False},
    {"type":"object", "properties":{"body":{"type":"string", "enum":[False]}}, "additionalProperties":False},
])
def test_unsupported_contract_is_rejected_before_registration(tmp_path, schema):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    try:
        with pytest.raises(FeedbackError, match="unsupported_schema"):
            dispatcher.register(f.owner["token"], f.scope, tool="unsupported", schema_version="v1", schema=schema,
                invoke=lambda args:path.write_text("must not occur"), native_guard=lambda args:True)
        assert [t["tool"] for t in dispatcher.tools(f.session)["tools"]] == ["fixture.write"]
        assert not path.exists()
    finally:
        f.feedback.memory.close()


def test_single_use_approval_binds_exact_actor_arguments_key_and_handler_generation(tmp_path):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    try:
        dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                            invoke=lambda args: path.write_text(args["body"]), native_guard=lambda args: True,
                            requires_approval=True)
        call = MCPInvocation("fixture.write", "v1", {"body": "approved"}, "specific-call")
        approval = dispatcher.approve(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                                      invocation=call, expires_at=1_700_000_060)
        changed = replace(call, arguments={"body": "changed"}, approval_id=approval)
        assert dispatcher.execute(f.session, changed)["reason"] == "approval_required"
        approved = replace(call, approval_id=approval)
        # The blocked different payload cannot be replaced under the same key.
        with pytest.raises(FeedbackError, match="conflicting_retry"):
            dispatcher.execute(f.session, approved)
        call = replace(call, idempotency_key="fresh-exact-call")
        approval = dispatcher.approve(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                                      invocation=call, expires_at=1_700_000_060)
        approved = replace(call, approval_id=approval)
        assert dispatcher.execute(f.session, approved)["status"] == "reported_complete"
        assert path.read_text() == "approved"
        assert dispatcher.execute(f.session, replace(approved, idempotency_key="replayed"))["reason"] == "approval_required"
        assert path.read_text() == "approved"
    finally:
        f.feedback.memory.close()


def test_hung_write_returns_uncertain_and_is_not_automatically_reexecuted(tmp_path):
    f, dispatcher, path = dispatcher_fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    dispatcher.timeout_seconds = .02
    def slow(args):
        entered.set()
        release.wait(3)
        path.write_text("one eventual effect")
        return {"accepted": True}
    dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
                        invoke=slow, native_guard=lambda args: True)
    try:
        call = MCPInvocation("fixture.write", "v1", {"body": "slow"}, "slow")
        receipt = dispatcher.execute(f.session, call)
        assert entered.is_set() and receipt["status"] == "uncertain"
        assert dispatcher.execute(f.session, call) == receipt
        assert not path.exists()
    finally:
        release.set()
        f.feedback.memory.close()


def test_unknown_write_can_only_be_reconciled_with_independent_terminal_effect(tmp_path):
    from hashlib import sha256
    import json
    from atmem.contracts.feedback import ActionCheck
    from atmem.core.canonical import canonical_json
    from atmem.feedback.verification import Readback
    from test_feedback_verification import verifier_fixture, verify
    f, original, verifier, reader, destination = verifier_fixture(tmp_path)
    f.feedback.memory = Memory(":memory:", auto_vectors=False)
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
        operations=("read", "report", "execute"), expires_at=1_700_010_000)
    dispatcher = GuardedDispatcher(f.feedback, versions={"adapter":"fixture"})
    journal = tmp_path/"operation-journal.json"
    def write(arguments, *, context):
        destination.write_text(arguments["body"])
        journal.write_text(json.dumps({"proxy_execution_id":context["receipt_id"], "backend_terminal":True,
            "effect_reference":context["receipt_id"], "observed_outcome_id":"proxied",
            "observed_run_id":original.run_id, "observed_turn_id":original.turn_id,
            "observed_invocation_id":"call-write", "arguments_sha256":sha256(canonical_json(arguments).encode()).hexdigest()}))
        raise TimeoutError("lost acknowledgement after durable terminal journal")
    dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=SCHEMA,
        invoke=write, native_guard=lambda args:True, with_context=True)
    try:
        invocation = MCPInvocation("fixture.write", "v1", {"body":"ten days"}, "lost-ack")
        execution = dispatcher.execute(f.session, invocation)
        assert execution["status"] == "uncertain" and destination.read_text() == "ten days"
        observation = replace(original.observations[1], arguments=invocation.arguments, evidence_id=execution["receipt_id"])
        outcome = replace(original, outcome_id="proxied", required=(original.required[1],), observations=(observation,))
        f.feedback.report_outcome(f.session, outcome, idempotency_key="proxied")
        def readback(*args, **kwargs):
            data = json.loads(journal.read_text())
            assert destination.read_text() == "ten days"
            return Readback(tuple(ActionCheck(key, "mechanical", "pass", "journal and destination read independently")
                for key in ("fact", "destination")), data)
        verifier.register(f.owner["token"], f.scope, principal_id="destination-reader", version="terminal",
            tool="fixture.write", schema_version="v1", check_ids=("fact", "destination"),
            readback=readback, binding="effect_receipt")
        proof = verify(verifier, reader, outcome, key="terminal-proof")
        options = dict(receipt_id=execution["receipt_id"], verification_id=proof["receipt_id"])
        with pytest.raises(FeedbackError, match="denied"):
            dispatcher.reconcile(f.user["token"], f.scope, **options)
        reconciled = dispatcher.reconcile(f.owner["token"], f.scope, **options)
        assert reconciled["status"] == "verified_complete"
        assert dispatcher.reconcile(f.owner["token"], f.scope, **options) == reconciled
        assert dispatcher.execute(f.session, invocation) == execution  # never repeats original intent
        with f.feedback.store.transaction(f.scope) as tx:
            assert tx.get("proxy_write_hold", "fixture.write") is None
    finally:
        f.feedback.memory.close()
