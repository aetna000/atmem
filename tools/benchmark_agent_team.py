"""Paired native single-reader, fixed-review and adaptive local agent benchmark."""

import argparse
from dataclasses import replace
import json
import re
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

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
    args = parser.parse_args()
    cases = json.loads((HERE / "cases.json").read_text())
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
                    run = run_agent_team(memory, SCOPE, case["question"], policy=policy, agents=agents)
                finally:
                    memory.close()
                score = grade(case, run)
                rows.append({"case_id": case["id"], "grade": score, "run": run})
                print(case["id"], policy, run["outcome"], score["correct"], run["model_calls"], flush=True)
    args.output.write_text(json.dumps({"model_digest": MODEL_DIGEST, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
