"""Run the frozen 30-task DolphinBench development slice, not a submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from research.production_benchmarks.dolphinbench import (  # noqa: E402
    evaluate_development,
    evaluate_development_diagnostic,
    require_completed_provider_response,
    verify_official_checkout,
)
from atmem.benchmark.finalization import validate_finalization_gate  # noqa: E402
from atmem.benchmark.attribution import validate_attribution_artifacts  # noqa: E402
from atmem.benchmark.contracts import load_json_compatible_yaml  # noqa: E402
from research.production_benchmarks.installed_product import (  # noqa: E402
    installed_atmem_identity,
)
from research.production_benchmarks.longmemeval_v2 import current_hardware_profile  # noqa: E402
from research.production_benchmarks.local_resources import (  # noqa: E402
    configure_local_resource_limits,
)


def validate_work_directory(actual: Path, configured_output: Path) -> None:
    """Bind official mutable run output separately from memory checkpoints."""
    if actual.expanduser().resolve() != configured_output.expanduser().resolve():
        raise RuntimeError(
            "official DolphinBench work directory differs from the configured output"
        )


def _call_openai_reasoning_judge(llm_judge, system_prompt: str,
                                 user_prompt: str, config: dict,
                                 timeout: int = 90) -> dict:
    """Use the current OpenAI request fields for the pinned reasoning judge."""
    model = config.get("judge_model", llm_judge.OPENAI_DEFAULT_MODEL)
    endpoint = config.get("judge_endpoint", llm_judge.OPENAI_DEFAULT_ENDPOINT)
    api_key_env = config.get("judge_key_env", llm_judge.OPENAI_API_KEY_ENV)
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Missing env var {api_key_env}")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "reasoning_effort": llm_judge.JUDGE_REASONING_EFFORT,
        "max_completion_tokens": llm_judge.DEFAULT_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        endpoint, method="POST", data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/hermes-agent",
            "X-Title": "DolphinBench Benchmark",
        },
    )
    started = time.monotonic()
    raw = llm_judge._urlopen_json(request, timeout, model=model)
    from graders.judge_recording import record_response
    record_response(
        {key: value for key, value in body.items() if key != "messages"},
        body["messages"], raw, (time.monotonic() - started) * 1000,
    )
    return llm_judge._extract_json(raw["choices"][0]["message"]["content"])


def _installed_artifact_sha256() -> str:
    """Hash the installed AtMem package, metadata, and entry point files."""
    return str(installed_atmem_identity()["artifact_sha256"])


def _tree_digest(root: Path, adapter: str | None = None) -> str:
    if not root.is_dir():
        raise RuntimeError(f"DolphinBench checkpoint root does not exist: {root}")
    include_atmem = adapter in (None, "research.production_benchmarks.dolphinbench:create_development")
    include_mem0 = adapter in (None, "research.production_benchmarks.dolphinbench:create_mem0_development")
    if not include_atmem and not include_mem0:
        raise RuntimeError("DolphinBench checkpoint digest received an unknown adapter")
    selected = [
        *sorted((root / "checkpoints").glob("*.json")),
        *([] if not include_atmem else sorted((root / "atmem-personas").glob("*.db"))),
        *([] if not include_atmem else sorted((root / "atmem-personas").glob("*.db-wal"))),
        *([] if not include_atmem else sorted((root / "atmem-personas").glob("*.db-shm"))),
        *([] if not include_atmem else sorted((root / "atmem-personas").glob("*.encryption.json"))),
        *([] if not include_mem0 else sorted(
            path for path in (root / "mem0-personas").rglob("*")
            if path.is_file() and not path.name.startswith("._") and path.name != ".DS_Store"
        )),
    ]
    files = {}
    for path in selected:
        if (
            not path.is_file()
            or path.name.startswith("._")
            or path.name == ".DS_Store"
        ):
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
    local_resources = configure_local_resource_limits()
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--finalization-gate")
    parser.add_argument(
        "--diagnostic-profile",
        help="predeclared frozen-subset profile for a non-score diagnostic run",
    )
    parser.add_argument("--checkpoint-root", required=True)
    parser.add_argument(
        "--finalization-manifest",
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
    diagnostic_profile_path = (
        Path(args.diagnostic_profile).expanduser().resolve()
        if args.diagnostic_profile else None
    )
    if not config.is_file():
        raise SystemExit(f"DolphinBench config does not exist: {config}")
    protocols = ROOT / "benchmarks/retrieval_quality/protocols"
    protocol = load_json_compatible_yaml(protocols / "2.3.8.yaml")
    longmem_profile = json.loads(
        (protocols / "longmemeval-v2-development-5pct-v1.json").read_text(encoding="utf-8")
    )
    dolphin_profile = json.loads(
        (protocols / "dolphinbench-development-5pct-v1.json").read_text(encoding="utf-8")
    )
    diagnostic_profile = None
    diagnostic_case_ids: set[str] | None = None
    diagnostic_profile_sha256 = None
    if diagnostic_profile_path is not None:
        diagnostic_profile = json.loads(
            diagnostic_profile_path.read_text(encoding="utf-8")
        )
        if diagnostic_profile.get("format") != "atmem-dolphinbench-remediation-development-v1":
            raise SystemExit("DolphinBench diagnostic profile format is invalid")
        diagnostic_case_ids = {str(value) for value in diagnostic_profile.get("case_ids") or ()}
        if (
            len(diagnostic_case_ids) != len(diagnostic_profile.get("case_ids") or ())
            or not diagnostic_case_ids
            or not diagnostic_case_ids <= set(dolphin_profile["development_ids"])
        ):
            raise SystemExit("DolphinBench diagnostic cases must be a unique frozen subset")
        source_manifest_path = protocols / str(diagnostic_profile.get("source_manifest") or "")
        source_manifest_sha256 = "sha256:" + hashlib.sha256(
            source_manifest_path.read_bytes()
        ).hexdigest()
        if source_manifest_sha256 != diagnostic_profile.get("source_manifest_sha256"):
            raise SystemExit("DolphinBench diagnostic source manifest hash differs")
        diagnostic_profile_sha256 = "sha256:" + hashlib.sha256(
            diagnostic_profile_path.read_bytes()
        ).hexdigest()
    attribution_artifacts = validate_attribution_artifacts(
        protocol,
        protocols_root=protocols,
        longmem_case_ids=longmem_profile["question_ids"],
        dolphin_case_ids=dolphin_profile["development_ids"],
    )
    official_checkout = verify_official_checkout(checkout, dolphin_profile)
    configuration = yaml.safe_load(config.read_text(encoding="utf-8"))
    if not isinstance(configuration, dict):
        raise SystemExit("DolphinBench config must be a YAML object")
    options = dict(configuration.get("options") or {})
    configured_checkout = Path(str(options.get("official_checkout") or "")).expanduser().resolve()
    if configured_checkout != checkout:
        raise SystemExit("DolphinBench config official checkout differs")
    adapter = str(configuration.get("adapter") or "")
    if adapter not in {
        "research.production_benchmarks.dolphinbench:create_development",
        "research.production_benchmarks.dolphinbench:create_mem0_development",
    }:
        raise SystemExit("DolphinBench config does not select a matched development adapter")
    if options.get("agent_driver") != "research.production_benchmarks.dolphin_openai_driver:run":
        raise SystemExit("DolphinBench config does not select the pinned agent driver")
    checkpoint_sha256 = _tree_digest(checkpoint_root, adapter)
    installed_product = installed_atmem_identity()
    if args.preflight_only:
        missing = [
            name for name in ("OPENAI_API_KEY", "RUN_POD")
            if not os.environ.get(name, "").strip()
        ]
        if missing:
            raise SystemExit(
                "DolphinBench preflight requires credentials: " + ", ".join(missing)
            )
        print(json.dumps({
            "format": "atmem-dolphinbench-development-preflight-v1",
            "status": "ready",
            "paid_egress_started": False,
            "official_checkout": official_checkout,
            "development_tasks": len(
                diagnostic_case_ids or dolphin_profile["development_ids"]
            ),
            "diagnostic_profile_sha256": diagnostic_profile_sha256,
            "adapter": adapter,
            "checkpoint_sha256": checkpoint_sha256,
            "installed_product": installed_product,
            "execution_topology": "mac-controller+runpod-gpu-reader",
            "local_resources": local_resources,
            "attribution_artifacts": {
                "review_protocol_sha256": attribution_artifacts[
                    "review_protocol"
                ]["review_protocol_sha256"],
                "manifest_sha256": attribution_artifacts[
                    "dolphinbench"
                ]["manifest"]["manifest_sha256"],
                "equivalence_sha256": attribution_artifacts[
                    "dolphinbench"
                ]["equivalence"]["receipt_sha256"],
            },
        }, indent=2, sort_keys=True))
        return 0
    if not args.finalization_gate or not args.finalization_manifest:
        raise SystemExit(
            "paid DolphinBench run requires --finalization-gate and "
            "--finalization-manifest"
        )
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
        "checkpoint_sha256": checkpoint_sha256,
        "hardware_profile": current_hardware_profile(),
        "gpu_execution_site": "runpod-only",
        "local_resources": local_resources,
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
    if diagnostic_profile_sha256 is not None:
        identity["diagnostic_profile_sha256"] = diagnostic_profile_sha256
    validate_finalization_gate(
        gate, expected_identity=identity, expected_gate_type="dolphinbench"
    )
    original = official_runner.Runner.evaluate
    original_init = official_runner.Runner.__init__
    original_urlopen_json = llm_judge._urlopen_json
    original_call_openai = llm_judge._call_openai
    driver_target = str(identity.get("agent_driver_target") or "")
    driver_sha256 = str(identity.get("agent_driver_sha256") or "")
    configured_output = Path(str(configuration.get("output") or "")).expanduser().resolve()
    if not str(configuration.get("output") or "").strip():
        raise RuntimeError("DolphinBench config does not declare an output directory")
    if not driver_target or not driver_sha256:
        raise RuntimeError("DolphinBench finalization must bind the agent driver")

    def checked_urlopen_json(*args, **kwargs):
        return require_completed_provider_response(
            original_urlopen_json(*args, **kwargs), role="grader"
        )

    def selected_evaluate(instance) -> None:
        validate_work_directory(Path(instance.directory), configured_output)
        if _tree_digest(checkpoint_root, adapter) != identity["checkpoint_sha256"]:
            raise RuntimeError("DolphinBench checkpoints changed after finalization")
        result = (
            evaluate_development_diagnostic(
                instance, checkout, case_ids=diagnostic_case_ids
            )
            if diagnostic_case_ids is not None
            else evaluate_development(instance, checkout)
        )
        print(
            f"Completed {result['tests']} frozen development tasks; "
            "this is not an official 600-task score."
        )

    def development_init(instance, *init_args, **init_kwargs) -> None:
        """Permit the manifest-bound OpenAI judge for this non-submission slice.

        The upstream runner intentionally accepts only its leaderboard Azure
        judge when paid execution is enabled.  This wrapper produces explicitly
        non-official 30-task development evidence, so it constructs the runner
        through the no-paid validation path and then enables the already-bound
        provider calls used by evaluation.
        """
        allow_paid = bool(init_kwargs.pop("allow_paid", False))
        original_init(instance, *init_args, allow_paid=False, **init_kwargs)
        instance.allow_paid = allow_paid

    official_runner.Runner.evaluate = selected_evaluate
    if llm_judge.BACKEND != "azure":
        official_runner.Runner.__init__ = development_init
        llm_judge._call_openai = lambda system_prompt, user_prompt, config, timeout=90: (
            _call_openai_reasoning_judge(
                llm_judge, system_prompt, user_prompt, config, timeout
            )
        )
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
        official_runner.Runner.__init__ = original_init
        llm_judge._urlopen_json = original_urlopen_json
        llm_judge._call_openai = original_call_openai
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
