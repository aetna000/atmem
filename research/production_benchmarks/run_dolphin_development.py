"""Run the frozen 18-task DolphinBench development slice, not a submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from research.production_benchmarks.dolphinbench import (  # noqa: E402
    evaluate_development,
    require_completed_provider_response,
)
from atmem.benchmark.finalization import validate_finalization_gate  # noqa: E402


def _installed_artifact_sha256() -> str:
    """Hash the installed AtMem package, metadata, and entry point files."""
    from importlib.metadata import distribution
    dist = distribution("atmem")
    files: dict[str, str] = {}
    for entry in sorted(dist.files or (), key=str):
        relative = str(entry)
        if not (
            relative.startswith("atmem/")
            or relative.endswith(("METADATA", "entry_points.txt"))
        ):
            continue
        path = Path(dist.locate_file(entry)).resolve()
        if path.is_file():
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files:
        raise RuntimeError("installed AtMem artifact has no hashable package files")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise RuntimeError(f"DolphinBench checkpoint root does not exist: {root}")
    selected = [
        *sorted((root / "checkpoints").glob("*.json")),
        *sorted((root / "atmem-personas").glob("*.db")),
        *sorted((root / "atmem-personas").glob("*.db-wal")),
        *sorted((root / "atmem-personas").glob("*.db-shm")),
        *sorted((root / "atmem-personas").glob("*.encryption.json")),
    ]
    files = {}
    for path in selected:
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        files[path.relative_to(root).as_posix()] = digest.hexdigest()
    if not files:
        raise RuntimeError("DolphinBench checkpoint root contains no files")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--finalization-gate", required=True)
    parser.add_argument("--checkpoint-root", required=True)
    parser.add_argument(
        "--finalization-manifest", required=True,
        help="independently reviewed JSON identity for this exact paid run",
    )
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("refusing paid DolphinBench development run without confirmation")
    if subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip():
        raise SystemExit("paid DolphinBench run requires the exact clean reviewed commit")
    checkout = Path(args.checkout).expanduser().resolve()
    config = Path(args.config).expanduser().resolve()
    checkpoint_root = Path(args.checkpoint_root).expanduser().resolve()
    if not config.is_file():
        raise SystemExit(f"DolphinBench config does not exist: {config}")
    gate = json.loads(Path(args.finalization_gate).read_text(encoding="utf-8"))
    manifest_path = Path(args.finalization_manifest).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "atmem-dolphin-finalization-manifest-v1":
        raise SystemExit("DolphinBench finalization manifest format is invalid")
    authorization_id = os.environ.get("ATMEM_COST_AUTHORIZATION_ID", "").strip()
    if not authorization_id:
        raise SystemExit("DolphinBench requires ATMEM_COST_AUTHORIZATION_ID")
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))
    from graders import llm_judge
    from harness import runner as official_runner

    grader_identity = {
        "backend": llm_judge.BACKEND,
        "deployment": llm_judge.AZURE_DEPLOYMENT,
        "api_version": llm_judge.AZURE_API_VERSION,
        "reasoning_effort": llm_judge.JUDGE_REASONING_EFFORT,
        "maximum_tokens": llm_judge.DEFAULT_MAX_TOKENS,
        "timeout_seconds": llm_judge.PER_CRITERION_TIMEOUT,
        "maximum_retries": llm_judge.JUDGE_MAX_RETRIES,
        "retry_base_seconds": llm_judge.JUDGE_RETRY_BASE_S,
        "retry_max_seconds": llm_judge.JUDGE_RETRY_MAX_S,
        "parallelism": llm_judge.PER_TEST_PARALLELISM,
        "endpoint_sha256": "sha256:" + hashlib.sha256(
            llm_judge.AZURE_ENDPOINT.encode("utf-8")
        ).hexdigest(),
        "system_prompt_sha256": "sha256:" + hashlib.sha256(
            llm_judge.JUDGE_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
    }
    identity = dict(manifest.get("identity") or {})
    identity.update({
        "gate_type": "dolphinbench",
        "candidate_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "candidate_artifact_sha256": _installed_artifact_sha256(),
        "checkpoint_sha256": _tree_digest(checkpoint_root),
        "run_config_sha256": "sha256:" + hashlib.sha256(config.read_bytes()).hexdigest(),
        "cost_authorization_id": authorization_id,
        "grader_runtime": grader_identity,
        "runner_sha256": "sha256:" + hashlib.sha256(json.dumps({
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "research/production_benchmarks/run_dolphin_development.py",
                ROOT / "research/production_benchmarks/dolphinbench.py",
            )
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    })
    validate_finalization_gate(
        gate, expected_identity=identity, expected_gate_type="dolphinbench"
    )
    original = official_runner.Runner.evaluate
    original_urlopen_json = llm_judge._urlopen_json
    driver_target = str(identity.get("agent_driver_target") or "")
    driver_sha256 = str(identity.get("agent_driver_sha256") or "")
    if not driver_target or not driver_sha256:
        raise RuntimeError("DolphinBench finalization must bind the agent driver")

    def checked_urlopen_json(*args, **kwargs):
        return require_completed_provider_response(
            original_urlopen_json(*args, **kwargs), role="grader"
        )

    def selected_evaluate(instance) -> None:
        if Path(instance.directory).resolve() != checkpoint_root:
            raise RuntimeError(
                "official DolphinBench work directory differs from the bound checkpoint root"
            )
        if _tree_digest(checkpoint_root) != identity["checkpoint_sha256"]:
            raise RuntimeError("DolphinBench checkpoints changed after finalization")
        result = evaluate_development(instance, checkout)
        print(
            f"Completed {result['tests']} frozen development tasks; "
            "this is not an official 600-task score."
        )

    official_runner.Runner.evaluate = selected_evaluate
    llm_judge._urlopen_json = checked_urlopen_json
    old_driver_target = os.environ.get("ATMEM_DOLPHIN_DRIVER_TARGET")
    old_driver_sha256 = os.environ.get("ATMEM_DOLPHIN_DRIVER_SHA256")
    os.environ["ATMEM_DOLPHIN_DRIVER_TARGET"] = driver_target
    os.environ["ATMEM_DOLPHIN_DRIVER_SHA256"] = driver_sha256
    try:
        return int(official_runner.main([
            "evaluate",
            "--config", str(config),
            "--confirm-paid-calls",
        ]))
    finally:
        official_runner.Runner.evaluate = original
        llm_judge._urlopen_json = original_urlopen_json
        if old_driver_target is None:
            os.environ.pop("ATMEM_DOLPHIN_DRIVER_TARGET", None)
        else:
            os.environ["ATMEM_DOLPHIN_DRIVER_TARGET"] = old_driver_target
        if old_driver_sha256 is None:
            os.environ.pop("ATMEM_DOLPHIN_DRIVER_SHA256", None)
        else:
            os.environ["ATMEM_DOLPHIN_DRIVER_SHA256"] = old_driver_sha256


if __name__ == "__main__":
    raise SystemExit(main())
