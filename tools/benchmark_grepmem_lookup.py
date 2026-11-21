"""Compare the pinned upstream GrepMem lookup with a saved AtMem holdout report."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from time import perf_counter_ns

from atmem.benchmark.exact_history import fixture_digest, make_fixture, score, summarize

GREPMEM_COMMIT = "b7e3744c2f7489feac4060b379be6936960dc7bd"
GREP_SOURCE_SHA256 = "4076e7849bc71f8e83cc3f4fffcce4b603fcdd6c4647fb1d8fd75c4e26533c92"


def compare(atmem_report: Path) -> dict:
    from agents import common

    source_hash = sha256(Path(common.__file__).read_bytes()).hexdigest()
    if source_hash != GREP_SOURCE_SHA256:
        raise ValueError(f"expected GrepMem lookup code from {GREPMEM_COMMIT}")

    baseline = json.loads(atmem_report.read_text(encoding="utf-8"))
    history, cases = make_fixture(baseline["split"])
    if fixture_digest(history, cases) != baseline["fixture_sha256"]:
        raise ValueError("AtMem report and test fixture do not match")

    budget = baseline["output_budget_bytes"]
    common.GREP_CHARS = budget
    entries = [f"[turn {index} tool observation]\n{line.text}"
               for index, line in enumerate(history, start=1) if not line.foreign]
    rows = []
    for case in cases:
        started = perf_counter_ns()
        reply = common.grep_history(entries, re.escape(case.literal), context_lines=0)
        elapsed = perf_counter_ns() - started
        output_size = len(reply.encode())
        if output_size > budget or reply.startswith("Error:"):
            raise RuntimeError(f"GrepMem exceeded its output ceiling or failed on {case.id}")
        matched = not reply.startswith("No matches for ")
        available = case.expected is not None and any(case.expected in entry for entry in entries)
        row = score(case, reply if matched else "", source_available=available,
                    status="matched" if matched else "no_match", elapsed_ns=elapsed)
        row["bytes"] = output_size
        rows.append(row)

    return {
        "format": "atmem-grepmem-lookup-comparison-v1",
        "classification": "synthetic_evidence_delivery",
        "grepmem_commit": GREPMEM_COMMIT, "grepmem_common_sha256": source_hash,
        "fixture_sha256": baseline["fixture_sha256"], "atmem_report": atmem_report.name,
        "model_calls": 0, "output_budget_bytes": budget,
        "query_source": "Question-visible anchor escaped as a literal regex",
        "grep_context_lines": 0, "grep_wire_bytes_include_headers_and_no_match_messages": True,
        "summary": summarize(rows), "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("atmem_report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = compare(args.atmem_report)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(output, file, indent=2, sort_keys=True)
        file.write("\n")


if __name__ == "__main__":
    main()
