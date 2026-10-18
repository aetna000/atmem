"""Reporting/backup for the distinct ten-attempt native/structure control."""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import statistics

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.archive import open_archive
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.control import PROTOCOL_ID


RUN_IDS = [f"click-ac-v3q-{arm}-t{order}" for order in range(1, 6) for arm in "ac"]


def terminal_rows(events):
    rows = []
    for run_id in RUN_IDS:
        values = [e["envelope"]["payload"]["result"] for e in events[run_id]
                  if e["envelope"]["event_type"] == "trial.completed"]
        if len(values) != 1 or values[0]["run_id"] != run_id:
            raise ValueError("missing or duplicate completed attempt: " + run_id)
        rows.append(values[0])
    return rows


def summarize(rows):
    result = {}
    for arm in "AC":
        selected = [r for r in rows if r["arm"] == arm]
        if len(selected) != 5 or sorted(r["task_order"] for r in selected) != list(range(1, 6)):
            raise ValueError("exactly five distinct task results per arm required")
        result[arm] = {"passed": sum(r["passed"] for r in selected),
            "functional_pass": sum(r["functional_pass"] for r in selected),
            "infra_invalid": sum(bool(r["infra_invalid"]) for r in selected),
            "solver_median_s": statistics.median(r["stage_ms"]["solver"] for r in selected) / 1000,
            "setup_median_s": statistics.median(r["stage_ms"]["setup"] for r in selected) / 1000,
            "index_median_s": statistics.median(r["stage_ms"]["index"] for r in selected) / 1000,
            "context_median_s": statistics.median(r["stage_ms"]["retrieval"] for r in selected) / 1000,
            "measured_path_median_s": statistics.median(sum(v for k, v in r["stage_ms"].items() if k != "grading") for r in selected) / 1000,
            "tool_calls": sum(r["tool_calls"] for r in selected),
            "context_bytes": sum(r["context_bytes"] for r in selected),
            "usage_receipts": sum(r["tokens"]["input_tokens"] is not None for r in selected)}
        for key in ("input_tokens", "output_tokens", "cached_tokens"):
            values = [r["tokens"][key] for r in selected]
            result[arm][key] = sum(values) if all(v is not None for v in values) else None
            result[arm]["observed_" + key] = sum(v for v in values if v is not None)
    return result


def markdown(rows, package, protocol_sha):
    summary = summarize(rows)
    lines = ["# Click: no memory versus current structural context", "",
        "Fresh matched follow-up: five authentic historical tasks, one A/C pair each. Experience disabled in both.",
        "Installed local preview (wheel metadata 2.3.8), not the public stable 2.3.8 artifact. Explicit benchmark integration, not normal Codex hooks.",
        "", "| Measure | No structure/experience (A) | Structure only (C) |", "| --- | ---: | ---: |"]
    for label, key in (("All-test and run-budget passes / 5", "passed"), ("Functional full-suite passes / 5", "functional_pass"),
            ("Infrastructure-invalid attempts", "infra_invalid"), ("Median solver seconds", "solver_median_s"),
            ("Median setup seconds", "setup_median_s"), ("Median indexing seconds", "index_median_s"),
            ("Median context-planning seconds", "context_median_s"),
            ("Median measured path seconds (setup + index + context + solver)", "measured_path_median_s"),
            ("Tool calls, total", "tool_calls"), ("Additional context bytes, total", "context_bytes"),
            ("Completed usage receipts / 5", "usage_receipts"), ("Total input tokens (includes cached)", "input_tokens"),
            ("Cached input tokens", "cached_tokens"), ("Total output tokens", "output_tokens")):
        values = [summary[a][key] for a in "AC"]
        lines.append("| " + label + " | " + " | ".join("unknown" if v is None else str(round(v, 2)) if isinstance(v, float) else str(v) for v in values) + " |")
    lines += ["", "Measured path excludes protected-evidence I/O and grading; it is not complete request wall time. Each C snapshot is cold-indexed in a fresh database, not an amortized warm-service estimate.",
        "Usage missing after a killed attempt is unknown, never zero. Cached tokens are a subset of input. Billing and remaining subscription quota are unknown; no API/GPU dispatch.",
        "", "| Task | A result | C result | A solver s | C solver s | C context bytes |", "| --- | --- | --- | ---: | ---: | ---: |"]
    paired = {"A_only": 0, "C_only": 0, "both_pass": 0, "neither_pass": 0}
    for order in range(1, 6):
        pair = {r["arm"]: r for r in rows if r["task_order"] == order}
        a, c = pair["A"], pair["C"]
        paired["both_pass" if a["passed"] and c["passed"] else "A_only" if a["passed"] else "C_only" if c["passed"] else "neither_pass"] += 1
        lines.append(f"| {a['task']} | {a['reason']} | {c['reason']} | {a['stage_ms']['solver']/1000:.2f} | {c['stage_ms']['solver']/1000:.2f} | {c['context_bytes']} |")
    lines += ["", "Paired all-budget results: " + ", ".join(f"{k}={v}" for k, v in paired.items()) + ".", "",
        "## Failures and interpretation", ""]
    for row in rows:
        if not row["passed"]:
            lines.append(f"- {row['run_id']}: {row['reason']}; functional pass={row['functional_pass']}; grader summary={json.dumps(row['grade_summary'], sort_keys=True)}; patch violations={row['patch_violations']}.")
    lines += ["", "The comparison measures this fixed structural context pack versus native exploration. Both arms have ordinary source/search/Git/test tools; A has no AtMem context or memory tools. No prior experience reaches either arm.",
        "The same five targets were inspected in the earlier C/D pilot. This follow-up uses corrected native Git/config isolation and fresh 2 GiB scratch in both arms; old results are not pooled or treated as matched controls.",
        "AC/CA/AC/CA/AC partially alternates order; it does not fully balance position or provider drift. Five public tasks with one pair each cannot establish general superiority or significance. Public pretraining familiarity remains possible.",
        "Model: subscription gpt-6-luna alias, low effort; CLI 0.162.1. The alias is not an immutable model-weight pin. Caps: 180s, 24 tool calls, 8192 extra context bytes, 500000 tokens audited after completion rather than provider-enforced. All attempts retained; no adaptive solve retries.",
        "Exact declared prompts, contexts, patches, CLI events and hidden grades are retained in protected evidence. These are not independently observed full system/model inputs or a complete Agent Black Box.",
        "", "Protocol SHA-256: `" + protocol_sha + "`.",
        "Frozen manifest: `/Volumes/MEM/AtMem-Code-Replay-20261017/click-ac-frozen-v3-qualified.json`.",
        "Preflight attrition: the initial v3 package stopped before any solver dispatch because Xcode Git was outside the allocator's Command Line Tools-only allowlist. That failure and original manifest are retained; the qualified package explicitly permits the tested native Xcode Git binary. No model attempt was retried.", ""]
    return "\n".join(lines)


def archive_all(vault, principal, events, package, archive_root, key_root, *, protocol_id=PROTOCOL_ID, run_ids=RUN_IDS):
    if key_root.resolve().is_relative_to(Path("/Volumes")):
        raise ValueError("private keys must remain internal")
    key_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    public, secret = generate_recipient_keypair()
    sign_public, sign_secret = generate_signing_keypair()
    for name, value in (("recipient.public", public), ("recipient.secret", secret), ("signing.public", sign_public), ("signing.secret", sign_secret)):
        descriptor = os.open(key_root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
    wheel = Path(package["wheel_path"])
    vault.capture(run_id=protocol_id, kind="harness.source_snapshot", principal=principal,
        payload={"files_base64": {p.name: base64.b64encode(p.read_bytes()).decode() for p in sorted(Path(__file__).parent.glob("*.py"))},
                 "wheel_base64": base64.b64encode(wheel.read_bytes()).decode(),
                 "wheel_sha256": sha256(wheel.read_bytes()).hexdigest(), "assurance": "post_run_retention_prefreeze_code_hashes_in_protocol"})
    initial_dispatches = sum(e["envelope"]["event_type"] == "trial.started"
        for order in range(1, 6) for arm in "ac"
        for e in vault.inspect(principal, f"click-ac-v3-{arm}-t{order}"))
    if initial_dispatches:
        raise ValueError("initial preflight unexpectedly contains solver dispatches")
    if protocol_id == PROTOCOL_ID:
        vault.capture(run_id=PROTOCOL_ID, kind="preflight.attrition", principal=principal,
        payload={"initial_protocol_events": vault.inspect(principal, "click-ac-20261017-v3"),
                 "initial_manifest": json.loads((archive_root.parent / "click-ac-frozen-v3.json").read_bytes()),
                 "solver_dispatches_before_correction": initial_dispatches})
    archive_root.mkdir(parents=True, exist_ok=False)
    for run_id in [protocol_id, *run_ids]:
        bundle = vault.encrypted_archive(principal, run_id, recipient_public_key=public,
            signing_public_key=sign_public, signing_secret_key=sign_secret)
        restored = json.loads(open_archive(bundle, run_id=run_id, recipient_secret_key=secret, trusted_signing_public_key=sign_public))
        if restored != vault.inspect(principal, run_id):
            raise ValueError("archive round-trip mismatch")
        with (archive_root / (run_id + ".encrypted.json")).open("x") as stream:
            json.dump(bundle, stream, separators=(",", ":"))
    print(json.dumps({"archives_verified": len(run_ids) + 1, "archive_root": str(archive_root)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--key-root", type=Path)
    parser.add_argument("--recover-only", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    package = json.loads(args.frozen.read_bytes())
    from benchmarks.code_replay.freeze import digest
    if args.recover_only:
        if not args.archive_root or not args.key_root:
            parser.error("archive and key roots required")
        events = {}
        for run_id in [PROTOCOL_ID, *RUN_IDS]:
            bundle = json.loads((args.archive_root / (run_id + ".encrypted.json")).read_bytes())
            events[run_id] = json.loads(open_archive(bundle, run_id=run_id,
                recipient_secret_key=(args.key_root / "recipient.secret").read_bytes(),
                trusted_signing_public_key=(args.key_root / "signing.public").read_bytes()))
        print(json.dumps({"fresh_process_recovered_events": sum(map(len, events.values())), "terminal_trials": len(terminal_rows(events))}))
    else:
        if not args.evidence_root:
            parser.error("evidence root required")
        scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
        principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
        vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
        events = {run_id: vault.inspect(principal, run_id) for run_id in RUN_IDS}
        terminal_rows(events)  # Do not publish partial, outcome-dependent denominators.
        if args.archive_root:
            if args.key_root is None:
                parser.error("internal key root required")
            archive_all(vault, principal, events, package, args.archive_root, args.key_root)
    rows = terminal_rows(events)
    if args.json_summary:
        print(json.dumps({"summary": summarize(rows), "rows": rows}, sort_keys=True))
    else:
        print(markdown(rows, package, digest(package)))


if __name__ == "__main__":
    main()
