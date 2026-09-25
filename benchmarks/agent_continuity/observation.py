"""Measure current AtFlows HTTP behaviour; never fill product gaps in the adapter."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

from .adapters.atflows import otlp_attempt
from .manifest import digest, file_digest


def current_source(root: Path) -> dict:
    lock = json.loads(Path(__file__).with_name("protocol-lock.json").read_text())
    pin = lock["current_products"]["atflows"]
    paths = ["apps/server", "packages", "pyproject.toml", "package.json", "bun.lock", "tsconfig.json", "bunfig.toml"]
    subprocess.run(["git", "diff", "--quiet", pin["commit"], "--", *paths], cwd=root, check=True)
    extra = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=root)
    if extra.strip():
        raise ValueError("untracked AtFlows runtime files invalidate current-product arm")
    files = subprocess.check_output(["git", "ls-files", "-z", "--", *paths], cwd=root).decode().split("\0")
    hashes = {name: file_digest(root / name) for name in files if name}
    return {"baseline_commit": pin["commit"], "version": pin["version"],
            "tracked_source_sha256": digest(hashes),
            "dependency_limit": "bun.lock pinned; installed node_modules bytes not hashed",
            "probe_sha256": file_digest(root / "tests/continuity/http-probe.ts"),
            "guard_sha256": file_digest(root / "tests/continuity/offline-preload.cjs")}


def fixtures() -> dict:
    def span(attempt, retry=False):
        return otlp_attempt(workflow_id="fixture-workflow", scope_id="fixture-scope",
            task_id="fixture-task", operation_id="fixture-operation", run_id="fixture-run",
            attempt_id=attempt, charge_id=f"charge-{attempt}", retry=retry, recovery=retry)
    first, lost, late = span("first"), span("lost", True), span("late", True)
    return {"requests": [{"action": "deliver", "payload": first},
                         {"action": "deliver", "payload": first},
                         {"action": "drop", "payload": lost},
                         {"action": "deliver", "payload": late}]}


def assess(plan: dict, observed: dict) -> dict:
    expected = {}
    for request in plan["requests"]:
        for resource in request["payload"]["resourceSpans"]:
            for scope in resource["scopeSpans"]:
                for span in scope["spans"]:
                    identifier = span["spanId"]
                    if identifier in expected and expected[identifier] != span:
                        raise ValueError("conflicting fixture span")
                    expected[identifier] = span
    rows = observed["rows"]
    actual = {row["id"]: row for row in rows}
    if len(actual) != len(rows):
        raise ValueError("duplicate observer rows")
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatched = []
    for identifier in set(expected) & set(actual):
        attrs = json.loads(actual[identifier]["attributes"])
        for item in expected[identifier]["attributes"]:
            key, value = item["key"], item["value"]
            wanted = next(iter(value.values()))
            if "intValue" in value:
                wanted = int(wanted)
            if attrs.get(key) != wanted:
                mismatched.append({"span_id": identifier, "field": key})
    # This is evaluator coverage. AtFlows has no independent knowledge of unsent events.
    return {"expected_unique_spans": len(expected), "retained_expected_spans": len(set(expected) & set(actual)),
            "coverage": len(set(expected) & set(actual)) / len(expected) if expected else None,
            "missing_span_ids": missing, "unexpected_span_ids": unexpected,
            "attribute_mismatches": mismatched,
            "rejected_spans": sum(r.get("body", {}).get("partialSuccess", {}).get("rejectedSpans", 0)
                                  for r in observed["responses"]),
            "fixture_usage": "unknown; no model was invoked",
            "missing_usage_stored_as_zero": sum(row["total_tokens"] == 0 for row in rows),
            "missing_cost_stored_as_zero": sum(row["estimated_cost"] == 0 for row in rows),
            "cost_accuracy": None,
            "cost_accuracy_unavailable_reason": "no priced independent charges in this fixture",
            "coverage_owner": "independent harness, not an AtFlows product feature"}


def run(root: Path, output: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    stamp = current_source(root)
    bun = shutil.which("bun")
    if not bun:
        raise RuntimeError("Bun is required for the isolated current-product probe")
    plan = fixtures()
    output.mkdir(parents=True, exist_ok=False)
    env = {"PATH": os.environ.get("PATH", "")}
    child = subprocess.Popen([bun, "--no-env-file", str(root / "tests/continuity/http-probe.ts"),
                              str(output / "server")], cwd=output, env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    try:
        stdout, stderr = child.communicate(json.dumps(plan), timeout=90)
    except BaseException:
        # Kill only this owned process group, including its owned test server.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.communicate()
        raise
    if child.returncode:
        raise RuntimeError("AtFlows probe failed; no valid observation report (inspect isolated fixture directory)")
    observed = json.loads(stdout)
    if current_source(root) != stamp:
        raise RuntimeError("AtFlows source changed during observation")
    result = {"evidence_level": "engineering-http-fixture", "production_claims_allowed": False,
              "four_arm_evaluation": False, "source": stamp, "harness_sha256": file_digest(Path(__file__)),
              "bun_version": subprocess.check_output([bun, "--version"], text=True).strip(),
              "assessment": assess(plan, observed), "observation": observed,
              "limitations": ["Fixture telemetry, not real agent/model execution",
                  "No authenticated producer binding tested", "No product source changes",
                  "Network guards are test tripwires, not a hostile-code sandbox"]}
    for name, value in [("schedule.json", plan), ("report.json", result)]:
        with (output / name).open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    hashes = {p.name: file_digest(p) for p in output.iterdir() if p.is_file()}
    hashes["server/observations.json"] = file_digest(output / "server/observations.json")
    with (output / "SHA256SUMS.json").open("x") as stream:
        json.dump(hashes, stream, indent=2)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atflows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.atflows, args.output)["assessment"], indent=2))


if __name__ == "__main__":
    main()
