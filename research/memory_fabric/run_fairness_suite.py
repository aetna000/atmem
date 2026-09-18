"""Freeze then execute a paired fairness experiment; never retune on results."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import statistics

from research.memory_fabric.homa_experiment import MIXES, digest, run_trial


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def freeze(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    if (root / "manifest.json").exists():
        raise ValueError("manifest already exists; use run to resume the frozen experiment")
    calibration = run_trial(policy="fifo", profile="write-heavy", seed=7, count=100, rate=10)
    save(root / "calibration.json", calibration)
    if calibration["summary"]["all"]["completed"] != 100 or calibration["quality"]["exact_read_digest_failures"]:
        raise ValueError("calibration incomplete or quality mismatch; cannot freeze")
    estimates = {}
    for kind in ("recall", "write", "artifact"):
        rows = [r for r in calibration["rows"] if r["kind"] == kind and r["outcome"] == "completed"]
        estimates[kind] = statistics.median(r["service_s"] for r in rows)
        for label in ("small", "large"):
            bucket = [r["service_s"] for r in rows if (r["size"] >= 65536) == (label == "large")]
            if bucket:
                estimates[f"{kind}:{label}"] = statistics.median(bucket)
    rates = {}
    for profile, fractions in MIXES.items():
        mean = sum(fraction / 100 * statistics.mean(r["service_s"] for r in calibration["rows"]
                   if r["kind"] == kind and r["outcome"] == "completed")
                   for kind, fraction in zip(("recall", "write", "artifact"), fractions))
        rates[profile] = .95 / mean
    seeds = [101, 103, 107, 109, 113]
    rng = random.Random(73021)
    trials = []
    # Same workload and implementation, repeated FIFO, measures local noise.
    for seed in seeds:
        for repeat in ("aa-a", "aa-b"):
            trials.append({"name": f"{repeat}-{seed}", "policy": "fifo", "profile": "mixed",
                           "seed": seed, "count": 160, "rate": rates["mixed"], "group": "aa"})
    scenarios = [("mixed-low", "mixed", rates["mixed"] * .6 / .95),
                 ("mixed-high", "mixed", rates["mixed"]),
                 ("write-heavy", "write-heavy", rates["write-heavy"]),
                 ("interactive", "interactive", rates["interactive"])]
    pairs = [(scenario, seed) for scenario in scenarios for seed in seeds]
    rng.shuffle(pairs)
    for (scenario, profile, rate), seed in pairs:
        policies = ["fifo", "homa", "fair"]
        rng.shuffle(policies)
        for policy in policies:
            trials.append({"name": f"{scenario}-{seed}-{policy}", "policy": policy, "profile": profile,
                           "seed": seed, "count": 160, "rate": rate, "group": scenario})
    manifest = {"format": "fabric-fairness-manifest-v1", "estimates": estimates,
                "policy_parameters": {"fifo_fraction": .05, "bulk_fraction": .4, "credit_cap_s": .005},
                "source_digest": calibration["source_digest"], "order_seed": 73021,
                "calibration_seed": 7, "held_out_seeds": seeds,
                "primary": "homa vs fifo, paired recall p95 ratio at mixed-high",
                "secondary": "fair fixed-40%-bulk ablation; all other scenarios",
                "acceptance": {"recall_p95_ratio_upper_ci": .90, "bulk_mean_ratio_upper_ci": 1.05,
                               "bulk_throughput_ratio_lower_ci": .95,
                               "all_scenarios_must_pass": True,
                               "no_extra_refusals_errors_or_quality_failures": True},
                "bulk_guardrail_scope": "aggregate bulk AND writes AND artifacts individually",
                "uncertainty": "10000 paired bootstrap draws across five seeds; descriptive pilot intervals",
                "limitations": ["warm, independent read/write subjects", "single non-preemptible worker",
                                "input payload cap excludes preloaded fixture memory", "no release authorization proof",
                                "bulk p95 per-trial sample sizes are small; bulk mean is guardrail"],
                "trials": trials}
    manifest["manifest_sha256"] = digest(manifest)
    save(root / "manifest.json", manifest)
    print(json.dumps({"frozen_manifest": str(root / "manifest.json"), "trials": len(trials),
                      "rates": rates, "estimates": estimates}), flush=True)


def run(root: Path):
    manifest = json.loads((root / "manifest.json").read_text())
    checksum = manifest.pop("manifest_sha256")
    if digest(manifest) != checksum:
        raise ValueError("frozen manifest changed")
    for index, trial in enumerate(manifest["trials"]):
        path = root / (trial["name"] + ".json")
        if path.exists():
            existing = json.loads(path.read_text())
            if existing.get("manifest_sha256") != checksum:
                raise ValueError("existing report belongs to a different manifest")
            continue
        result = run_trial(policy=trial["policy"], profile=trial["profile"], seed=trial["seed"],
                           count=trial["count"], rate=trial["rate"], estimates=manifest["estimates"])
        if result["source_digest"] != manifest["source_digest"]:
            raise ValueError("runner changed after manifest freeze; retain prior runs and freeze a new suite")
        result["manifest_sha256"] = checksum
        result["group"] = trial["group"]
        save(path, result)
        print(json.dumps({"trial": index + 1, "total": len(manifest["trials"]), "name": trial["name"],
                          "recall_p95_ms": round(result["summary"]["recall"]["p95_s"] * 1000, 2),
                          "bulk_mean_ms": round(result["summary"]["bulk"]["mean_s"] * 1000, 2),
                          "completed": result["summary"]["all"]["completed"],
                          "lag_valid": result["generator_valid"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    (freeze if args.action == "freeze" else run)(args.root)


if __name__ == "__main__":
    main()
