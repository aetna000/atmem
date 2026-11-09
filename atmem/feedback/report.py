"""Offline report gates; diagnostic measurements are never qualification.

Missing native/AtMem outcomes, power, conformance or provenance are explicit
insufficient evidence. No pasted aggregate, synthetic success rate or fast
interpreter measurement can manufacture an accepted activation receipt.
"""
import math

from atmem.feedback.baseline import GATES, validate_baseline
from atmem.feedback.observability import percentile


def diagnostic_report(manifest, *, rule_latencies_ms, elapsed_seconds):
    baseline = validate_baseline(manifest)
    if (type(rule_latencies_ms) is not tuple or not 20 <= len(rule_latencies_ms) <= 100
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rule_latencies_ms)
            or type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0):
        raise ValueError("bounded finite actual contract measurements required")
    p95 = percentile(rule_latencies_ms, .95)
    gates = {name:{"status":"insufficient_evidence"} for name in (
        "paired_quality_improvement", "answerable_coverage", "power_and_held_out_provenance", "independent_verification",
        "unauthorized_admissions", "forbidden_call_escapes", "false_denial_rate", "native_disabled_parity",
        "rag_unauthorized_disclosures", "mcp_unauthorized_effects", "retrieval_p95_overhead")}
    gates["pure_rule_p95"] = {"status":"pass" if p95 <= GATES["rule_p95_ms_max"] else "fail",
                              "observed_ms":p95, "ceiling_ms":GATES["rule_p95_ms_max"], "applicable_rules":1000,
                              "basis":"synthetic_allowed_call_interpreter_only"}
    gates["diagnostic_time_budget"] = {"status":"pass" if elapsed_seconds <= manifest["budget"]["seconds"] else "fail"}
    failed = any(row["status"] == "fail" for row in gates.values())
    return {"format":"atmem-feedback-diagnostic-report-v1", "manifest_sha256":baseline.digest,
            "claim":"synthetic_contract_only", "qualification_issued":False,
            "decision":"reject" if failed else "inconclusive", "gates":gates,
            "rule_latency_ms":{"p50":percentile(rule_latencies_ms, .5), "p95":p95, "samples":len(rule_latencies_ms)},
            "resources":{"elapsed_seconds":elapsed_seconds, "model_calls":0, "tokens":0, "usd":0},
            "limitations":["no_quality_run", "no_paid_calls_authorized", "no_acceptance_from_diagnostics",
                           "compilation_storage_auth_and_remote_time_excluded_from_rule_latency"]}
