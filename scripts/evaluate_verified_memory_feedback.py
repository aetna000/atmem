#!/usr/bin/env python3
"""Bounded, content-free synthetic rule report. No memory, model or network I/O."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atmem.contracts.feedback import FeedbackScope, MCPInvocation, RuleCandidate, RulePredicate, SourceRevision
from atmem.feedback.baseline import MAX_MANIFEST_BYTES, validate_baseline
from atmem.feedback.report import diagnostic_report
from atmem.rules.compiler import compile_rule
from atmem.rules.evaluator import evaluate


def run(manifest, *, samples=20):
    if type(samples) is not int or not 20 <= samples <= 100:
        raise ValueError("20..100 bounded samples required")
    validate_baseline(manifest)
    started = time.perf_counter()
    candidate = RuleCandidate("synthetic-rule", FeedbackScope("fixture", "fixture", "fixture", "fixture"),
        "fixture.write", "v1", (SourceRevision("synthetic-source", 1, sha256(b"synthetic").hexdigest()),),
        (RulePredicate("equals", ("target",), "staging"),), "Synthetic interpreter timing only.")
    schema = {"type":"object", "properties":{"target":{"type":"string"}},
              "required":["target"], "additionalProperties":False}
    compiled = []
    for i in range(1000):
        if time.perf_counter()-started > manifest["budget"]["seconds"]:
            raise ValueError("diagnostic time budget exhausted during compilation")
        compiled.append(compile_rule(replace(candidate, rule_id=f"synthetic-{i}"), schema))
    rules = tuple(compiled)
    invocation = MCPInvocation("fixture.write", "v1", {"target":"staging"}, "never-dispatched")
    latencies = []
    for _ in range(samples):
        if time.perf_counter()-started > manifest["budget"]["seconds"]:
            raise ValueError("diagnostic time budget exhausted")
        tick = time.perf_counter()
        result = evaluate(rules, invocation)
        latencies.append((time.perf_counter()-tick)*1000)
        if not result.allowed or len(result.applicable_rule_ids) != 1000:
            raise ValueError("synthetic interpreter contract failed")
    report = diagnostic_report(manifest, rule_latencies_ms=tuple(latencies), elapsed_seconds=time.perf_counter()-started)
    encoded = json.dumps(report, sort_keys=True, indent=2).encode()
    if len(encoded) > manifest["budget"]["disk_bytes"]:
        raise ValueError("diagnostic output budget exhausted")
    return encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    with args.manifest.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES+1)
    if len(raw)>MAX_MANIFEST_BYTES:
        parser.error("manifest exceeds byte ceiling")
    encoded = run(json.loads(raw), samples=args.samples)
    with args.output.open("xb") as stream:
        stream.write(encoded)
    print("Diagnostic report written; no qualification or quality claim issued.")


if __name__ == "__main__":
    main()
