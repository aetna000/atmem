"""Measure exact duplicate read eviction on synthetic or normalized request traces."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from atmem.context_engine.read_deduplication import project_read_results, wire

TRACE_FORMAT = "atmem-context-eviction-trace-v1"


def project(request, successful_read_ids, grace, count=len):
    messages, bodies = project_read_results(request["messages"], successful_read_ids, grace, count)
    return {**request, "messages": messages}, bodies


def shared_message_prefix(previous, current):
    for index, (left, right) in enumerate(zip(previous, current)):
        if left != right:
            return index
    return min(len(previous), len(current))


def benchmark(trace, count, grace):
    if trace["format"] != TRACE_FORMAT or not trace["sessions"] or grace < 0:
        raise ValueError("expected a nonempty v1 corpus and nonnegative grace")
    sessions = []
    seen = set()
    for session in trace["sessions"]:
        if session["id"] in seen or not session["requests"]:
            raise ValueError("each session needs a distinct identity and at least one request")
        seen.add(session["id"])
        requests = []
        previous = previous_projected = None
        for index, snapshot in enumerate(session["requests"], 1):
            request = snapshot["request"]
            verified = snapshot["successful_read_ids"]
            if not isinstance(verified, list) or any(not isinstance(item, str) for item in verified):
                raise ValueError("successful_read_ids must be a list of strings")
            projected, bodies = project(request, verified, grace, count)
            baseline = count(wire(request))
            candidate = count(wire(projected))
            if candidate >= baseline:
                candidate, projected, bodies = baseline, request, []
            rewrite_index = None
            if previous is not None:
                original_prefix = shared_message_prefix(previous, request["messages"])
                projected_prefix = shared_message_prefix(previous_projected, projected["messages"])
                if projected_prefix < original_prefix:
                    rewrite_index = projected_prefix
            previous = request["messages"]
            previous_projected = projected["messages"]
            requests.append({
                "request": index, "baseline_tokens": baseline, "projected_tokens": candidate,
                "net_saved_tokens": baseline - candidate, "replacement_instances": len(bodies),
                "candidate_body_tokens": sum(count(wire(body)[1:-1]) for body in bodies),
                "message_tokens": count(wire(request["messages"])),
                "first_extra_rewrite_message_index": rewrite_index,
            })
        sessions.append({"id": session["id"], "requests": requests})
    rows = [row for session in sessions for row in session["requests"]]
    finals = [session["requests"][-1] for session in sessions]
    summary = {key: sum(row[key] for row in rows) for key in (
        "baseline_tokens", "projected_tokens", "net_saved_tokens", "replacement_instances",
    )}
    summary.update(
        requests=len(rows), final_candidate_body_tokens=sum(row["candidate_body_tokens"] for row in finals),
        final_message_tokens=sum(row["message_tokens"] for row in finals),
        final_baseline_request_tokens=sum(row["baseline_tokens"] for row in finals),
        final_net_saved_tokens=sum(row["net_saved_tokens"] for row in finals),
        requests_with_extra_prefix_rewrite=sum(row["first_extra_rewrite_message_index"] is not None for row in rows),
        net_saved_percent=round(100 * summary["net_saved_tokens"] / summary["baseline_tokens"], 2),
    )
    summary["final_candidate_percent"] = round(
        100 * summary["final_candidate_body_tokens"] / summary["final_message_tokens"], 2,
    )
    summary["final_net_saved_percent"] = round(
        100 * summary["final_net_saved_tokens"] / summary["final_baseline_request_tokens"], 2,
    )
    return {
        "format": "atmem-context-eviction-report-v1",
        "corpus": trace["corpus"], "trace_sha256": sha256(wire(trace).encode()).hexdigest(),
        "measurement": "canonical request JSON token estimate", "grace_tool_batches": grace,
        "model_calls": 0, "summary": summary, "sessions": sessions,
    }


def synthetic_trace():
    """Known controls with a neutral payload, and cumulative request snapshots."""
    lines = [f"def parse_field_{i}(value):\n    return str(value).strip().lower()" for i in range(160)]
    file_body = "\n\n".join(lines)

    def scenario(name, reads):
        messages = [
            {"role": "system", "content": "Inspect project files and verify the requested behavior."},
            {"role": "user", "content": "Review the parser and report what you verified."},
        ]
        successful = []
        requests = []

        def snapshot():
            requests.append({"request": {"model": "replay", "messages": messages.copy()},
                             "successful_read_ids": successful.copy()})

        snapshot()
        for index, (tool, args, body, success) in enumerate(reads):
            call_id = f"call_{index}"
            messages.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": call_id, "type": "function", "function": {"name": tool, "arguments": wire(args)}},
            ]})
            messages.append({"role": "tool", "tool_call_id": call_id, "content": body})
            if tool == "read" and success:
                successful.append(call_id)
            snapshot()
        return {"id": name, "requests": requests}

    read = ("read", {"path": "parser.py"}, file_body, True)
    check = ("exec", {"command": "unit check"}, "Checks completed.", True)
    return {"format": TRACE_FORMAT, "corpus": "synthetic-program-reads-v1", "sessions": [
        scenario("repeat-heavy", [read, check, read, check, check, read, check, check, check]),
        scenario("single-late-repeat", [read, check, check, read]),
        scenario("changed-partial-and-failed", [
            read, ("read", {"path": "parser.py"}, file_body.replace("strip", "rstrip", 1), True),
            ("read", {"path": "parser.py", "offset": 1, "limit": 10}, file_body, True),
            ("read", {"path": "parser.py"}, file_body, False), check, check,
        ]),
        scenario("read-light", [check, check, read, check, check]),
    ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, help="Normalized JSON trace. Omit for the bundled synthetic corpus.")
    parser.add_argument("--grace", type=int, default=2, help="Subsequent tool batches before an identical read can replace an older result.")
    parser.add_argument("--encoding", default="o200k_base")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.grace < 0:
        parser.error("--grace must be nonnegative")

    import tiktoken

    encoding = tiktoken.get_encoding(args.encoding)
    try:
        trace = json.loads(args.trace.read_text(encoding="utf-8")) if args.trace else synthetic_trace()
        report = benchmark(trace, lambda text: len(encoding.encode_ordinary(text)), args.grace)
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        parser.error(f"invalid trace: {error}")
    report["tokenizer"] = {"library": "tiktoken", "version": version("tiktoken"), "encoding": encoding.name}
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(result)
        except OSError as error:
            parser.error(f"cannot write report: {error}")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
