"""Export only verified public base Git blobs, not a whole evaluator payload."""
import argparse
import base64
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.source_policy import checked_snapshot, path_name, file_byte_limit


def tracked_solver_snapshot(original_base64, baseline, commit, tree, expected_commit, *,
                            runtime_manifest=None, runtime_policy=None):
    if (not re.fullmatch(r"[0-9a-f]{40}", expected_commit) or commit.get("sha") != expected_commit
        or not re.fullmatch(r"[0-9a-f]{40}", commit.get("tree", {}).get("sha", ""))
        or tree.get("sha") != commit["tree"]["sha"] or tree.get("truncated") is not False
        or not isinstance(tree.get("tree"), list) or len(tree["tree"]) > 20000):
        raise ValueError("complete pinned public base tree required")
    fixtures, fixture_seen = {}, set()
    if runtime_manifest is not None:
        from benchmarks.code_replay.runtime_fixtures import validate_manifest
        if runtime_policy is None or baseline.get("format") != "atmem-source-runtime-projection-v2":
            raise ValueError("explicit verified runtime projection required")
        fixtures = validate_manifest(runtime_manifest, runtime_policy)
    elif runtime_policy is not None or baseline.get("format") == "atmem-source-runtime-projection-v2":
        raise ValueError("runtime projection manifest/policy missing")
    files, modes, identities, seen = {}, {}, {}, set()
    for entry in tree["tree"]:
        name = path_name(entry["path"])
        if name in seen:
            raise ValueError("duplicate public tree path")
        seen.add(name)
        if entry.get("type") == "tree" and entry.get("mode") == "040000":
            continue
        if name in fixtures:
            fixture = fixtures[name]
            if (name in original_base64 or entry.get("type") != "blob"
                or entry.get("mode") != fixture["mode"] or entry.get("sha") != fixture["git_blob"]
                or type(entry.get("size")) is not int or entry["size"] != fixture["bytes"]):
                raise ValueError("runtime fixture public Git identity or disjointness differs")
            fixture_seen.add(name)
            identities[name] = fixture["git_blob"]
            continue
        if (entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}
            or not re.fullmatch(r"[0-9a-f]{40}", entry.get("sha", ""))
            or type(entry.get("size")) is not int or not 0 <= entry["size"] <= file_byte_limit(name)):
            raise ValueError("bounded regular public Git blob required")
        encoded = original_base64.get(name)
        if not isinstance(encoded, str) or len(encoded) > 4 * ((file_byte_limit(name) + 2) // 3):
            raise ValueError("captured public base bytes missing or oversized")
        raw = base64.b64decode(encoded, validate=True)
        identity = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if len(raw) != entry["size"] or identity != entry["sha"]:
            raise ValueError("captured source differs from pinned public base blob")
        files[name], modes[name], identities[name] = raw, entry["mode"], identity
    checked_snapshot(files)
    fingerprint = sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()
    if fixture_seen != set(fixtures):
        raise ValueError("runtime fixture absent from public Git tree")
    if runtime_manifest is None:
        count, size = len(files), sum(map(len, files.values()))
        size_matches = baseline.get("bytes") == size
    else:
        count = len(files) + len(fixtures)
        size_matches = (
            baseline.get("source_bytes") == sum(map(len, files.values()))
            and baseline.get("source_files") == len(files)
            and baseline.get("runtime_files") == len(fixtures)
            and baseline.get("runtime_bytes") == sum(item["bytes"] for item in fixtures.values())
            and baseline.get("runtime_manifest_sha256") == sha256(json.dumps(fixtures, sort_keys=True).encode()).hexdigest())
    if (baseline.get("files") != count or not size_matches
        or baseline.get("tree_fingerprint_sha256") != fingerprint):
        raise ValueError("public base differs from qualified container fingerprint")
    result = {"files": files, "modes": modes, "base_commit": expected_commit,
            "tree_sha": tree["sha"], "tree_fingerprint_sha256": fingerprint,
            "untracked_files_exported": 0, "git_history_exported": False}
    if runtime_manifest is not None:
        result.update(runtime_projection="v2", runtime_manifest=fixtures,
                      omitted_runtime_files=len(fixtures))
    return result


def public_api(path):
    reply = subprocess.run(["gh", "api", "repos/marshmallow-code/marshmallow/" + path],
        capture_output=True, check=True, timeout=30)
    return json.loads(reply.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    if Path("/Volumes") in args.state_root.resolve().parents:
        raise ValueError("source export state must stay internal")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "external-solver-source-v1-20261017"
    if vault.inspect(principal, run_id):
        raise ValueError("source export already retained; no silent retry")
    prior = [e["envelope"] for e in vault.inspect(principal, "external-source-boundary-v1-20261017")]
    qualified = [e["payload"] for e in prior if e["event_type"] == "external.boundary_completed"]
    unchanged = [e["payload"] for e in prior if e["event_type"] == "external.boundary_attempt" and e["payload"].get("phase") == "unchanged"]
    if len(qualified) != 1 or qualified[0].get("qualified") is not True or len(unchanged) != 1:
        raise ValueError("qualified source boundary predecessor required")
    worker = unchanged[0].get("worker", {})
    if (worker.get("phase") != "unchanged" or worker.get("base_source_verified") is not True
        or not worker.get("original_sha256") or worker["original_sha256"] != worker.get("candidate_sha256")
        or worker["original_sha256"] != worker.get("assembled_sha256")):
        raise ValueError("only unchanged pre-test original source may be exported")
    base = "456bacbbead4fa30a1a82892c9446ac9efb8055b"
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    vault.capture(run_id=run_id, kind="external.solver_source_planned", principal=principal,
        payload={"base_commit": base, "repository": "marshmallow-code/marshmallow", "solver_calls": 0,
            "prior_run": "external-source-boundary-v1-20261017",
            "driver_source_base64": base64.b64encode(Path(__file__).read_bytes()).decode(),
            "policy_text": Path("specs/042-atmem-code/external-solver-source-v1.md").read_text()})
    try:
        commit = public_api("git/commits/" + base)
        if commit.get("sha") != base or not re.fullmatch(r"[0-9a-f]{40}", commit.get("tree", {}).get("sha", "")):
            raise ValueError("public base commit binding differs")
        tree = public_api("git/trees/" + commit["tree"]["sha"] + "?recursive=1")
        exported = tracked_solver_snapshot(worker["original_files_base64"], worker["tracked_base"], commit, tree, base)
        payload = {key: value for key, value in exported.items() if key != "files"}
        payload.update({"files_base64": {name: base64.b64encode(raw).decode() for name, raw in exported["files"].items()},
                        "public_commit": commit, "public_tree": tree, "solver_calls": 0})
        vault.capture(run_id=run_id, kind="external.solver_source_exported", principal=principal, payload=payload)
        summary = {"qualified_public_base_export": True, "files": len(exported["files"]),
            "bytes": sum(map(len, exported["files"].values())), "solver_calls": 0,
            "untracked_files_exported": 0, "git_history_exported": False, "base_commit": base}
        with (args.state_root / "summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        vault.capture(run_id=run_id, kind="external.solver_source_failed", principal=principal,
            payload={"exception_type": type(exc).__name__, "failure": str(exc), "solver_calls": 0})
        raise


if __name__ == "__main__":
    main()
