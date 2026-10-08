"""Build immutable memory checkpoints for every matched LongMemEval arm."""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from atmem.service.household import HouseholdApplication  # noqa: E402
from research.production_benchmarks.longmemeval_v2 import (  # noqa: E402
    install_official_adapter,
    preflight_selected_data,
)
from research.production_benchmarks.installed_product import (  # noqa: E402
    installed_atmem_identity,
)


METHODS = ("no-retrieval", "typed-local", "mem0-oss", "agentrunbook-r")


def _preflight_runtime(protocol: dict) -> dict[str, object]:
    """Reject a partial or wrong-architecture benchmark environment early."""
    expected = dict(protocol["paid_run_requirements"]["official_runtime_packages"])
    installed: dict[str, str] = {}
    missing: list[str] = []
    mismatched: list[str] = []
    for distribution, required in sorted(expected.items()):
        try:
            actual = version(distribution)
        except PackageNotFoundError:
            missing.append(distribution)
            continue
        installed[distribution] = actual
        if actual != required:
            mismatched.append(f"{distribution}={actual} (requires {required})")
    if missing or mismatched:
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if mismatched:
            detail.append("mismatched: " + ", ".join(mismatched))
        raise RuntimeError("official benchmark runtime is incomplete; " + "; ".join(detail))
    # The frozen macOS hardware receipt is arm64.  An Intel/Rosetta interpreter
    # cannot install the pinned Torch wheel and is not the declared runtime.
    machine = platform.machine()
    if sys.platform == "darwin" and machine != "arm64":
        raise RuntimeError(
            f"official macOS benchmark runtime requires arm64 Python; found {machine}"
        )
    product = installed_atmem_identity(
        str(protocol["paid_run_requirements"]["candidate_atmem_version"])
    )
    return {
        "python": sys.version.split()[0], "machine": machine,
        "executable": sys.executable, "packages": installed,
        "installed_product": product,
    }


def _digest_tree(root: Path) -> str:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("._") or path.name == ".DS_Store":
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        files[path.relative_to(root).as_posix()] = digest.hexdigest()
    if not files:
        raise RuntimeError(f"checkpoint contains no files: {root}")
    body = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _wait_ready(process: subprocess.Popen, path: Path) -> str:
    for _ in range(200):
        if path.is_file():
            return str(json.loads(path.read_text(encoding="utf-8"))["base_url"])
        if process.poll() is not None:
            raise RuntimeError("local embedding proxy exited before readiness")
        time.sleep(0.05)
    raise RuntimeError("local embedding proxy did not become ready")


def _start_embedding_proxy(ready: Path) -> tuple[subprocess.Popen, str]:
    """Start a fresh proxy without trusting a prior run's readiness receipt."""
    ready.unlink(missing_ok=True)
    process = subprocess.Popen([
        sys.executable,
        str(ROOT / "research/production_benchmarks/local_embedding_proxy.py"),
        "--ready-file", str(ready),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process, _wait_ready(process, ready)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--mem0-checkout", required=True)
    parser.add_argument("--reader-base-url", default=os.environ.get("ATMEM_READER_BASE_URL", ""))
    parser.add_argument("--confirm-paid-formation", action="store_true")
    parser.add_argument(
        "--resume", action="store_true",
        help="reuse only completed, digestible arm checkpoints in an existing root",
    )
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    args = parser.parse_args()
    methods = tuple(dict.fromkeys(args.methods))
    if "agentrunbook-r" in methods and not args.confirm_paid_formation:
        raise SystemExit("AgentRunbook-R formation requires --confirm-paid-formation")
    if "agentrunbook-r" in methods and (
        not args.reader_base_url or not os.environ.get("RUNPOD_READER_API_KEY")
    ):
        raise SystemExit("AgentRunbook-R formation requires the RunPod URL and key")
    checkout = Path(args.checkout).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    output = Path(args.output_root).expanduser().resolve()
    mem0_checkout = Path(args.mem0_checkout).expanduser().resolve()
    if output.exists() and not args.resume:
        raise SystemExit(f"refusing to overwrite checkpoint root: {output}")
    if not mem0_checkout.is_dir():
        raise SystemExit("pinned Mem0 checkout does not exist")
    install = install_official_adapter(checkout)
    protocols = ROOT / "benchmarks/retrieval_quality/protocols"
    profile = json.loads((protocols / "longmemeval-v2-development-5pct-v1.json").read_text())
    protocol = json.loads((protocols / "2.3.8.yaml").read_text())
    runtime = _preflight_runtime(protocol)
    pin = protocol["datasets"]["longmemeval_v2"]
    preflight = preflight_selected_data(
        data_root, profile["question_ids"], dataset_revision=pin["dataset_revision"],
        expected_sha256=pin["content_sha256"],
    )
    if preflight.selected_input_manifest_sha256 != profile["selected_input_manifest_sha256"]:
        raise RuntimeError("selected dataset differs from the frozen profile")
    domains: dict[str, list[str]] = {"web": [], "enterprise": []}
    for line in (data_root / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("id") in profile["question_ids"]:
            domains[str(row["domain"])].append(str(row["id"]))
    output.mkdir(parents=True, exist_ok=args.resume)
    ready = output / "embedding-ready.json"
    proxy, embedding_url = _start_embedding_proxy(ready)
    receipts = []
    try:
        work = [("no-retrieval", "web")]
        work.extend(
            (method, domain) for method in methods if method != "no-retrieval"
            for domain in ("web", "enterprise") if domains[domain]
        )
        for method, domain in work:
            official_method = {
                "no-retrieval": "no_retrieval", "typed-local": "atmem",
                "mem0-oss": "mem0_oss", "agentrunbook-r": "agentrunbook_r",
            }[method]
            destination = output / method / (domain if method != "no-retrieval" else "")
            build_output = destination
            state = build_output / "memory_state"
            if args.resume and state.is_dir():
                receipts.append({
                    "method": method, "domain": domain,
                    "checkpoint": str(state), "checkpoint_sha256": _digest_tree(state),
                    "resumed": True,
                })
                continue
            environment = dict(os.environ)
            environment.update({
                "PYTHONDONTWRITEBYTECODE": "1",
                "ATMEM_LME_DATABASE_PATH": str(destination / "build.db"),
                "ATMEM_LME_SUBJECT_ID": "longmemeval-public",
                "ATMEM_LME_AGENT_ID": "longmemeval-v2",
                "ATMEM_LME_WORKSPACE_ID": f"{domain}-small",
                "ATMEM_MEM0_CHECKOUT": str(mem0_checkout),
                "ATMEM_MEM0_STORAGE_PATH": str(destination / "mem0-build"),
            })
            if method == "typed-local":
                destination.mkdir(parents=True, exist_ok=True)
                HouseholdApplication.initialize(
                    destination / "build.db", encrypted=True, backend="file"
                )
            command = [
                sys.executable, str(checkout / "evaluation/run_eval.py"),
                "--data-root", str(data_root), "--domain", domain,
                "--tier", "small", "--method", official_method,
                "--output-dir", str(build_output), "--question-ids", *domains[domain],
                "--save-memory", "--skip-evaluation",
                "--reader-model", "Qwen/Qwen3.5-9B",
                "--reader-base-url", args.reader_base_url or "http://127.0.0.1:9/v1",
                "--reader-api-key-env", "RUNPOD_READER_API_KEY",
                "--controller-model", "Qwen/Qwen3.5-9B",
                "--controller-base-url", args.reader_base_url or "http://127.0.0.1:9/v1",
                "--controller-api-key-env", "RUNPOD_READER_API_KEY",
                "--embedding-model", "atmem/hash-bow-768-v1",
                "--embedding-base-url", embedding_url,
                "--embedding-api-key-env", "RUNPOD_READER_API_KEY",
            ]
            subprocess.run(command, cwd=checkout, env=environment, check=True)
            receipts.append({
                "method": method, "domain": domain,
                "checkpoint": str(state), "checkpoint_sha256": _digest_tree(state),
                "resumed": False,
            })
    finally:
        proxy.terminate()
        try:
            proxy.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proxy.kill()
            proxy.wait(timeout=5)
    # A targeted resume must not erase receipts for already-complete matched
    # arms. This is important when AtMem formation is rebuilt locally while
    # expensive comparator checkpoints are intentionally reused.
    recorded = {(str(row["method"]), str(row["domain"])) for row in receipts}
    for method in METHODS:
        domains_to_check = ("web",) if method == "no-retrieval" else ("web", "enterprise")
        for domain in domains_to_check:
            key = (method, domain)
            if key in recorded:
                continue
            destination = output / method / (domain if method != "no-retrieval" else "")
            state = destination / "memory_state"
            if state.is_dir() and (state / "memory_config.json").is_file():
                receipts.append({
                    "method": method,
                    "domain": domain,
                    "checkpoint": str(state),
                    "checkpoint_sha256": _digest_tree(state),
                    "resumed": True,
                })
                recorded.add(key)
    receipts.sort(key=lambda row: (str(row["method"]), str(row["domain"])))
    manifest = {
        "format": "atmem-longmemeval-matched-checkpoints-v1",
        "profile_sha256": profile["profile_sha256"],
        "adapter_install": install,
        "runtime": runtime,
        "arms": receipts,
    }
    (output / "checkpoint-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
