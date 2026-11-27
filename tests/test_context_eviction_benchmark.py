from copy import deepcopy

import pytest

from tools.benchmark_context_eviction import benchmark, project, synthetic_trace, wire


def test_projection_retains_original_requests_and_call_result_protocol():
    trace = synthetic_trace()
    snapshot = trace["sessions"][0]["requests"][-1]
    request = snapshot["request"]
    original = deepcopy(request)
    projected, bodies = project(request, snapshot["successful_read_ids"], grace=2)
    assert request == original
    assert len(projected["messages"]) == len(request["messages"])
    changed = []
    for before, after in zip(request["messages"], projected["messages"]):
        if before != after:
            assert {**after, "content": before["content"]} == before
            assert before["role"] == "tool"
            changed.append(after)
    assert len(changed) == len(bodies) == 2
    assert all("call_5" in message["content"] for message in changed)
    retained = next(m for m in projected["messages"] if m.get("tool_call_id") == "call_5")
    assert all(body == retained["content"] for body in bodies)


def test_late_read_matters_only_after_grace_and_other_results_do_not_match():
    trace = synthetic_trace()
    result = benchmark(trace, len, grace=2)
    by_id = {s["id"]: s["requests"] for s in result["sessions"]}
    assert all(r["replacement_instances"] == 0 for r in by_id["single-late-repeat"])
    assert all(r["replacement_instances"] == 0 for r in by_id["changed-partial-and-failed"])
    assert all(r["replacement_instances"] == 0 for r in by_id["read-light"])
    # A deterministic character counter pins accounting independently of BPE.
    summary = result["summary"]
    assert summary["baseline_tokens"] == 535_006
    assert summary["projected_tokens"] == 457_775
    assert summary["net_saved_tokens"] == 77_231
    assert summary["replacement_instances"] == 7
    assert summary["final_net_saved_tokens"] == 22_066
    assert benchmark(synthetic_trace(), len, grace=0)["trace_sha256"] == result["trace_sha256"]
    immediate = benchmark(trace, len, grace=0)
    assert immediate["summary"]["net_saved_tokens"] > result["summary"]["net_saved_tokens"]


@pytest.mark.parametrize("control", [
    "unverified", "duplicate_result", "duplicate_call", "user_boundary", "incomplete_batch",
    "same_batch", "uncorrelated_result",
])
def test_ambiguous_or_unverified_reads_remain_intact(control):
    snapshot = synthetic_trace()["sessions"][1]["requests"][-1]
    request, verified = snapshot["request"], snapshot["successful_read_ids"]
    messages = request["messages"]
    if control == "unverified":
        verified.pop()
    elif control == "duplicate_result":
        messages.append(messages[-1].copy())
    elif control == "duplicate_call":
        messages.append(messages[-2].copy())
    elif control == "user_boundary":
        messages.insert(-2, {"role": "user", "content": "Now check the current file."})
    elif control == "incomplete_batch":
        messages[-2]["tool_calls"].append({"id": "no_result"})
    elif control == "same_batch":
        first_result = messages.pop(3)
        first_call = messages.pop(2)["tool_calls"][0]
        messages[-2]["tool_calls"].append(first_call)
        messages.append(first_result)
    elif control == "uncorrelated_result":
        messages.insert(-1, {"role": "assistant", "content": "No tool result was observed."})
    projected, eligible = project(request, verified, grace=0)
    assert not eligible
    assert wire(projected) == wire(request)


def test_incomplete_later_batch_does_not_mature_a_replacement():
    snapshot = synthetic_trace()["sessions"][1]["requests"][-1]
    request, verified = snapshot["request"], snapshot["successful_read_ids"]
    request["messages"].append({"role": "assistant", "tool_calls": [{"id": "pending"}]})
    _, eligible = project(request, verified, grace=1)
    assert not eligible


def test_grace_boundary_and_prefix_rewrite():
    rows = benchmark(synthetic_trace(), len, grace=2)["sessions"][0]["requests"]
    # The second full read lands at request four. Its first eligible snapshot
    # differs from the previous projection at the original result message.
    assert [row["replacement_instances"] for row in rows[3:6]] == [0, 0, 1]
    assert rows[5]["first_extra_rewrite_message_index"] == 3
    assert rows[6]["first_extra_rewrite_message_index"] is None
    assert rows[8]["first_extra_rewrite_message_index"] == 3


def test_tiny_repeated_body_cannot_increase_request_size():
    snapshot = synthetic_trace()["sessions"][1]["requests"][-1]
    request = snapshot["request"]
    for message in request["messages"]:
        if message.get("tool_call_id") in snapshot["successful_read_ids"]:
            message["content"] = "x"
    projected, bodies = project(request, snapshot["successful_read_ids"], grace=0)
    assert not bodies
    assert wire(projected) == wire(request)


@pytest.mark.parametrize("case", ["mismatch", "no_user", "verifier_failure", "bad_count"])
def test_sdk_projection_keeps_native_messages_when_verification_is_unusable(case):
    from atmem.context_engine.read_deduplication import ReadDeduplication, VerifiedRead

    snapshot = synthetic_trace()["sessions"][1]["requests"][-1]
    normalized = snapshot["request"]["messages"]
    receipts = [
        VerifiedRead.from_result(message["tool_call_id"], {"path": "parser.py"}, message["content"])
        for message in normalized if message.get("tool_call_id") in snapshot["successful_read_ids"]
    ]
    if case == "mismatch":
        receipts[-1] = VerifiedRead.from_result(receipts[-1].call_id, {"path": "parser.py"}, "Other result")
    if case == "no_user":
        normalized = [message for message in normalized if message["role"] != "user"]

    def verify(_runtime, _messages):
        if case == "verifier_failure":
            raise RuntimeError("unavailable verifier")
        return receipts

    def count(text):
        return -1 if case == "bad_count" else len(text)

    assert ReadDeduplication(verify, count, grace=0).project(None, normalized, normalized) is normalized
