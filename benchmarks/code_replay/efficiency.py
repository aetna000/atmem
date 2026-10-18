"""Bounded, frozen efficiency cohorts. No automatic target retries or paid API."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.archive import open_archive
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.control import freeze_control, execute, SCHEDULE, prompt_for
from benchmarks.code_replay.control_report import summarize, archive_all
from benchmarks.code_replay.freeze import digest


FORMAT = "atmem-code-structural-efficiency-cohort-v1"


def validate(package, expected):
    if digest(package) != expected or package["format"] != FORMAT or package["schedule"] != SCHEDULE:
        raise ValueError("efficiency freeze binding failed")
    if package["experience"] is not False or len(package["tasks"]) != 5:
        raise ValueError("five matched pairs without experience required")
    if not re.fullmatch(r"efficiency-(c[123]|confirm|p[23456789]c1|p[23456789]confirm|p1[01](?:c1|confirm)|p5c1r1)-20261017", package["cohort_id"]):
        raise ValueError("outside bounded cohort inventory")
    for phase in ("p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10"):
        if package["run_prefix"].startswith("efficiency-" + phase) and package.get("localization_qualification") != f"implementation-localization-{phase}-logging":
            raise ValueError("mandatory installed localization qualification missing")
    if package["run_prefix"].startswith("efficiency-p6") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("host_qualification") != "progressive-host-p6" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("focused source contract mandatory")
    if package["run_prefix"].startswith("efficiency-p7") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("host_qualification") != "progressive-host-p7" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("compact navigation focused source contract mandatory")
    if package["run_prefix"].startswith("efficiency-p8") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("host_qualification") != "progressive-host-p8" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("budgeted usage focused source contract mandatory")
    if package["run_prefix"].startswith("efficiency-p9") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("host_qualification") != "progressive-host-p9" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("joint budget focused source contract mandatory")
    if package["run_prefix"].startswith("efficiency-p10") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("host_qualification") != "progressive-host-p10" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("covered navigation focused source contract mandatory")
    if package["run_prefix"].startswith("efficiency-p11") and (package.get("delivery_mode") != "focused_progressive" or
        package.get("initial_context_bytes") != 4096 or package.get("required_initial_source") is not True or
        package.get("localization_qualification") != "implementation-localization-p11r1-logging" or
        package.get("host_qualification") != "progressive-host-p11" or package["budgets"]["context_bytes"] != 4096):
        raise ValueError("producer-linked usage focused source qualification mandatory")
    if package["run_prefix"].startswith("efficiency-p5") and (package.get("delivery_mode") != "progressive" or package.get("required_mcp_source") is not True):
        raise ValueError("progressive delivery/source gate mandatory")
    if package["run_prefix"].startswith("efficiency-p5"):
        host = "progressive-host-p5" if package["run_prefix"] == "efficiency-p5c1" else "progressive-host-p5r1"
        if package.get("host_qualification") != host:
            raise ValueError("exact host diagnostic binding required")
    for name, value in package["code_sha256"].items():
        if sha256((Path(__file__).parent / name).read_bytes()).hexdigest() != value:
            raise ValueError("frozen harness changed: " + name)
    for name, value in package["runtime_sha256"].items():
        if sha256(Path(name).read_bytes()).hexdigest() != value:
            raise ValueError("frozen runtime changed")


def metrics(rows, *, required_passes=0, required_mcp_source=False, required_initial_source=False):
    summary = summarize(rows)
    a, c = summary["A"], summary["C"]
    saving = None if not a["input_tokens"] or c["input_tokens"] is None else 1 - c["input_tokens"] / a["input_tokens"]
    quality = c["functional_pass"] >= max(a["functional_pass"], required_passes)
    capability = not required_mcp_source or all(r.get("mcp_source_observed") is True for r in rows if r["arm"] == "C")
    if required_initial_source:
        capability = capability and all(r.get("atmem_source_submitted") is True for r in rows if r["arm"] == "C")
    quality = quality and capability
    known = a["input_tokens"] is not None and c["input_tokens"] is not None
    return {"summary": summary, "input_token_saving": saving, "quality_gate": quality, "capability_gate": capability,
            "target_50": quality and known and c["input_tokens"] * 2 <= a["input_tokens"],
            "fallback_20": quality and known and c["input_tokens"] * 5 <= a["input_tokens"] * 4,
            "classification": "cohort_observation_not_general_user_guarantee", "rows": rows}


def efficient_prompt(task, python, context):
    return prompt_for(task, python, context) + ("Use the configured workspace-local TMPDIR for tests; do not override it or create additional scratch trees. "
            "Temporary symlinks outside the configured scratch area violate the patch policy.\n")


def focused_prompt(task, python, context):
    return efficient_prompt(task, python, context) + ("Use any supplied current-source excerpts as a starting point; avoid rereading identical complete sections. "
        "If code_context is available, it can retrieve missing related implementations in one focused query. "
        "Inspect omitted or changed source with available tools and verify behavior with tests.\n")


def implementation_present(context):
    if not re.search(r"(?m)^\d+:\s+(?:async )?def\s+\w+\s*\([^\n]*\).*:\s*\n\d+:\s+\S", context):
        raise ValueError("structural pack lacks Python implementation evidence; headings are insufficient")


def require_localization(args, package):
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    events = vault.inspect(principal, package["localization_qualification"])
    observations = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == "localization.qualified"]
    qualified = [o for o in observations if o["wheel_sha256"] == package["versions"]["atmem"]["artifact_sha256"]]
    if not qualified or any(not qualified[-1].get(k) for k in ("passed", "stale_context_withheld", "stale_submission_refused")):
        raise ValueError("installed disjoint localization/source-currentness qualification absent")
    if len(qualified[-1]["receipts"]) != 3 or not all(r["localized"] for r in qualified[-1]["receipts"]):
        raise ValueError("all three real-source implementation controls must pass")
    if package["run_prefix"].startswith(("efficiency-p3", "efficiency-p4", "efficiency-p5", "efficiency-p6", "efficiency-p7", "efficiency-p8", "efficiency-p9", "efficiency-p10", "efficiency-p11")) and not all(r.get("call_context_localized") for r in qualified[-1]["receipts"]):
        raise ValueError("call-context qualification missing")
    if package["run_prefix"].startswith(("efficiency-p4", "efficiency-p5", "efficiency-p6", "efficiency-p7", "efficiency-p8", "efficiency-p9", "efficiency-p10", "efficiency-p11")) and not all(r.get("usage_localized") for r in qualified[-1]["receipts"]):
        raise ValueError("existing-test source qualification missing")
    if package["run_prefix"].startswith(("efficiency-p5", "efficiency-p6", "efficiency-p7", "efficiency-p8", "efficiency-p9", "efficiency-p10", "efficiency-p11")):
        progressive = qualified[-1].get("progressive") or {}
        if not all(progressive.get(k, {}).get("passed") for k in ("current", "stale")):
            raise ValueError("actual installed progressive transport qualification absent")
        if package["run_prefix"].startswith(("efficiency-p6", "efficiency-p7", "efficiency-p8", "efficiency-p9", "efficiency-p10", "efficiency-p11")) and not progressive["current"].get("argument_error_verified"):
            raise ValueError("safe argument feedback qualification absent")
        host = vault.inspect(principal, package["host_qualification"])
        configs = [e["envelope"]["payload"] for e in host if e["envelope"]["event_type"] == "mcp.host_configuration"]
        proofs = [e["envelope"]["payload"] for e in host if e["envelope"]["event_type"] == "mcp.host_semantic_qualified"]
        if not configs or configs[-1]["wheel_sha256"] != package["versions"]["atmem"]["artifact_sha256"] or not proofs or not proofs[-1].get("passed"):
            raise ValueError("actual candidate host semantic qualification absent")
        from benchmarks.code_replay.progressive import require_qualified_configuration
        require_qualified_configuration(host)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "run", "inspect", "recover"))
    p.add_argument("--frozen", type=Path, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--wheel", type=Path)
    p.add_argument("--cohort", choices=("c1", "c2", "c3", "confirm", "p2c1", "p2confirm", "p3c1", "p3confirm", "p4c1", "p4confirm", "p5c1", "p5confirm", "p5c1r1", "p6c1", "p6confirm", "p7c1", "p7confirm", "p8c1", "p8confirm", "p9c1", "p9confirm", "p10c1", "p10confirm", "p11c1", "p11confirm"))
    p.add_argument("--task-package", type=Path)
    for name in ("checkout", "ram-root", "auth-file", "evidence-root", "state-root", "archive-root", "key-root"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--freeze-sha256")
    p.add_argument("--subscription-only", action="store_true")
    args = p.parse_args()
    if args.action == "freeze":
        if not args.source or not args.wheel or not args.cohort:
            p.error("source task package, exact wheel and bounded cohort required")
        package = freeze_control(json.loads(args.source.read_bytes()))
        package.update(format=FORMAT, cohort_id=f"efficiency-{args.cohort}-20261017",
                       run_prefix=f"efficiency-{args.cohort}", wheel_path=str(args.wheel),
                       classification="new_task_confirmation" if args.cohort.endswith("confirm") else "reused_task_tuning")
        package["required_functional_passes"] = 0 if args.cohort.endswith("confirm") else 5
        package["common_prompt_revision"] = "explicit-existing-scratch-policy-v1"
        package["versions"]["atmem"]["artifact_sha256"] = sha256(args.wheel.read_bytes()).hexdigest()
        package["code_sha256"]["efficiency.py"] = sha256(Path(__file__).read_bytes()).hexdigest()
        if args.cohort.startswith(("p7", "p8", "p9", "p10", "p11")):
            package["code_sha256"]["usage_audit.py"] = sha256(Path(__file__).with_name("usage_audit.py").read_bytes()).hexdigest()
        if args.cohort.startswith(("p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11")):
            package["code_sha256"]["localization_probe.py"] = sha256(Path(__file__).with_name("localization_probe.py").read_bytes()).hexdigest()
            phase = re.match(r"p\d+", args.cohort)[0]
            package["localization_qualification"] = f"implementation-localization-{phase}-logging"
            if phase == "p11":
                package["localization_qualification"] = "implementation-localization-p11r1-logging"
        if args.cohort.startswith(("p5", "p6", "p7", "p8", "p9", "p10", "p11")):
            package.update(delivery_mode="progressive", required_mcp_source=True,
                host_qualification="progressive-host-p5" if args.cohort == "p5c1" else "progressive-host-p5r1",
                progressive_runtime={"python": str(Path(sys.executable).absolute()), "dependencies": [p for p in sys.path if p.endswith("site-packages")]})
            for name in ("progressive.py", "progressive_host.py", "progressive_audit.py", "progressive_probe.py"):
                package["code_sha256"][name] = sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        if args.cohort.startswith(("p6", "p7", "p8", "p9", "p10", "p11")):
            package.update(delivery_mode="focused_progressive", required_mcp_source=False, required_initial_source=True,
                           initial_context_bytes=4096, host_qualification="progressive-host-p6",
                           common_prompt_revision="focused-source-use-identical-both-arms-v1")
            if args.cohort.startswith("p7"):
                package["host_qualification"] = "progressive-host-p7"
            if args.cohort.startswith("p8"):
                package["host_qualification"] = "progressive-host-p8"
            if args.cohort.startswith("p9"):
                package["host_qualification"] = "progressive-host-p9"
            if args.cohort.startswith("p10"):
                package["host_qualification"] = "progressive-host-p10"
            if args.cohort.startswith("p11"):
                package["host_qualification"] = "progressive-host-p11"
            package["budgets"]["context_bytes"] = 4096
        if args.task_package:
            tasks = json.loads(args.task_package.read_bytes())
            from benchmarks.code_replay.contracts import TaskManifest
            if len(tasks["tasks"]) != 5:
                raise ValueError("five qualified tasks required")
            for task in tasks["tasks"]:
                TaskManifest.from_dict(task["manifest"])
            package["tasks"] = tasks["tasks"]
            package["task_package_sha256"] = digest(tasks)
        elif args.cohort.endswith("confirm"):
            raise ValueError("new task package required for confirmation")
        with args.frozen.open("x") as stream:
            json.dump(package, stream, sort_keys=True, indent=2)
        print(json.dumps({"protocol_sha256": digest(package), "cohort": package["cohort_id"]}))
        return
    package = json.loads(args.frozen.read_bytes())
    if args.action == "run":
        if not args.subscription_only or any(getattr(args, name) is None for name in ("checkout", "ram_root", "auth_file", "evidence_root", "state_root", "freeze_sha256")):
            p.error("all isolated paths, freeze hash and explicit subscription authorization required")
        validate(package, args.freeze_sha256)
        if package.get("localization_qualification"):
            require_localization(args, package)
        execute(args, package, validate_package=validate,
                prompt_factory=focused_prompt if package.get("delivery_mode") == "focused_progressive" else efficient_prompt,
                structural_check=None if package.get("delivery_mode") == "progressive" else implementation_present if package.get("localization_qualification") else None)
        return
    ids = [f"{package['run_prefix']}-{arm}-t{order}" for order in range(1, 6) for arm in "ac"]
    events = {}
    if args.action == "recover":
        for run_id in [package["cohort_id"], *ids]:
            events[run_id] = json.loads(open_archive(json.loads((args.archive_root / (run_id + ".encrypted.json")).read_bytes()),
                run_id=run_id, recipient_secret_key=(args.key_root / "recipient.secret").read_bytes(),
                trusted_signing_public_key=(args.key_root / "signing.public").read_bytes()))
    else:
        scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
        principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
        vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
        events = {run_id: vault.inspect(principal, run_id) for run_id in ids}
    rows = []
    for run_id in ids:
        terminal = [e["envelope"]["payload"]["result"] for e in events[run_id] if e["envelope"]["event_type"] == "trial.completed"]
        if len(terminal) != 1 or terminal[0]["run_id"] != run_id:
            raise ValueError("incomplete cohort; no partial-denominator selection")
        rows.extend(terminal)
    if args.action == "inspect" and args.archive_root:
        archive_all(vault, principal, events, package, args.archive_root, args.key_root,
                    protocol_id=package["cohort_id"], run_ids=ids)
    print(json.dumps(metrics(rows, required_passes=package.get("required_functional_passes", 0),
                             required_mcp_source=package.get("required_mcp_source", False),
                             required_initial_source=package.get("required_initial_source", False)), sort_keys=True))


if __name__ == "__main__":
    main()
