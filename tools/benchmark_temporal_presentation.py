"""Run a paired reader comparison on native exact-history temporal contexts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess

from atmem.benchmark.exact_history import OUTPUT_BYTES, SPLIT_SEEDS, make_fixture, run_benchmark


PROMPT = "Use the evidence to answer the question. Return only the routing code.\n\nEvidence\n{context}\n\n{question}"
UPDATE_TIME = re.compile(r"^At ((?:[01]\d|2[0-3]):[0-5]\d) ")
ARMS = ("native_order", "newest_first")


def newest_first(context: str) -> str:
    # Each delivered paragraph is one fixture span. HH:MM is on the same day.
    def time_key(span: str) -> str:
        match = UPDATE_TIME.match(span)
        return match[1] if match else ""

    return "\n\n".join(sorted(context.split("\n\n"), key=time_key, reverse=True))


def compare(retrieval: dict, read_answer) -> dict:
    _, cases = make_fixture(retrieval["split"])
    cases_by_id = {case.id: case for case in cases}
    rows = []
    budget = retrieval["output_budget_bytes"]
    for native in retrieval["arms"]["atmem_v3"]["cases"]:
        if native["cohort"] != "latest":
            continue
        case = cases_by_id[native["id"]]
        context = native["context"]
        if len(context.encode()) != native["bytes"] or native["bytes"] > budget:
            raise ValueError(f"Invalid delivered context size for {case.id}")
        arms = {}
        # Alternate the first condition across cases. Each read starts a fresh session.
        for arm in (reversed(ARMS) if len(rows) % 2 else ARMS):
            presented = context if arm == "native_order" else newest_first(context)
            reply = read_answer(PROMPT.format(context=presented, question=case.question)).strip()
            selection = "other"
            if reply == case.expected:
                selection = "current"
            elif reply == case.outdated:
                selection = "stale"
            arms[arm] = {"context": presented, "context_bytes": len(presented.encode()),
                         "answer": reply, "selection": selection}
        rows.append({"id": case.id, "question": case.question, "expected": case.expected, "outdated": case.outdated,
                     "retrieval_passed": native["passed"], "retrieval_status": native["status"],
                     "retrieval_error": native["error"], "stale_delivered": native["stale_delivered"], "arms": arms})

    summary = {}
    for arm in ARMS:
        selections = [row["arms"][arm]["selection"] for row in rows]
        summary[arm] = {key: selections.count(key) for key in ("current", "stale", "other")}
        summary[arm]["stale_on_retrieval_pass"] = sum(
            row["retrieval_passed"] and row["arms"][arm]["selection"] == "stale" for row in rows
        )
    transitions = {}
    for row in rows:
        pair = "->".join(row["arms"][arm]["selection"] for arm in ARMS)
        transitions[pair] = transitions.get(pair, 0) + 1
    return {
        "format": "atmem-temporal-presentation-v1", "split": retrieval["split"],
        "fixture_sha256": retrieval["fixture_sha256"], "output_budget_bytes": budget,
        "native_context_service_sha256": retrieval["native_context_service_sha256"],
        "prompt_template": PROMPT, "reader_calls": 2 * len(rows), "cases": rows,
        "retrieval_passes": sum(row["retrieval_passed"] for row in rows),
        "summary": summary, "native_to_newest_first": transitions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(SPLIT_SEEDS), default="development")
    parser.add_argument("--output-bytes", type=int, choices=(512, OUTPUT_BYTES), default=512)
    parser.add_argument("--reader", type=Path, required=True, help="Single-turn executable reading a prompt on stdin.")
    parser.add_argument("--model", required=True, help="Reader model and decoding settings for the report.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output path")
    reader = args.reader.resolve(strict=True)

    def read_answer(prompt: str) -> str:
        return subprocess.run([reader], input=prompt, text=True, stdout=subprocess.PIPE,
                              check=True, timeout=120).stdout

    retrieval = run_benchmark(args.split, output_bytes=args.output_bytes, include_temporal_context=True)
    report = compare(retrieval, read_answer)
    report.update(model=args.model, reader_sha256=sha256(reader.read_bytes()).hexdigest(), platform=platform.platform())
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
