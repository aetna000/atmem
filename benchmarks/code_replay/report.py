"""Authorized protected-evidence reporting; never reads solver homes/logs."""
import argparse
import base64
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import statistics

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair, decrypt_export
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.archive import open_archive


def summarize(rows, expected_per_arm=10):
    result = {}
    for arm in ("C", "D"):
        selected = [r for r in rows if r["run"]["arm"] == arm]
        measurements = [r["result"]["measurements"] for r in selected]
        states = Counter(r["result"]["status"] for r in selected)
        def total(key):
            values = [m[key] for m in measurements]
            return sum(values) if values and all(v is not None for v in values) else None
        solver = [r["result"]["stage_ms"]["solver"] for r in selected]
        overhead = [sum(v for k, v in r["result"]["stage_ms"].items() if k not in ("solver", "grading") and v is not None) for r in selected]
        def p95(values):
            return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None
        result[arm] = {"expected": expected_per_arm, "completed": len(selected), "passed": states["passed"],
            "failed": states["failed"], "infra_invalid": states["infra_invalid"], "missing": expected_per_arm - len(selected),
            "input_tokens": total("input_tokens"), "cached_tokens": total("cached_tokens"), "output_tokens": total("output_tokens"),
            "usage_receipts": sum(m["input_tokens"] is not None for m in measurements),
            "observed_input_subtotal": sum(m["input_tokens"] or 0 for m in measurements),
            "observed_output_subtotal": sum(m["output_tokens"] or 0 for m in measurements),
            "solver_median_ms": statistics.median(solver) if solver else None,
            "solver_p95_ms": p95(solver),
            "overhead_median_ms": statistics.median(overhead) if overhead else None,
            "context_median_ms": statistics.median(r["result"]["stage_ms"]["retrieval"] for r in selected) if selected else None,
            "context_p95_ms": p95([r["result"]["stage_ms"]["retrieval"] for r in selected]),
            "end_to_end_total_ms": total("elapsed_ms"), "billing_cost": None,
            "context_bytes_total": total("context_bytes"), "memory_deliveries": sum(len(r["result"]["memory_ids"]) for r in selected),
            "candidates": sum(r["formation"]["candidates"] for r in selected),
            "admitted": sum(r["formation"]["admitted"] for r in selected)}
    return result


def markdown(rows, summary, protocol_sha256):
    lines = ["# Click structure versus structure + experience", "",
             "Reduced historical pilot; installed local preview, not a published release or general superiority result.",
             "Benchmark integration through product services, not normal Codex automatic hooks. Two five-task trajectories per arm.",
             "", "| Measure | Structure (C) | Structure + experience (D) |", "| --- | ---: | ---: |"]
    for label, key in (("Planned attempts", "expected"), ("Completed attempts", "completed"), ("All-check passes", "passed"),
                       ("Failed attempts", "failed"), ("Infrastructure-invalid", "infra_invalid"), ("Missing attempts", "missing"),
                       ("Median solver seconds", "solver_median_ms"), ("Sample p95 solver seconds", "solver_p95_ms"),
                       ("Median context-planning seconds", "context_median_ms"), ("Sample p95 context-planning seconds", "context_p95_ms"),
                       ("Median measured product/setup overhead seconds", "overhead_median_ms"),
                       ("Summed measured stage seconds, excluding grading/evidence I/O", "end_to_end_total_ms"),
                       ("Input tokens, including cached", "input_tokens"), ("Cached input tokens", "cached_tokens"),
                       ("Output tokens", "output_tokens"), ("Prior memory records submitted", "memory_deliveries"),
                       ("Attempts with completed usage receipts", "usage_receipts"),
                       ("Observed input-token subtotal, incomplete coverage", "observed_input_subtotal"),
                       ("Observed output-token subtotal, incomplete coverage", "observed_output_subtotal"),
                       ("Experience candidates", "candidates"), ("Admitted observations", "admitted")):
        values = [summary[a][key] for a in ("C", "D")]
        if key.endswith("_ms"):
            values = [None if v is None else round(v / 1000, 2) for v in values]
        lines.append("| " + label + " | " + " | ".join("unknown" if v is None else str(v) for v in values) + " |")
    lines += ["", "Billing and remaining subscription quota are unknown; no API/GPU dispatch was used. Cached tokens are a subset of input, not extra tokens.",
              "Sample p95 uses nearest rank on at most ten observations per arm; it is not a production tail-latency estimate. Summed stage timing omits uninstrumented protected-evidence I/O and is not complete request wall time.",
              "", "| Rep | Task | C | D | C solver s | D solver s | D prior memories |", "| --- | --- | --- | --- | ---: | ---: | ---: |"]
    for repetition in (1, 2):
        for order in range(1, 6):
            # Task identity and chronological order come from started run order;
            # the frozen task ID is joined by the caller's indexed rows.
            pair = {r["run"]["arm"]: r for r in rows if r["run"]["repetition"] == repetition and r.get("task_order") == order}
            task = next(iter(pair.values()))["run"]["task_id"] if pair else f"task-{order}"
            def cell(arm, field):
                row = pair.get(arm)
                if row is None:
                    return "missing"
                return row["result"]["status"] if field == "status" else str(round(row["result"]["stage_ms"]["solver"] / 1000, 2))
            delivered = len(pair["D"]["result"]["memory_ids"]) if "D" in pair else "missing"
            lines.append(f"| {repetition} | {task} | {cell('C','status')} | {cell('D','status')} | {cell('C','solver')} | {cell('D','solver')} | {delivered} |")
    reasons = Counter(reason for r in rows for receipt in r["applicability"] for reason in receipt["reason_codes"])
    digests = {}
    for row in rows:
        digests.setdefault((row["run"]["repetition"], row["run"]["task_id"]), {})[row["run"]["arm"]] = row["result"]["context_sha256"]
    paired = [value for value in digests.values() if set(value) == {"C", "D"}]
    same = sum(value["C"] == value["D"] for value in paired)
    lines += ["", "## Interpretation", "", "Task 1 is cold in each trajectory; later tasks use only their own earlier attempts.",
              "No hidden grade is fed into memory. Stored attempt reports have unknown outcome unless separately verified.",
              "Whole-file anchor freshness is conservative; a changed file can withhold a still-useful lesson.",
              "Operational constraints: some agent reports record denied ambient Git configuration reads. The final D attempt of repetition 1 also reports scratch exhaustion during its public test run, before the later staging failure. Hidden grades ran separately, but these conditions limit ordinary-user latency/quality interpretation. Future-only Git-environment normalization is not retroactively counted as tested in these attempts.",
              "Applicability reason counts: " + json.dumps(dict(reasons), sort_keys=True) + ".",
              f"Paired context byte-digests identical: {same}/{len(paired)} completed C/D pairs (not a claim about the unobserved full model input).",
              "Five public historical tasks and two trajectories do not establish population-level benefit; provider drift and pretraining familiarity remain possible.",
              "CLI prompt/tool streams are retained as declared events, not complete independently observed model/system input.",
              "", "Protocol SHA-256: `" + protocol_sha256 + "`.", ""]
    if summary["D"]["memory_deliveries"] == 0:
        lines += ["No earlier memory reached D in these observed attempts. Any quality/timing difference therefore cannot be attributed to useful recalled experience.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-memories", action="store_true", help="authorized stdout only; never persisted in the metadata report")
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--key-root", type=Path)
    args = parser.parse_args()
    package = json.loads(args.frozen.read_bytes())
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    task_order = {t["manifest"]["task_id"]: t["manifest"]["order"] for t in package["tasks"]}
    rows, events, memories = [], {}, []
    for repetition in (1, 2):
        for arm in ("C", "D"):
            for order in range(1, 6):
                run_id = f"click-v2-r{repetition}-{arm.lower()}-t{order}"
                events[run_id] = vault.inspect(principal, run_id)
                terminal = [e["envelope"]["payload"] for e in events[run_id] if e["envelope"]["event_type"] == "trial.completed"]
                if len(terminal) > 1:
                    raise ValueError("duplicate terminal attempt, not an independent repetition")
                if terminal:
                    row = terminal[0]
                    row["task_order"] = task_order[row["run"]["task_id"]]
                    rows.append(row)
                    if row["formation"].get("proposal"):
                        memories.append({"run_id": run_id, **row["formation"], "later_exposure_must_be_joined_by_record_id": True})
    summary = summarize(rows)
    text = markdown(rows, summary, package["protocol_sha256"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            stream.write(text)
    print(text)
    if args.include_memories:
        print(json.dumps({"authorized_memory_inspection": memories}, ensure_ascii=False))
    if args.archive_root:
        if args.key_root is None or str(args.key_root).startswith("/Volumes/MEM"):
            raise ValueError("private archive key directory must remain off MEM")
        args.key_root.mkdir(parents=True, exist_ok=False, mode=0o700)
        harness = Path(__file__).resolve().parent
        wheel = Path(package["wheel_path"])
        if wheel.stat().st_size > 8_000_000:
            raise ValueError("benchmark artifact retention budget exceeded")
        vault.capture(run_id=package["protocol"]["protocol_id"], kind="harness.source_snapshot", principal=principal,
            payload={"assurance": "post_run_source_retention_not_prefreeze_driver_pin",
                     "files_base64": {path.name: base64.b64encode(path.read_bytes()).decode()
                                      for path in sorted(harness.glob("*.py"))},
                     "wheel_base64": base64.b64encode(wheel.read_bytes()).decode(),
                     "wheel_sha256": sha256(wheel.read_bytes()).hexdigest(),
                     "frozen_protocol_sha256": package["protocol_sha256"]})
        public, secret = generate_recipient_keypair()
        sign_public, sign_secret = generate_signing_keypair()
        for name, value in (("recipient.secret", secret), ("recipient.public", public),
                            ("signing.secret", sign_secret), ("signing.public", sign_public)):
            descriptor = os.open(args.key_root / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(value)
        args.archive_root.mkdir(parents=True, exist_ok=False)
        archived = []
        for run_id in [package["protocol"]["protocol_id"], *events]:
            if run_id in events and not events[run_id]:
                continue
            bundle = vault.encrypted_archive(principal, run_id, recipient_public_key=public,
                signing_public_key=sign_public, signing_secret_key=sign_secret)
            restored = json.loads(open_archive(bundle, run_id=run_id, recipient_secret_key=secret, trusted_signing_public_key=sign_public))
            expected = vault.inspect(principal, run_id)
            if restored != expected:
                raise ValueError("archive did not round-trip exact retained events")
            raw = json.dumps(bundle, separators=(",", ":")).encode()
            with (args.archive_root / (run_id + ".encrypted.json")).open("xb") as stream:
                stream.write(raw)
            archived.append({"run_id": run_id, "sha256": sha256(raw).hexdigest(), "events": len(restored)})
        print(json.dumps({"encrypted_archive": str(args.archive_root), "archives": archived,
                          "private_keys": str(args.key_root), "keys_on_MEM": False}))


if __name__ == "__main__":
    main()
