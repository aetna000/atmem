"""Evaluator-only qualification diagnostics, never real solver results."""
import argparse
from pathlib import Path
import json
import re

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.grade import qualification
from benchmarks.code_replay.prepare import git


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--interpreter-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("references", nargs="+")
    args = parser.parse_args()
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    for abbreviated in args.references:
        # Revisions supplied by evaluator, never from a model tool invocation.
        reference = git(args.checkout, "rev-parse", "--verify", abbreviated + "^{commit}").decode().strip()
        parent = git(args.checkout, "rev-parse", reference + "^1").decode().strip()
        changed = git(args.checkout, "diff", "--name-only", parent, reference).decode().splitlines()
        tests = tuple(p for p in changed if p.startswith("tests/") and "/typing/" not in p and p.endswith(".py"))
        if not tests:
            print(json.dumps({"reference_commit": reference, "status": "no_changed_behavioral_tests", "selected": False}), flush=True)
            continue
        results = qualification(args.checkout, parent, reference, python=args.python,
                                interpreter_root=args.interpreter_root, test_paths=tests)
        payload = {"parent_commit": parent, "reference_commit": reference, "test_paths": list(tests),
                   "runtime": str(args.python), "interpreter_root": str(args.interpreter_root),
                   "observations": {name: {**r.summary(), "output": r.output.decode(errors="replace")} for name, r in results.items()},
                   "qualification_only": True, "real_solver_run": False}
        retained = evidence.capture(run_id="qualify-" + reference, kind="grader.qualification", payload=payload, principal=principal)
        discriminating = (results["parent"].exit_code == 1 and not results["parent"].environment_error and
                          results["reference"].exit_code == 0 and not results["reference"].environment_error)
        counts = {name: {label: int(value) for value, label in re.findall(r"([0-9]+) (passed|failed|skipped|errors?)", r.output.decode(errors="replace"))}
                  for name, r in results.items()}
        print(json.dumps({"reference_commit": reference, "discriminating_tests": discriminating,
                          "observations": {name: r.summary() for name, r in results.items()}, "counts": counts,
                          "evidence": retained, "selection_status": "chronology_and_scope_review_still_required"}), flush=True)


if __name__ == "__main__":
    main()
