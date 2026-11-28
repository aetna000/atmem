"""Paired native single-reader, fixed-review and adaptive local agent benchmark."""

import argparse
from dataclasses import replace
import json
import re
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from unittest.mock import patch
from hashlib import sha256

from atmem import Memory
from atmem.agent_team import run_agent_team
from atmem.agent_team.local import LocalAgents, MODEL_DIGEST
from atmem.contracts import AuthorityScope, SourceCaptureRequest
from atmem.extract.formation import form_typed_proposals

HERE = Path(__file__).resolve().parents[1] / "specs/057-multi-agent-evidence-routing"
SCOPE = AuthorityScope("pilot", "team", "pilot-workspace")
POLICIES = ("single", "fixed", "adaptive")


def seed(memory, case):
    for i, fact in enumerate(case["facts"]):
        source = f"{case['id']}-source-{i + 1}"
        memory.capture_source(SourceCaptureRequest(source, source, SCOPE, fact))
        proposals = form_typed_proposals(
            fact, scope=SCOPE, source_id=source, formation_id=source,
            observed_at=f"2019-01-{i + 1:02}T10:00:00Z",
        )
        if not proposals:
            raise ValueError(f"Fixture did not form a typed memory: {source}")
        for proposal in proposals:
            if case.get("valid_until"):
                proposal = replace(proposal, unit=replace(proposal.unit, valid_until=case["valid_until"]))
            if case.get("unkeyed"):
                # Two independent, unkeyed live claims deliberately leave a conflict.
                proposal = replace(proposal, fact_key=None)
            outcome = memory.submit_extraction_proposal(proposal, source_text=fact)
            if outcome["review_state"] != "committed":
                raise ValueError(f"Fixture could not commit {source}: {outcome.get('review_state')}")


def grade(case, run):
    actual = (run["answer"] or "").strip().casefold()
    correct = (run["outcome"] == "abstained" if case["answer"] is None else
               run["outcome"] == "answered" and actual == case["answer"].casefold())
    stale = any(re.search(r"(?<!\w)" + re.escape(v.casefold()) + r"(?!\w)", actual)
                for v in case.get("stale", []))
    return {"correct": correct, "stale": stale,
            "correct_abstention": case["answer"] is None and run["outcome"] == "abstained"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=HERE / "cases.json")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    agents = LocalAgents()
    agents.ensure_available()
    rows = []
    with TemporaryDirectory(prefix="atmem-team-benchmark-") as directory:
        for index, case in enumerate(cases):
            source = Path(directory) / f"{case['id']}.db"
            memory = Memory(source, auto_vectors=False, allow_insecure_typed_development=True)
            try:
                seed(memory, case)
            finally:
                memory.close()
            # Identical source IDs, record IDs and generations in all three arms.
            order = POLICIES[index % 3:] + POLICIES[:index % 3]
            for policy in order:
                target = source.with_name(f"{source.stem}-{policy}.db")
                copyfile(source, target)
                memory = Memory(target, auto_vectors=False, allow_insecure_typed_development=True)
                try:
                    typed_rows = []
                    read = memory.store.typed_units_for_records

                    def observed_rows(*args, **kwargs):
                        found = read(*args, **kwargs)
                        typed_rows.extend(row["record_id"] for row in found)
                        return found

                    with patch.object(memory.store, "typed_units_for_records", observed_rows), patch.object(
                        memory.store, "get_protocol_source_by_id", wraps=memory.store.get_protocol_source_by_id
                    ) as source_reads:
                        run = run_agent_team(memory, SCOPE, case["question"], policy=policy, agents=agents)
                    run["typed_rows_read"] = len(typed_rows)
                    run["unique_typed_records_read"] = len(set(typed_rows))
                    run["raw_source_fetches"] = source_reads.call_count
                finally:
                    memory.close()
                score = grade(case, run)
                rows.append({"case_id": case["id"], "grade": score, "run": run})
                print(case["id"], policy, run["outcome"], score["correct"], run["model_calls"], flush=True)
    args.output.write_text(json.dumps({"model_digest": MODEL_DIGEST, "cases_sha256": sha256(args.cases.read_bytes()).hexdigest(), "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
