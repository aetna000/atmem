"""Paired report and descriptive seed-bootstrap intervals for frozen trials."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import random
import statistics

from research.memory_fabric.homa_experiment import digest, percentile


def interval(ratios):
    if not ratios or any(value is None or not math.isfinite(value) or value <= 0 for value in ratios):
        return {"geometric_mean_ratio": None, "bootstrap_95": [None, None], "paired_ratios": ratios}
    values = [math.log(value) for value in ratios]
    rng = random.Random(1009)
    draws = [math.exp(statistics.mean(rng.choices(values, k=len(values)))) for _ in range(10000)]
    return {"geometric_mean_ratio": math.exp(statistics.mean(values)),
            "bootstrap_95": [percentile(draws, .025), percentile(draws, .975)],
            "paired_ratios": ratios}


def analyze(root):
    manifest = json.loads((root / "manifest.json").read_text())
    checksum = manifest.pop("manifest_sha256")
    if digest(manifest) != checksum:
        raise ValueError("manifest checksum mismatch")
    reports = {}
    for trial in manifest["trials"]:
        report = json.loads((root / (trial["name"] + ".json")).read_text())
        if report["manifest_sha256"] != checksum or report["source_digest"] != manifest["source_digest"]:
            raise ValueError("source or manifest mismatch")
        reports[trial["name"]] = report
    result = {"manifest_sha256": checksum, "trials": len(reports), "comparisons": {},
              "all_generator_valid": all(r["generator_valid"] for r in reports.values()),
              "total_offered": sum(r["summary"]["all"]["offered"] for r in reports.values()),
              "total_completed": sum(r["summary"]["all"]["completed"] for r in reports.values()),
              "errors": sum(r["summary"]["all"]["error"] for r in reports.values()),
              "refused": sum(r["summary"]["all"]["refused"] for r in reports.values()),
              "digest_failures": sum(r["quality"]["exact_read_digest_failures"] for r in reports.values()),
              "reconstructed_events": sum(r["quality"]["reconstructed_events"] for r in reports.values()),
              "recovered_artifacts": sum(r["quality"]["recovered_artifacts"] for r in reports.values())}
    seeds = manifest["held_out_seeds"]
    result["aa_recall_p95"] = interval([reports[f"aa-b-{s}"]["summary"]["recall"]["p95_s"] /
                                       reports[f"aa-a-{s}"]["summary"]["recall"]["p95_s"] for s in seeds])
    for group in ("mixed-low", "mixed-high", "write-heavy", "interactive"):
        result["comparisons"][group] = {}
        for policy in ("homa", "fair"):
            pairs = [(reports[f"{group}-{s}-fifo"], reports[f"{group}-{s}-{policy}"]) for s in seeds]
            for left, right in pairs:
                if left["workload_digest"] != right["workload_digest"] or left["media_digest"] != right["media_digest"]:
                    raise ValueError("paired fixture mismatch")
            metrics = {}
            for label, lane, key in (("recall_p95", "recall", "p95_s"), ("bulk_mean", "bulk", "mean_s"),
                                     ("bulk_p95", "bulk", "p95_s"), ("bulk_throughput", "bulk", "completed_per_s"),
                                     ("write_mean", "write", "mean_s"), ("artifact_mean", "artifact", "mean_s"),
                                     ("write_throughput", "write", "completed_per_s"),
                                     ("artifact_throughput", "artifact", "completed_per_s")):
                ratios = [(b["summary"][lane][key] / a["summary"][lane][key])
                          if a["summary"][lane][key] and b["summary"][lane][key] is not None else None
                          for a, b in pairs]
                metrics[label] = interval(ratios)
                for name, values in (("fifo_median", [a["summary"][lane][key] for a, _ in pairs]),
                                     ("candidate_median", [b["summary"][lane][key] for _, b in pairs])):
                    metrics[label][name] = statistics.median(values) if all(v is not None for v in values) else None
            metrics["counts"] = {variant: {key: sum(r["summary"]["all"][key] for r in rows)
                                                  for key in ("offered", "completed", "error", "refused")}
                                  for variant, rows in (("fifo", [a for a, _ in pairs]),
                                                        (policy, [b for _, b in pairs]))}
            gates = manifest["acceptance"]
            def upper(key):
                return metrics[key]["bootstrap_95"][1] if metrics[key]["bootstrap_95"][1] is not None else math.inf
            def lower(key):
                return metrics[key]["bootstrap_95"][0] if metrics[key]["bootstrap_95"][0] is not None else -math.inf
            metrics["passes_predeclared_gate"] = (
                upper("recall_p95") <= gates["recall_p95_ratio_upper_ci"]
                and upper("bulk_mean") <= gates["bulk_mean_ratio_upper_ci"]
                and lower("bulk_throughput") >= gates["bulk_throughput_ratio_lower_ci"]
                and all(upper(f"{kind}_mean") <= gates["bulk_mean_ratio_upper_ci"]
                        and lower(f"{kind}_throughput") >= gates["bulk_throughput_ratio_lower_ci"]
                        for kind in ("write", "artifact"))
                and all(b["generator_valid"] and a["generator_valid"] and
                        b["quality"]["exact_read_digest_failures"] == a["quality"]["exact_read_digest_failures"] == 0
                        and b["summary"]["all"]["error"] == a["summary"]["all"]["error"] == 0
                        and all(b["summary"][lane]["refused"] <= a["summary"][lane]["refused"]
                                for lane in ("recall", "write", "artifact")) for a, b in pairs))
            result["comparisons"][group][policy] = metrics
    result["accepted"] = {policy: all(group[policy]["passes_predeclared_gate"]
                                      for group in result["comparisons"].values()) for policy in ("homa", "fair")}
    result["limitations"] = ["five-seed bootstrap is descriptive, not a high-powered superiority trial",
                              "atomic local operations; no host exposure or authority proof",
                              "no comparison of production Homa networking performance"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    result = analyze(args.root)
    (args.root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))
