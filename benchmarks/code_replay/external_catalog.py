"""Pinned metadata-only external preflight. No gold/tests/hints or solver calls."""
import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess

import yaml


UPSTREAM = "SWE-bench/swe-bench-tasks"
REVISION = "3d07b464b7b311a0cbfb5ed5b2d8a3b96f84a33d"
TASK_TREE = "39df60edb3d9e709c7f6c19516c1d4b1fa3a8d50"
SEED = "atmem-repository-disjoint-preflight-20261017-v1"
REPOSITORIES = ("marshmallow-code/marshmallow", "psf/requests", "pylint-dev/astroid")
CONFIRMATION_REPOSITORIES = ("pydicom/pydicom", "sqlfluff/sqlfluff", "pvlib/pvlib-python", "pytest-dev/pytest", "sphinx-doc/sphinx")
CONFIRMATION_SEED = "atmem-repository-disjoint-confirmation-20261018-v1"
ELIGIBILITY_REPOSITORIES = ('pallets/flask', 'mwaskom/seaborn', 'pydata/xarray', 'pylint-dev/pylint', 'pyvista/pyvista')
ELIGIBILITY_SEED = 'atmem-repository-disjoint-confirmation-eligibility-20261018-v2'
ALLOWED_FILES = {"task.yaml", "Dockerfile"}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def api(path):
    result = subprocess.run(["gh", "api", "repos/" + UPSTREAM + "/" + path],
        capture_output=True, check=True, timeout=30)
    if len(result.stdout) > 3_000_000:
        raise ValueError("metadata response budget exceeded")
    return json.loads(result.stdout)


def catalog(tree, *, seed=SEED, per_repo=2, repositories=REPOSITORIES, eligibility_pool=False):
    if tree.get("sha") != TASK_TREE or tree.get("truncated") is not False:
        raise ValueError("complete pinned task tree required")
    if type(eligibility_pool) is not bool:
        raise ValueError('explicit eligibility-pool mode required')
    if type(per_repo) is not int or not 1 <= per_repo <= (8 if eligibility_pool else 4):
        raise ValueError("bounded per-repository preflight count required")
    if eligibility_pool and (tuple(repositories) != ELIGIBILITY_REPOSITORIES or seed != ELIGIBILITY_SEED or per_repo != 8):
        raise ValueError('fixed prospective eligibility design required')
    if (not isinstance(repositories, (tuple, list)) or not 1 <= len(repositories) <= 5
        or len(set(repositories)) != len(repositories)
        or any(not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) for repo in repositories)):
        raise ValueError("bounded distinct repository identities required")
    candidates = {}
    for entry in tree["tree"]:
        if entry.get("type") != "tree":
            continue
        name = entry["path"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+", name) or not re.fullmatch(r"[0-9a-f]{40}", entry["sha"]):
            raise ValueError("invalid task catalog entry")
        if name in candidates:
            raise ValueError("duplicate task identity")
        candidates[name] = entry["sha"]
    groups, selected = {}, []
    for repo in repositories:
        prefix = repo.replace("/", "__") + "-"
        pool = sorted(name for name in candidates if name.startswith(prefix))
        if len(pool) < per_repo:
            raise ValueError("insufficient declared repository candidates")
        ordered = sorted(pool, key=lambda name: (sha256((seed + "\0" + repo + "\0" + name).encode()).hexdigest(), name))
        groups[repo] = ordered
        selected += [{"instance_id": name, "repo": repo, "task_tree": candidates[name]} for name in ordered[:per_repo]]
    result = {"format": "atmem-external-catalog-preflight-v1", "upstream": UPSTREAM,
        "revision": REVISION, "task_tree": TASK_TREE, "seed": seed, "per_repo": per_repo,
        "ordered_candidate_pools": groups, "selected": selected,
        "selection_rule": "sha256(seed,NUL,repository,NUL,instance_id); first fixed count; no outcome filtering",
        "selection_basis": "metadata identities only; not qualified or scored",
        "solver_calls": 0, "gold_test_hints_opened": False}
    if eligibility_pool:
        result['sampling_stage'] = 'eligibility_candidates_not_final_model_tasks'
        result['final_model_tasks_per_repository'] = 4
    return result


def checked_blob(entry, fetch=api):
    if entry.get("path") not in ALLOWED_FILES or entry.get("type") != "blob" or entry.get("mode") != "100644":
        raise ValueError("only regular metadata and recipe blobs allowed")
    if not re.fullmatch(r"[0-9a-f]{40}", entry.get("sha", "")) or type(entry.get("size")) is not int or not 0 < entry["size"] <= 262144:
        raise ValueError("bounded pinned metadata blob required")
    response = fetch("git/blobs/" + entry["sha"])
    if response.get("encoding") != "base64":
        raise ValueError("base64 metadata blob required")
    raw = base64.b64decode("".join(response["content"].split()), validate=True)
    actual = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if len(raw) != entry["size"] or actual != entry["sha"] or response.get("sha") != actual:
        raise ValueError("metadata blob identity differs")
    return raw


def task_metadata(raw, selected):
    # Upstream task manifests are small flat mappings. No executable YAML loader.
    if len(raw) > 65536:
        raise ValueError("task metadata budget")
    value = yaml.safe_load(raw)
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("bounded task mapping required")
    fields = ("instance_id", "repo", "base_commit", "created_at", "image", "log_parser", "eval_type", "split", "version")
    if any(not isinstance(value.get(k), str) or not 0 < len(value[k]) <= 512 for k in fields):
        raise ValueError("typed task identity/environment metadata required")
    if value["instance_id"] != selected["instance_id"] or value["repo"] != selected["repo"] or not re.fullmatch(r"[0-9a-f]{40}", value["base_commit"]):
        raise ValueError("task identity/base commit differs")
    datasets = value.get("datasets")
    if not isinstance(datasets, list) or not 1 <= len(datasets) <= 16 or any(not isinstance(d, str) or len(d) > 256 for d in datasets):
        raise ValueError("declared upstream dataset membership required")
    return {**{k: value[k] for k in fields}, "datasets": datasets,
        "image_digest_pinned": bool(re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", value["image"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-repo", type=int, default=2)
    parser.add_argument("--confirmation", action="store_true", help="Use the five prospectively declared new repositories and a distinct fixed seed")
    parser.add_argument('--eligibility-v2', action='store_true', help='Freeze forty feasibility candidates for the new product; not final model tasks')
    args = parser.parse_args()
    if args.confirmation and args.eligibility_v2:
        raise ValueError('select one prospective design only')
    if args.output.exists():
        raise ValueError("preflight output already exists; no silent reselection")
    root = api("git/trees/" + REVISION)
    tasks = [e for e in root.get("tree", []) if e.get("path") == "tasks" and e.get("type") == "tree"]
    if root.get("truncated") is not False or len(tasks) != 1 or tasks[0]["sha"] != TASK_TREE:
        raise ValueError("task tree is not bound to pinned repository revision")
    tree = api("git/trees/" + TASK_TREE)
    plan = catalog(tree, per_repo=args.per_repo,
        repositories=ELIGIBILITY_REPOSITORIES if args.eligibility_v2 else CONFIRMATION_REPOSITORIES if args.confirmation else REPOSITORIES,
        seed=ELIGIBILITY_SEED if args.eligibility_v2 else CONFIRMATION_SEED if args.confirmation else SEED,
        eligibility_pool=args.eligibility_v2)
    # Retain selection BEFORE fetching task content; failed metadata cannot
    # change the pool, hide attrition or trigger a replacement task.
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (args.output / "selection.json").open("x") as stream:
        json.dump(plan, stream, indent=2, sort_keys=True)
    reports = []
    for selected in plan["selected"]:
        report = {"instance_id": selected["instance_id"], "repo": selected["repo"], "qualified": False}
        try:
            task_tree = api("git/trees/" + selected["task_tree"])
            if task_tree.get("sha") != selected["task_tree"] or task_tree.get("truncated") is not False:
                raise ValueError("pinned complete task subtree required")
            entries = {e["path"]: e for e in task_tree["tree"] if e["path"] in ALLOWED_FILES}
            if set(entries) != ALLOWED_FILES:
                raise ValueError("missing metadata/recipe")
            blobs = {name: checked_blob(entries[name]) for name in sorted(ALLOWED_FILES)}
            report.update(metadata=task_metadata(blobs["task.yaml"], selected),
                files={name: {"git_blob": entries[name]["sha"], "sha256": sha256(raw).hexdigest(),
                    "bytes_base64": base64.b64encode(raw).decode()} for name, raw in blobs.items()},
                declared_platforms=sorted(set(re.findall(r"--platform=(\S+)", blobs["Dockerfile"].decode()))),
                status="metadata_verified_environment_not_executed")
        except Exception as exc:
            report.update(status="metadata_preflight_failed", error=type(exc).__name__ + ": " + str(exc))
        reports.append(report)
        print(json.dumps({k: report[k] for k in ("instance_id", "status", "qualified")}), flush=True)
    result = {"selection_sha256": digest(plan), "created_at": datetime.now(timezone.utc).isoformat(),
              "reports": reports, "solver_calls": 0, "gold_test_hints_opened": False,
              "assurance": "metadata_only_not_environment_reference_or_model_qualification"}
    with (args.output / "metadata.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print(json.dumps({"selected": len(reports), "metadata_verified": sum(r["status"] == "metadata_verified_environment_not_executed" for r in reports),
                      "environment_qualified": 0, "selection_sha256": digest(plan)}), flush=True)


if __name__ == "__main__":
    main()
