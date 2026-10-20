"""Freeze an authentic, reduced five-task pilot before any target solving."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

from atmem.evidence import EvidenceScope, EvidenceRole, EvidencePrincipal
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.contracts import TaskManifest, StructureExperienceProtocol
from benchmarks.code_replay.frozen import TASKS, digest_files, grader_tree, solution_tree, recover_report
from benchmarks.code_replay.grade import tree_files, grade_files
from benchmarks.code_replay.prepare import git
from benchmarks.code_replay.select import CHECKS, SelectionCandidate, select_candidates


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkout", "discovery", "output", "evidence-root", "wheel", "python", "interpreter-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("frozen protocol output already exists; do not overwrite")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    discovery = json.loads(args.discovery.read_bytes())
    environment = {"python": str(args.python), "interpreter": str(args.interpreter_root),
                   "version": subprocess.check_output([str(args.python), "--version"], text=True).strip(),
                   "packages": json.loads(subprocess.check_output([str(args.python), "-c",
                       'import importlib.metadata as m,json; print(json.dumps(sorted((str(d.metadata.get("Name","")),d.version) for d in m.distributions())))'], text=True))}
    tasks, reports, qualifications = [], {}, {}
    baseline = {"tests": "entire frozen tests directory", "repeat_reference": 2,
                "environment_exclusion": "test_commands.py::test_other_command_invoke_with_defaults[opt_params12-/tmp] requires forbidden literal /tmp access; identically deselected before target execution",
                "b67832c": "public issue behavior replaces reserved-private-name and unrelated-warning oracle tests; parent info_dict private-name fixture excluded",
                "changes": "only regular src/click/*.py and nested Python implementation files accepted; tests/config changes cannot affect evaluator",
                "hidden_feedback": "never supplied to solver or future memory"}
    for order, definition in enumerate(TASKS, 1):
        task = dict(definition)
        task["reference_commit"] = git(args.checkout, "rev-parse", task["short"] + "^{commit}").decode().strip()
        task["parent_commit"] = git(args.checkout, "rev-parse", task["reference_commit"] + "^1").decode().strip()
        report = recover_report(task)
        observed_at = report["last_edited_at"] or report["report"]["created_at"]
        if datetime.fromisoformat(observed_at.replace("Z", "+00:00")) >= datetime.fromisoformat(task["cutoff"].replace("Z", "+00:00")):
            raise ValueError("no trustworthy pre-solution report: " + task["short"])
        reports[task["short"]] = report
        grader = grader_tree(args.checkout, task)
        outcomes = {}
        for variant in ("parent", "reference", "reference_repeat"):
            revision = task["parent_commit"] if variant == "parent" else task["reference_commit"]
            observed = grade_files(solution_tree(grader, tree_files(args.checkout, revision)), python=args.python,
                                   interpreter_root=args.interpreter_root, test_paths=("tests/",), timeout=180)
            outcomes[variant] = {**observed.summary(), "output": observed.output.decode(errors="replace")}
            print(json.dumps({"task": task["short"], "variant": variant, **observed.summary()}), flush=True)
        retained = evidence.capture(run_id="frozen-qualification-" + task["reference_commit"], kind="grader.frozen_qualification",
                                    principal=principal, payload={"task": task, "report": report, "baseline": baseline, "outcomes": outcomes})
        qualified = (outcomes["parent"]["exit_code"] == 1 and not outcomes["parent"]["environment_error"] and
                     all(outcomes[k]["passed"] for k in ("reference", "reference_repeat")))
        if not qualified:
            raise RuntimeError("full-suite qualification failed; retained " + retained["object_id"])
        row = {"format": TaskManifest.format, "task_id": "click-" + task["short"], "order": order,
               "parent_commit": task["parent_commit"], "reference_commit": task["reference_commit"],
               "issue_version_sha256": digest(report), "requirements_sha256": digest(task["requirements"]),
               "source_sha256": digest_files(tree_files(args.checkout, task["parent_commit"])),
               "environment_sha256": digest(environment), "grader_sha256": digest_files(grader),
               "baseline_policy_sha256": digest(baseline), "license_ref": "click-bsd3-public-reports-private-evaluation",
               "requirements_at": observed_at, "solution_cutoff": task["cutoff"], "parent_fails": True, "reference_passes": True}
        TaskManifest.from_dict(row)
        tasks.append({**task, "manifest": row})
        qualifications[task["reference_commit"]] = retained
    selected = {t["reference_commit"] for t in tasks}
    reasons = {
        0: "Incomplete pre-solution public API requirements: later deprecation/get_help_spec details cannot be inferred from naming comment.",
        1: "Earlier stable implementation e2bddbc authored 2026-09-11 predates retained complete requirement edit; chronology fails.",
        2: "Multi-feature stable merge.", 3: "Multi-feature stable merge.",
        8: "Retained PR report follows first retained solution author time; no older complete report recovered.",
        9: "Refactor with no changed discriminating behavioral tests or pre-solution report.",
        10: "Stream refactor combines private protocol changes and separate fixes; no complete pre-solution single-feature contract recovered.",
        14: "Retained report includes solution snippets after initial PR; no sufficiently earlier independent requirement recovered.",
        19: "Test refactor, not a functional source change.", 20: "Typing-only scope; runtime behavioral discrimination absent.",
        21: "Deprecation policy: no verified pre-solution requirement recovered.",
        22: "Multiple private/public deprecations; no single pre-solution feature contract recovered.",
        23: "PowerShell environment unavailable for executable reference qualification.",
        24: "Wide option flag API/policy rewrite; no complete pre-solution single-feature contract recovered."}
    candidates, review = [], []
    for i, entry in enumerate(discovery["entries"][:26]):
        chosen = entry["reference_commit"] in selected
        reason = "Qualified authentic issue and full-suite reference controls." if chosen else reasons.get(i, entry["change_kind"])
        kind = "functional" if chosen or entry["change_kind"] == "functional_review_required" else entry["change_kind"]
        if i in (2, 3, 10, 22, 24):
            kind = "ambiguous_multi_feature"
        proof = digest({"entry": entry, "reason": reason, "qualification": qualifications.get(entry["reference_commit"])})
        candidates.append(SelectionCandidate.from_dict({"format": SelectionCandidate.format, "commit": entry["reference_commit"],
                          "mainline_parent": entry["parent_commit"], "change_kind": kind,
                          "checks": {name: {"eligible": chosen, "evidence_sha256": proof} for name in CHECKS}}))
        review.append({"commit": entry["reference_commit"], "reason": reason, "selected": chosen})
    ledger = select_candidates(discovery["anchor_commit"], candidates)
    if ledger.to_dict()["selected_commits"] != [t["reference_commit"] for t in tasks]:
        raise ValueError("selection chronology disagrees")
    policy = {"integration": "explicit_benchmark_harness_not_normal_codex_hooks", "sessions": 20,
              "context_order": "memory_then_current_structure_shared_8192_byte_budget",
              "history": "own earlier final reports only; anchor to authenticated post-attempt source; unknown outcome without verification",
              "teacher_forcing": "fresh authentic parent trees, stable lane/worktree path; separate CLI homes",
              "caps": "wall/tool/output enforced; token ceiling audited after turn, not hard provider-side control",
              "result": "all tests pass plus source-only patch policy; retain every failure; no adaptive retry",
              "cost": "subscription account only; incremental billing and quota unknown; no API/GPU spend"}
    wheel = sha256(args.wheel.read_bytes()).hexdigest()
    cli = Path(subprocess.check_output(["which", "codex"], text=True).strip()).resolve()
    config_hash = digest(policy)
    analysis = {"unit": "five-task trajectory", "cold": "task 1 separated", "population_superiority": False,
                "metrics": ["all-tests resolution", "solver_ms", "index_ms", "context_ms", "tokens", "cache", "memory_attrition"],
                "cost_unknown": True, "no_significance_claim": True}
    protocol = StructureExperienceProtocol.from_dict({"format": StructureExperienceProtocol.format,
        "protocol_id": "click-cd-20261017-v2", "anchor_commit": discovery["anchor_commit"], "search_horizon": 100,
        "tasks": [t["manifest"] for t in tasks], "arms": ["C", "D"], "repetitions": 2, "schedule": [["C", "D"], ["D", "C"]],
        "versions": {"atmem": {"artifact_sha256": wheel, "configuration_sha256": config_hash},
                     "agent": {"artifact_sha256": sha256(cli.read_bytes()).hexdigest(), "configuration_sha256": config_hash},
                     "model": {"artifact_sha256": digest("gpt-6-luna-provider-alias-no-immutable-weights"), "configuration_sha256": config_hash},
                     "extractor": {"artifact_sha256": args.image_id.removeprefix("sha256:"), "configuration_sha256": config_hash}},
        "configuration_sha256": config_hash, "hardware_sha256": digest({"machine": platform.machine(), "platform": platform.platform()}),
        "budgets": {"tokens": 500000, "tool_calls": 24, "wall_seconds": 180, "context_bytes": 8192, "cost_microusd": 0},
        "total_cost_microusd": 0, "inference": {"provider_id": "codex-chatgpt-subscription", "endpoint": "https://chatgpt.com",
            "license_review_sha256": digest("BSD-3-Clause Click source; private evaluation of public issue requirements; no public redistribution of reports authorized"),
            "egress_policy_sha256": digest("only permitted parent source, task requirements and authorized context via existing subscription CLI; tools offline")},
        "storage_profile": {"profile_id": "encrypted-atmem-evidence-partial-cli-boundaries", "qualification_sha256": digest(qualifications)},
        "analysis_sha256": digest(analysis)})
    package = {"protocol": protocol.to_dict(), "protocol_sha256": protocol.sha256, "tasks": tasks,
               "ledger": ledger.to_dict(), "review": review, "environment": environment,
               "policy": policy, "baseline": baseline, "analysis": analysis, "image_id": args.image_id,
               "wheel_path": str(args.wheel), "frozen_at": datetime.now(timezone.utc).isoformat()}
    evidence.capture(run_id=protocol.to_dict()["protocol_id"], kind="protocol.frozen", principal=principal, payload=package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(package, stream, indent=2)
    print(json.dumps({"frozen": str(args.output), "protocol_sha256": protocol.sha256, "sessions": 20}), flush=True)


if __name__ == "__main__":
    main()
