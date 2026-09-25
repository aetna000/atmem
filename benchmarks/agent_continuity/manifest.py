"""Pin public inputs and reserve held-out tasks without copying their answers."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
import platform
import urllib.request

UPSTREAM_COMMIT = "b7ea9074c1cba482b30687fecdb5c8425fd6f619"
WRITE_TOOLS = (
    "cancel_pending_order", "exchange_delivered_order_items",
    "modify_pending_order_address", "modify_pending_order_items",
    "modify_pending_order_payment", "modify_user_address",
    "return_delivered_order_items",
)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def partition(tasks: list[dict], base_ids: list[str], seed: int, database: dict | None = None) -> dict:
    """Cluster related customer/order tasks before selecting any held-out IDs.

    Task 0 was inspected during protocol design, so its entire cluster is pilot.
    Evaluation labels are used only by this evaluator-side manifest builder.
    """
    base = set(base_ids)
    if len(base) != len(base_ids):
        raise ValueError("duplicate base task IDs")
    if "0" not in base:
        raise ValueError("design-exposed task 0 must be present in base split")
    if len({str(t["id"]) for t in tasks}) != len(tasks):
        raise ValueError("duplicate task IDs")
    if not base <= {str(t["id"]) for t in tasks}:
        raise ValueError("missing base task")
    groups: list[tuple[set[str], set[str]]] = []
    excluded = []
    users = (database or {}).get("users", {})
    orders = (database or {}).get("orders", {})
    for task in tasks:
        tid = str(task["id"])
        if tid not in base:
            continue
        actions = (task.get("evaluation_criteria") or {}).get("actions") or []
        if not any(a["name"] in WRITE_TOOLS for a in actions):
            excluded.append(tid)
        keys = set()
        for action in actions:
            for key, value in action.get("arguments", {}).items():
                if key in {"user_id", "order_id", "email"}:
                    keys.add(f"{key}:{value}")
                if key == "user_id":
                    keys.add("customer:" + str(value))
                if key == "order_id" and value in orders:
                    keys.add("customer:" + orders[value]["user_id"])
                if key == "email":
                    for uid, user in users.items():
                        if user.get("email", "").casefold() == str(value).casefold():
                            keys.add("customer:" + uid)
            if action["name"] == "find_user_id_by_name_zip":
                keys.add("person:" + digest(action["arguments"]))
                args = action["arguments"]
                for uid, user in users.items():
                    if all(str(user["name"].get(k, "")).casefold() == str(args.get(k, "")).casefold()
                           for k in ("first_name", "last_name")) and str(user["address"]["zip"]) == str(args.get("zip")):
                        keys.add("customer:" + uid)
        ids = {tid}
        matched = [g for g in groups if g[1] & keys]
        for group in matched:
            ids |= group[0]
            keys |= group[1]
            groups.remove(group)
        groups.append((ids, keys))
    # Read-only tasks still connect clusters even though not scored in write cohort.
    clusters = sorted([(sorted(ids - set(excluded)), "0" in ids)
                       for ids, _ in groups if ids - set(excluded)], key=lambda x: x[0][0])
    forced = [c for c, exposed in clusters if exposed]
    rest = [c for c, exposed in clusters if not exposed]
    random.Random(seed).shuffle(rest)
    count = max(1, round(len(clusters) * .2))
    pilot_clusters = forced + rest[:max(0, count-len(forced))]
    heldout_clusters = rest[max(0, count-len(forced)):]
    if not pilot_clusters or not heldout_clusters:
        raise ValueError("need disjoint nonempty pilot and held-out clusters")
    pilot = sorted(t for c in pilot_clusters for t in c)
    heldout = sorted(t for c in heldout_clusters for t in c)
    return {"seed": seed, "pilot_ids": pilot, "heldout_ids": heldout,
            "pilot_clusters": pilot_clusters, "heldout_clusters": heldout_clusters,
            "pilot_digest": digest(pilot), "heldout_digest": digest(heldout),
            "excluded_zero_write_ids": sorted(excluded),
            "design_exposed_ids": ["0"],
            "method": "canonical customer aliases from pinned DB; read-only bridges retained; 20% pilot clusters"}


def pinned_file(root: Path, relative: str) -> Path:
    expected = subprocess.check_output(["git", "show", f"{UPSTREAM_COMMIT}:{relative}"], cwd=root)
    path = root / relative
    if path.read_bytes() != expected:
        raise ValueError(f"upstream file differs from pinned commit: {relative}")
    return path


def source_version(root: Path) -> str:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]


def environment_stamp(*, lock_path: Path | None = None) -> dict:
    root = Path(__file__).resolve().parent
    lock_path = lock_path or root / "protocol-lock.json"
    lock = json.loads(lock_path.read_text())
    versions = {}
    for name, metadata in lock["runtime"]["packages"].items():
        versions[name] = importlib.metadata.version(name)
        if versions[name] != metadata["version"]:
            raise ValueError(f"installed {name} does not match protocol lock")
    requirements = root / "requirements.txt"
    for line in requirements.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.split("==")
        versions[name] = importlib.metadata.version(name)
        if versions[name] != expected:
            raise ValueError(f"installed {name} differs from benchmark requirements")
    versions["atmem"] = importlib.metadata.version("atmem")
    if versions["atmem"] != lock["current_products"]["atmem"]["version"]:
        raise ValueError("installed AtMem version differs from pinned current-product arm")
    source = {str(p.relative_to(root)): file_digest(p) for p in root.rglob("*.py")}
    import atmem
    product_root = Path(atmem.__file__).resolve().parent
    product_source = {str(p.relative_to(product_root)): file_digest(p)
                      for p in product_root.rglob("*")
                      if p.is_file() and p.suffix in {".py", ".json", ".sql", ".yaml", ".yml"}}
    return {"protocol_sha256": file_digest(lock_path), "harness_sha256": digest(source),
            "atmem_source_sha256": digest(product_source),
            "requirements_sha256": file_digest(requirements),
            "packages": versions, "python": platform.python_version()}


def make_lock(upstream: Path, atmem: Path, atflows: Path) -> dict:
    if git_head(upstream) != UPSTREAM_COMMIT:
        raise ValueError("wrong upstream commit")
    tasks_path = pinned_file(upstream, "data/tau2/domains/retail/tasks.json")
    splits = pinned_file(upstream, "data/tau2/domains/retail/split_tasks.json")
    database_path = pinned_file(upstream, "data/tau2/domains/retail/db.json")
    license_path = pinned_file(upstream, "LICENSE")
    if "MIT License" not in license_path.read_text():
        raise ValueError("unexpected upstream license")
    artifacts = {}
    for name, version in (("langgraph", "1.2.12"), ("langgraph-checkpoint-sqlite", "3.1.1")):
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
            metadata = json.load(response)
        artifacts[name] = {"version": version, "files": [
            {"filename": f["filename"], "sha256": f["digests"]["sha256"], "url": f["url"]}
            for f in metadata["urls"]], "license": "MIT"}
    return {
        "schema_version": 1, "evidence_level": "protocol-only",
        "upstream": {"repository": "https://github.com/sierra-research/tau2-bench",
                     "commit": UPSTREAM_COMMIT, "package_version": "1.0.1",
                     "license": "MIT", "license_sha256": file_digest(license_path),
                     "tasks_sha256": file_digest(tasks_path), "split_sha256": file_digest(splits),
                     "database_sha256": file_digest(database_path),
                     "domain": "retail", "suite": "base"},
        "split": partition(json.loads(tasks_path.read_text()), json.loads(splits.read_text())["base"], 20260925,
                           json.loads(database_path.read_text())),
        "runtime": {"name": "langgraph", "packages": artifacts},
        "current_products": {"atmem": {"commit": git_head(atmem), "version": source_version(atmem)},
                             "atflows": {"commit": git_head(atflows), "version": source_version(atflows)}},
        "contract_sha256": file_digest(atmem / "specs/benchmarking/002-agent-continuity/contracts/continuity-v1.md"),
        "write_tools": list(WRITE_TOOLS),
        "live_model_protocol": {"status": "not_executed", "agent_model": "gpt-4.1-2025-04-14",
                                "user_model": "gpt-4.1-2025-04-14", "temperature": 0,
                                "prompts": "upstream pinned prompts; digest at live adapter freeze",
                                "egress": "public workload only; explicit live opt-in required"},
        "equivalence": {"recorded_outcome_agreement": 1.0,
                        "native_wrapped_pass_rate_margin_absolute": .02},
        "limitations": ["No paid evaluation or production evidence yet",
                        "Upstream native equivalence and live adapter remain required",
                        "Source commits pinned; installed wheel hashes still required before G2"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--atflows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = make_lock(args.upstream, Path(__file__).resolve().parents[2], args.atflows)
    # Exclusive create prevents a later run silently choosing a more favorable split.
    with args.output.open("x") as output:
        json.dump(lock, output, indent=2, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
