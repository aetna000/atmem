"""Reproducible installer for the official inert LongMemEval-V2 adapter."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

from atmem.benchmark.contracts import validate_retrieval_quality_protocol
from atmem.service.household import HouseholdApplication
from research.production_benchmarks.cost_ledger import DurableCostLedger


PINNED_COMMIT = "2cc8c540bdb87fe6761629b585e727e1c4704520"
IMPORT_LINE = "from .atmem import AtMemMemory  # noqa: E402,F401"
METHOD_MARKER = 'METHODS = {\n    "atmem",'
METHOD_ORIGINAL = "METHODS = {"
CONFIG_MARKER = '''def build_memory_config(args: argparse.Namespace, data_root: Path) -> dict[str, object]:
    if args.method == "atmem":
        required = {
            name: os.environ.get(name, "").strip()
            for name in (
                "ATMEM_LME_DATABASE_PATH", "ATMEM_LME_SUBJECT_ID",
                "ATMEM_LME_AGENT_ID", "ATMEM_LME_WORKSPACE_ID",
            )
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise RuntimeError(f"AtMem LongMemEval environment is missing: {', '.join(missing)}")
        return {
            "memory_type": "atmem",
            "memory_params": {
                "database_path": required["ATMEM_LME_DATABASE_PATH"],
                "subject_id": required["ATMEM_LME_SUBJECT_ID"],
                "agent_id": required["ATMEM_LME_AGENT_ID"],
                "workspace_id": required["ATMEM_LME_WORKSPACE_ID"],
                "trajectory_pool_root": str(data_root),
                "require_encrypted": True,
            },
        }
'''
CONFIG_ORIGINAL = (
    "def build_memory_config(args: argparse.Namespace, data_root: Path) -> dict[str, object]:\n"
)
EVALUATOR_ARG_ORIGINAL = '    parser.add_argument("--evaluator-model", default=os.getenv("EVALUATOR_MODEL", "gpt-5.2"))\n'
EVALUATOR_ARG_MARKER = EVALUATOR_ARG_ORIGINAL + '    parser.add_argument("--evaluator-base-url", default=None)\n'
EVALUATOR_FORWARD_ORIGINAL = '    if not args.reader_enable_thinking:\n'
EVALUATOR_FORWARD_MARKER = (
    '    if args.evaluator_base_url:\n'
    '        harness_argv.extend(["--evaluator-base-url", args.evaluator_base_url])\n'
    + EVALUATOR_FORWARD_ORIGINAL
)
RETRY_ORIGINAL = "OPENAI_MAX_RETRIES = 10\n"
RETRY_MARKER = "OPENAI_MAX_RETRIES = 0  # AtMem paid-pilot egress cap\n"
LLM_EVALUATORS = {"llm_abstention_checker", "llm_gotchas_checker"}
NONSECRET_CHILD_ENVIRONMENT = {
    "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "PYTHONDONTWRITEBYTECODE",
}


def _proxy_environment(environment: dict[str, str], credential: str) -> dict[str, str]:
    return {
        name: value for name, value in environment.items()
        if name in NONSECRET_CHILD_ENVIRONMENT or name == credential
    }


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_for_proxy(
    process: subprocess.Popen[bytes], ready_file: Path, *, label: str
) -> str:
    for _ in range(100):
        if ready_file.is_file():
            try:
                payload = json.loads(ready_file.read_text(encoding="utf-8"))
                base_url = str(payload["base_url"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                pass
            else:
                if base_url.startswith("http://127.0.0.1:"):
                    return base_url
                raise RuntimeError(f"{label} proxy advertised a non-loopback endpoint")
        if process.poll() is not None:
            raise RuntimeError(f"{label} proxy exited before readiness")
        time.sleep(0.05)
    raise RuntimeError(f"{label} proxy did not become ready")


def preflight_paid_runtime(
    protocol: dict[str, Any],
    *,
    methods: tuple[str, ...],
    environment: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate credentials, proxy code, and reservations without writing output."""
    supplied = dict(environment or {})
    credentials = {
        name: supplied.get(name) or os.environ.get(name, "")
        for name in ("HF_TOKEN", "OPENAI_API_KEY")
    }
    missing = sorted(name for name, value in credentials.items() if not value.strip())
    if missing:
        raise RuntimeError(
            "paid pilot requires credentials: " + ", ".join(missing)
        )
    requirements = dict(protocol["paid_run_requirements"])
    packages = requirements.get("official_runtime_packages")
    if not isinstance(packages, dict) or not packages:
        raise RuntimeError("paid pilot requires pinned official runtime packages")
    for distribution, expected in sorted(packages.items()):
        try:
            actual = package_version(str(distribution))
        except PackageNotFoundError as exc:
            raise RuntimeError(
                f"paid pilot requires official runtime package {distribution}=={expected}"
            ) from exc
        if actual != str(expected):
            raise RuntimeError(
                "paid pilot official runtime package differs from the frozen "
                f"protocol: {distribution}=={actual}, expected {expected}"
            )
    sources = {
        "embedding_proxy_sha256": Path(__file__).with_name("hf_embedding_proxy.py"),
        "judge_proxy_sha256": Path(__file__).with_name("openai_judge_proxy.py"),
    }
    result: dict[str, str] = {}
    for field, source in sources.items():
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != requirements.get(field):
            raise RuntimeError(f"paid pilot {field} differs from the frozen protocol")
        result[field] = digest
    reservations = dict(requirements.get("pilot_method_reservations_usd") or {})
    endpoint_runtime_billing = (
        dict(requirements.get("huggingface_reader_billing") or {}).get("mode")
        == "endpoint-runtime"
    )
    for method in methods:
        amounts = reservations.get(method)
        if (
            not isinstance(amounts, dict)
            or (
                not endpoint_runtime_billing
                and float(amounts.get("huggingface", 0)) <= 0
            )
            or float(amounts.get("openai", 0)) < 0
        ):
            raise RuntimeError(
                f"pilot method has no price-derived reservation: {method}"
            )
    return result


def _preflight_official_harness_import(
    root: Path, environment: dict[str, str]
) -> None:
    """Import the complete official harness before reserving paid capacity."""

    checked = subprocess.run(
        [os.sys.executable, "-c", "import evaluation.harness"],
        cwd=root,
        env={**environment, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
    )
    if checked.returncode != 0:
        detail = (checked.stderr or checked.stdout).strip().splitlines()
        suffix = detail[-1] if detail else f"exit code {checked.returncode}"
        raise RuntimeError(f"official LongMemEval harness import failed: {suffix}")


@dataclass(frozen=True)
class DatasetPreflight:
    data_root: Path
    dataset_revision: str
    question_ids: frozenset[str]
    trajectory_count: int
    trajectory_screenshot_count: int
    question_image_count: int
    selected_input_manifest_sha256: str

    def report(self) -> dict[str, Any]:
        return {
            "format": "atmem-longmemeval-v2-data-preflight-v1",
            "dataset_revision": self.dataset_revision,
            "question_count": len(self.question_ids),
            "trajectory_count": self.trajectory_count,
            "trajectory_screenshot_count": self.trajectory_screenshot_count,
            "question_image_count": self.question_image_count,
            "selected_input_manifest_sha256": self.selected_input_manifest_sha256,
            "content_retained": False,
        }


def preflight_selected_data(
    data_root: str | Path,
    question_ids: list[str],
    *,
    dataset_revision: str,
    expected_sha256: dict[str, str],
) -> DatasetPreflight:
    """Prove selected official inputs are complete before output or paid egress."""
    root = Path(data_root).expanduser().resolve()
    haystack_path = root / "haystacks" / "lme_v2_small.json"
    trajectories_path = root / "trajectories.jsonl"
    questions_path = root / "questions.jsonl"
    for required in (haystack_path, trajectories_path, questions_path):
        if not required.is_file():
            raise RuntimeError(f"official dataset input is missing: {required.name}")
    required_hashes = {
        "questions.jsonl": questions_path,
        "trajectories.jsonl": trajectories_path,
        "haystacks/lme_v2_small.json": haystack_path,
        "checksums.sha256": root / "checksums.sha256",
    }
    if set(expected_sha256) != set(required_hashes):
        raise RuntimeError("official dataset content pins are incomplete")
    for relative, path in required_hashes.items():
        if not path.is_file() or _sha256(path) != expected_sha256[relative]:
            raise RuntimeError(
                f"official dataset content differs from pinned revision: {relative}"
            )

    haystacks = json.loads(haystack_path.read_text(encoding="utf-8"))
    selected = frozenset(str(value) for value in question_ids)
    missing_questions = sorted(selected - set(haystacks))
    if missing_questions:
        raise RuntimeError(
            "pilot questions are missing from the official small haystack: "
            + ", ".join(missing_questions)
        )
    required_trajectories = {
        str(trajectory_id)
        for question_id in selected
        for trajectory_id in haystacks[question_id]
    }
    question_rows: dict[str, dict[str, Any]] = {}
    with questions_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            question_id = str(row.get("id") or "")
            if question_id in selected:
                question_rows[question_id] = row
    if set(question_rows) != set(selected):
        raise RuntimeError("pilot questions are missing from questions.jsonl")

    seen: set[str] = set()
    screenshot_count = 0
    manifest = hashlib.sha256()

    def add_manifest_part(label: str, value: bytes) -> None:
        encoded_label = label.encode("utf-8")
        manifest.update(len(encoded_label).to_bytes(8, "big"))
        manifest.update(encoded_label)
        manifest.update(len(value).to_bytes(8, "big"))
        manifest.update(value)

    for question_id in sorted(question_rows):
        add_manifest_part(
            f"question:{question_id}",
            json.dumps(
                question_rows[question_id],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8"),
        )
    hashed_media: set[Path] = set()
    with trajectories_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            trajectory_id = str(row.get("id") or "")
            if trajectory_id not in required_trajectories:
                continue
            seen.add(trajectory_id)
            add_manifest_part(
                f"trajectory:{trajectory_id}",
                json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8"),
            )
            for state in row.get("states") or []:
                if not isinstance(state, dict):
                    continue
                screenshot = state.get("screenshot")
                if not isinstance(screenshot, str) or not screenshot:
                    continue
                resolved = (root / screenshot).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError as exc:
                    raise RuntimeError(
                        "official screenshot path escapes the dataset root"
                    ) from exc
                if not resolved.is_file():
                    raise RuntimeError(
                        "official pilot screenshots are not prepared; run the pinned "
                        "data/prepare_data.py before any paid pilot"
                    )
                screenshot_count += 1
                if resolved not in hashed_media:
                    add_manifest_part(f"media:{screenshot}", _sha256(resolved).encode())
                    hashed_media.add(resolved)
    missing_trajectories = sorted(required_trajectories - seen)
    if missing_trajectories:
        raise RuntimeError(
            "official pilot trajectories are missing: "
            + ", ".join(missing_trajectories[:10])
        )

    question_image_count = 0
    for row in question_rows.values():
        image = row.get("image")
        if not isinstance(image, str) or not image:
            continue
        resolved = (root / image).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("official question image escapes the dataset root") from exc
        if not resolved.is_file():
            raise RuntimeError("official pilot question images are not prepared")
        question_image_count += 1
        if resolved not in hashed_media:
            add_manifest_part(f"media:{image}", _sha256(resolved).encode())
            hashed_media.add(resolved)

    return DatasetPreflight(
        data_root=root,
        dataset_revision=dataset_revision,
        question_ids=selected,
        trajectory_count=len(required_trajectories),
        trajectory_screenshot_count=screenshot_count,
        question_image_count=question_image_count,
        selected_input_manifest_sha256=manifest.hexdigest(),
    )


def current_hardware_profile() -> str:
    if platform.system() != "Darwin":
        raise RuntimeError("the frozen paid pilot hardware profile requires macOS")
    arm64 = subprocess.run(
        ["sysctl", "-n", "hw.optional.arm64"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    architecture = "arm64" if arm64 == "1" else platform.machine()
    cpu = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"],
        check=True, capture_output=True, text=True,
    ).stdout.strip().replace(" ", "-")
    build = subprocess.run(
        ["sw_vers", "-buildVersion"], check=True, capture_output=True, text=True
    ).stdout.strip()
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return (
        f"{cpu};{architecture};{memory}-bytes;"
        f"macOS-{platform.mac_ver()[0]}-build-{build}"
    )


def install_official_adapter(checkout: str | Path) -> dict[str, str]:
    root = Path(checkout).expanduser().resolve()
    verification = verify_official_checkout(root)
    head = verification["source_commit"]
    if head != PINNED_COMMIT:
        raise RuntimeError(f"LongMemEval-V2 checkout must be {PINNED_COMMIT}; found {head}")
    source = Path(__file__).with_name("adapters") / "longmemeval_atmem.py"
    destination = root / "memory_modules" / "atmem.py"
    registry = root / "memory_modules" / "memory.py"
    runner = root / "evaluation" / "run_eval.py"
    retry_files = (
        root / "evaluation" / "harness.py",
        root / "evaluation" / "qa_eval_metrics.py",
    )
    if not registry.is_file():
        raise FileNotFoundError(f"official memory registry missing: {registry}")
    destination.write_bytes(source.read_bytes())
    text = registry.read_text(encoding="utf-8")
    if IMPORT_LINE not in text:
        registry.write_text(text.rstrip() + "\n" + IMPORT_LINE + "\n", encoding="utf-8")
    runner_text = runner.read_text(encoding="utf-8")
    if METHOD_MARKER not in runner_text:
        if METHOD_ORIGINAL not in runner_text:
            raise RuntimeError("official run_eval METHODS marker changed")
        runner_text = runner_text.replace(METHOD_ORIGINAL, METHOD_MARKER, 1)
    if CONFIG_MARKER not in runner_text:
        if CONFIG_ORIGINAL not in runner_text:
            raise RuntimeError("official run_eval memory-config marker changed")
        runner_text = runner_text.replace(CONFIG_ORIGINAL, CONFIG_MARKER, 1)
    if EVALUATOR_ARG_MARKER not in runner_text:
        if EVALUATOR_ARG_ORIGINAL not in runner_text:
            raise RuntimeError("official run_eval evaluator argument marker changed")
        runner_text = runner_text.replace(
            EVALUATOR_ARG_ORIGINAL, EVALUATOR_ARG_MARKER, 1
        )
    if EVALUATOR_FORWARD_MARKER not in runner_text:
        if runner_text.count(EVALUATOR_FORWARD_ORIGINAL) != 1:
            raise RuntimeError("official run_eval evaluator forwarding marker changed")
        runner_text = runner_text.replace(
            EVALUATOR_FORWARD_ORIGINAL, EVALUATOR_FORWARD_MARKER, 1
        )
    runner.write_text(runner_text, encoding="utf-8")
    for retry_file in retry_files:
        retry_text = retry_file.read_text(encoding="utf-8")
        if RETRY_MARKER not in retry_text:
            if retry_text.count(RETRY_ORIGINAL) != 1:
                raise RuntimeError(
                    f"official retry marker changed: {retry_file.relative_to(root)}"
                )
            retry_file.write_text(
                retry_text.replace(RETRY_ORIGINAL, RETRY_MARKER, 1),
                encoding="utf-8",
            )
    installed = verify_installed_adapter(root)
    return {
        "format": "atmem-longmemeval-v2-adapter-install-v1",
        "source_commit": head,
        "adapter_path": str(destination),
        "adapter_sha256": _sha256(destination),
        "registry_sha256": _sha256(registry),
        "runner_sha256": _sha256(runner),
        "runtime_verified": str(installed["runtime_verified"]),
        "official_code_combined_sha256": verification[
            "official_code_combined_sha256"
        ],
    }


def verify_official_checkout(checkout: str | Path) -> dict[str, str]:
    """Verify frozen git blobs and reject unexpected working-tree changes."""
    root = Path(checkout).expanduser().resolve()
    head = _git_head(root)
    if head != PINNED_COMMIT:
        raise RuntimeError(f"LongMemEval-V2 checkout must be {PINNED_COMMIT}; found {head}")
    protocol_path = (
        Path(__file__).resolve().parents[2]
        / "benchmarks/retrieval_quality/protocols/2.3.8.yaml"
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    requirements = dict(protocol["paid_run_requirements"])
    files = dict(requirements["official_code_files"])
    actual = {
        name: hashlib.sha256(_git_blob(root, name)).hexdigest()
        for name in files
    }
    if actual != files:
        raise RuntimeError("official LongMemEval-V2 source files differ from frozen pins")
    _verify_worktree_shape(root)
    for name, digest in files.items():
        path = root / name
        if not path.is_file():
            raise RuntimeError(f"official LongMemEval-V2 working-tree file is missing: {name}")
        working_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if working_digest == digest:
            continue
        if name == "memory_modules/memory.py" and _is_expected_registry_patch(
            root, path
        ):
            continue
        if name == "evaluation/run_eval.py" and _is_expected_runner_patch(root, path):
            continue
        if name in {"evaluation/harness.py", "evaluation/qa_eval_metrics.py"} and (
            _is_expected_retry_patch(root, path, name)
        ):
            continue
        raise RuntimeError(
            f"official LongMemEval-V2 working-tree file differs unexpectedly: {name}"
        )
    combined = hashlib.sha256(
        json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if combined != requirements["official_code_combined_sha256"]:
        raise RuntimeError("official LongMemEval-V2 combined source pin differs")
    harness = _git_blob(root, "evaluation/harness.py")
    tree = ast.parse(harness.decode("utf-8"))
    prompts = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "DOMAIN_SYSTEM_PROMPTS"
            for target in node.targets
        ):
            prompts = ast.literal_eval(node.value)
            break
    if prompts is None:
        raise RuntimeError("official reader prompts were not found")
    prompt_digest = hashlib.sha256(
        json.dumps(
            prompts, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    if prompt_digest != requirements["reader_prompt_sha256"]:
        raise RuntimeError("official reader prompt differs from frozen pin")
    comparator = hashlib.sha256(
        _git_blob(root, "evaluation/memory_configs/rag_query_to_slice_notes.json")
    ).hexdigest()
    if comparator != requirements["comparator_config_sha256"]:
        raise RuntimeError("official comparator config differs from frozen pin")
    return {
        "source_commit": head,
        "reader_prompt_sha256": prompt_digest,
        "official_code_combined_sha256": combined,
        "comparator_config_sha256": comparator,
    }


def verify_installed_adapter(checkout: str | Path) -> dict[str, Any]:
    root = Path(checkout).expanduser().resolve()
    verification = verify_official_checkout(root)
    adapter = root / "memory_modules" / "atmem.py"
    registry = root / "memory_modules" / "memory.py"
    runner = root / "evaluation" / "run_eval.py"
    expected_adapter = Path(__file__).with_name("adapters") / "longmemeval_atmem.py"
    if not adapter.is_file() or adapter.read_bytes() != expected_adapter.read_bytes():
        raise RuntimeError("installed AtMem adapter differs from the reviewed source")
    if not _is_expected_registry_patch(root, registry):
        raise RuntimeError("official LongMemEval registry has not loaded the AtMem adapter")
    if not _is_expected_runner_patch(root, runner):
        raise RuntimeError("official LongMemEval runner has not enabled the AtMem adapter")
    if not _is_expected_retry_patch(
        root, root / "evaluation/harness.py", "evaluation/harness.py"
    ):
        raise RuntimeError("official LongMemEval reader retries are not safely bounded")
    if not _is_expected_retry_patch(
        root,
        root / "evaluation/qa_eval_metrics.py",
        "evaluation/qa_eval_metrics.py",
    ):
        raise RuntimeError("official LongMemEval judge retries are not safely bounded")
    return {**verification, "runtime_verified": True}


def run_official_pilot_case(
    checkout: str | Path, *, data_root: str | Path, output_root: str | Path,
    question_id: str, domain: str, method: str,
    protocol_path: str | Path, question_split: dict, pilot: dict,
    dolphin_split: dict, route_probe: dict, environment: dict[str, str] | None = None,
    confirmed_paid_run: bool = False,
    data_preflight: DatasetPreflight | None = None,
    shared_hf_runtime_reservation: bool = False,
    judge_gate_file: str | Path | None = None,
) -> dict[str, Any]:
    """Run one frozen case through the official executable with durable spend guards."""
    root = Path(checkout).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    validate_retrieval_quality_protocol(
        protocol, split=question_split, pilot=pilot,
        dolphin_split=dolphin_split, route_probe=route_probe,
        for_pilot_run=True, external_root=output,
        repository_root=Path(__file__).resolve().parents[2],
    )
    if not confirmed_paid_run:
        raise RuntimeError("paid pilot requires an explicit confirmed_paid_run flag")
    supplied = dict(environment or {})
    benchmark_root_value = (
        supplied.get("ATMEM_BENCHMARK_ROOT")
        or os.environ.get("ATMEM_BENCHMARK_ROOT", "")
    ).strip()
    if not benchmark_root_value:
        raise RuntimeError(
            "paid pilot requires ATMEM_BENCHMARK_ROOT for the shared cost ledger"
        )
    benchmark_root = Path(benchmark_root_value).expanduser().resolve()
    try:
        output.relative_to(benchmark_root)
    except ValueError as exc:
        raise RuntimeError(
            "paid pilot output must be inside ATMEM_BENCHMARK_ROOT"
        ) from exc
    verify_installed_adapter(root)
    allowed = set(pilot["question_ids"])
    if question_id not in allowed:
        raise ValueError("question is not in the frozen development pilot")
    resolved_data_root = Path(data_root).expanduser().resolve()
    dataset_pin = dict(protocol["datasets"]["longmemeval_v2"])
    if data_preflight is None:
        data_preflight = preflight_selected_data(
            resolved_data_root,
            [str(value) for value in pilot["question_ids"]],
            dataset_revision=str(dataset_pin["dataset_revision"]),
            expected_sha256=dict(dataset_pin["content_sha256"]),
        )
    if (
        data_preflight.data_root != resolved_data_root
        or data_preflight.question_ids != frozenset(str(value) for value in pilot["question_ids"])
        or data_preflight.dataset_revision != dataset_pin["dataset_revision"]
        or data_preflight.selected_input_manifest_sha256
        != pilot.get("selected_input_manifest_sha256")
    ):
        raise RuntimeError("paid pilot case lacks a matching verified data preflight")
    if domain not in {"web", "enterprise"}:
        raise ValueError("domain must be web or enterprise")
    method_map = {
        "no-retrieval": "no_retrieval",
        "official-rag-query-to-slice-notes": "rag_query_to_slice_notes",
        "typed-local": "atmem",
    }
    if method not in method_map:
        raise ValueError("pilot method is not an executable frozen operating point")
    requirements = protocol["paid_run_requirements"]
    reader_billing = dict(requirements.get("huggingface_reader_billing") or {})
    endpoint_runtime_billing = reader_billing.get("mode") == "endpoint-runtime"
    if endpoint_runtime_billing and not shared_hf_runtime_reservation:
        raise RuntimeError(
            "dedicated-endpoint pilot cases require the batch runtime reservation"
        )
    preflight_paid_runtime(protocol, methods=(method,), environment=supplied)
    actual_hardware = current_hardware_profile()
    if actual_hardware != requirements.get("hardware_profile"):
        raise RuntimeError(
            "paid pilot hardware differs from the frozen protocol: "
            f"{actual_hardware}"
        )
    proxy_source = Path(__file__).with_name("hf_embedding_proxy.py")
    judge_proxy_source = Path(__file__).with_name("openai_judge_proxy.py")
    reservations = requirements["pilot_method_reservations_usd"].get(method)
    if not isinstance(reservations, dict):  # guarded by the no-write preflight
        raise AssertionError("missing preflighted method reservation")
    case_key = f"longmem:{question_id}:{method}"
    protocol_digest = hashlib.sha256(
        json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    shared_ledger_root = benchmark_root / "cost-ledgers" / protocol_digest
    hf_ledger = DurableCostLedger(
        shared_ledger_root / "longmem-hf-cost-ledger.json",
        total_cap_usd=float(requirements["pilot_hf_cost_cap_usd"]),
    )
    openai_ledger = DurableCostLedger(
        shared_ledger_root / "longmem-openai-cost-ledger.json",
        total_cap_usd=float(requirements["pilot_openai_cost_cap_usd"]),
    )
    hf_key = f"{case_key}:hf"
    judge_key = f"{case_key}:openai"
    hf_max = float(reservations.get("huggingface", 0) or 0)
    judge_max = float(reservations["openai"])
    case_output = output / "runs" / question_id / method
    allowed_environment = {
        "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
        "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "HF_TOKEN", "OPENAI_API_KEY",
        "ATMEM_BENCHMARK_ROOT",
    }
    forbidden = sorted(set(supplied) - allowed_environment)
    if forbidden:
        raise ValueError(
            "pilot environment contains non-allowlisted variables: "
            + ", ".join(forbidden)
        )
    run_environment = {
        name: value for name, value in os.environ.items()
        if name in allowed_environment
    }
    run_environment.update(supplied)
    run_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if not run_environment.get("HF_TOKEN") or not run_environment.get("OPENAI_API_KEY"):
        raise RuntimeError("paid pilot requires HF_TOKEN and OPENAI_API_KEY")
    _preflight_official_harness_import(root, run_environment)
    case_output.mkdir(parents=True, exist_ok=False)
    models = protocol["models"]
    run_environment.update({
        "ATMEM_LME_DATABASE_PATH": str(case_output / "atmem.db"),
        "ATMEM_LME_SUBJECT_ID": "longmemeval-public",
        "ATMEM_LME_AGENT_ID": "longmemeval-v2",
        "ATMEM_LME_WORKSPACE_ID": f"{domain}-small",
        "ATMEM_JUDGE_PROXY_KEY": "local-proxy",
    })
    if method == "typed-local":
        HouseholdApplication.initialize(
            case_output / "atmem.db", encrypted=True, backend="file"
        )
    if not endpoint_runtime_billing:
        hf_ledger.reserve(hf_key, provider="huggingface", maximum_usd=hf_max)
    openai_ledger.reserve(judge_key, provider="openai", maximum_usd=judge_max)
    embedding_base_url = models["official_rag_embedding"]["base_url"]
    proxy: subprocess.Popen[bytes] | None = None
    judge_proxy: subprocess.Popen[bytes] | None = None
    judge_usage = case_output / "judge-usage.json"
    try:
        if method == "official-rag-query-to-slice-notes":
            ready_file = case_output / "embedding-proxy-ready.json"
            proxy = subprocess.Popen(
                [os.sys.executable, os.fspath(proxy_source), "--ready-file", os.fspath(ready_file)],
                cwd=case_output, env=_proxy_environment(run_environment, "HF_TOKEN"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            embedding_base_url = _wait_for_proxy(proxy, ready_file, label="HF embedding")
        judge_ready = case_output / "judge-proxy-ready.json"
        judge_proxy_command = [
                os.sys.executable, os.fspath(judge_proxy_source),
                "--ready-file", os.fspath(judge_ready),
                "--usage-file", os.fspath(judge_usage),
            ]
        if judge_gate_file is not None:
            judge_proxy_command.extend(
                ["--gate-file", os.fspath(Path(judge_gate_file).resolve())]
            )
        judge_proxy = subprocess.Popen(
            judge_proxy_command,
            cwd=case_output,
            env=_proxy_environment(run_environment, "OPENAI_API_KEY"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        evaluator_base_url = _wait_for_proxy(
            judge_proxy, judge_ready, label="OpenAI judge"
        )
        command = [
            os.fspath(Path(os.sys.executable)), os.fspath(root / "evaluation/run_eval.py"),
            "--data-root", os.fspath(resolved_data_root),
            "--domain", domain, "--tier", "small", "--method", method_map[method],
            "--output-dir", os.fspath(case_output), "--question-ids", question_id,
            "--reader-model", models["longmemeval_reader"]["model"],
            "--reader-base-url", models["longmemeval_reader"]["base_url"],
            "--reader-api-key-env", "HF_TOKEN",
            "--reader-temperature", str(models["longmemeval_reader"]["temperature"]),
            "--reader-top-p", str(models["longmemeval_reader"]["top_p"]),
            "--reader-top-k", str(models["longmemeval_reader"]["top_k"]),
            *(
                ["--reader-enable-thinking"]
                if models["longmemeval_reader"]["enable_thinking"]
                else []
            ),
            "--max-completion-tokens", str(
                models["longmemeval_reader"]["max_completion_tokens"]
            ),
            "--memory-context-max-tokens", str(
                models["longmemeval_reader"]["memory_context_max_tokens"]
            ),
            "--controller-model", models["official_rag_controller"]["model"],
            "--controller-base-url", models["official_rag_controller"]["base_url"],
            "--controller-api-key-env", "HF_TOKEN",
            "--controller-temperature", str(models["official_rag_controller"]["temperature"]),
            "--controller-top-p", str(models["official_rag_controller"]["top_p"]),
            "--controller-top-k", str(models["official_rag_controller"]["top_k"]),
            "--embedding-model", models["official_rag_embedding"]["model"],
            "--embedding-base-url", embedding_base_url,
            "--embedding-api-key-env", "HF_TOKEN",
            "--evaluator-model", models["longmemeval_judge"]["model"],
            "--evaluator-base-url", evaluator_base_url,
            "--evaluator-api-key-env", "ATMEM_JUDGE_PROXY_KEY",
            "--evaluator-reasoning-effort",
            models["longmemeval_judge"]["reasoning_effort"],
            "--evaluator-max-completion-tokens",
            str(models["longmemeval_judge"]["max_completion_tokens"]),
        ]
        harness_environment = dict(run_environment)
        harness_environment.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            command, cwd=root, env=harness_environment, check=False
        )
    finally:
        _stop_process(proxy)
        _stop_process(judge_proxy)
    if completed.returncode != 0:
        raise RuntimeError(
            f"official LongMemEval case failed with exit code {completed.returncode}; "
            "reservations remain consumed and retry requires explicit reconciliation"
        )
    case_row = _read_case_row(case_output)
    reader_usage = _reader_usage(case_row)
    if endpoint_runtime_billing:
        hf_cost = None
    else:
        reader_rates = requirements["huggingface_reader_price_usd_per_million"]
        hf_cost = (
            reader_usage["prompt_tokens"] * float(reader_rates["input"])
            + reader_usage["completion_tokens"] * float(reader_rates["output"])
        ) / 1_000_000
    judge = _judge_usage(case_row, judge_usage, reservation_usd=judge_max)
    if not endpoint_runtime_billing:
        hf_ledger.complete(hf_key, cost_usd=float(hf_cost))
    openai_ledger.complete(judge_key, cost_usd=float(judge["cost_usd"]))
    return {
        "format": "atmem-longmemeval-pilot-case-v1",
        "question_id": question_id, "domain": domain, "method": method,
        "output_dir": str(case_output),
        "cost_accounting": (
            "shared-endpoint-runtime" if endpoint_runtime_billing
            else "provider-token-usage"
        ),
        "hf_cost_usd": None if hf_cost is None else round(hf_cost, 9),
        "openai_cost_usd": float(judge["cost_usd"]),
        "reader_usage": reader_usage,
        "judge_usage": {key: judge[key] for key in (
            "requests", "prompt_tokens", "completion_tokens"
        )},
    }


def _is_expected_runner_patch(root: Path, path: Path) -> bool:
    original = _git_blob(root, "evaluation/run_eval.py").decode("utf-8")
    expected = original.replace(METHOD_ORIGINAL, METHOD_MARKER, 1).replace(
        CONFIG_ORIGINAL, CONFIG_MARKER, 1
    ).replace(EVALUATOR_ARG_ORIGINAL, EVALUATOR_ARG_MARKER, 1).replace(
        EVALUATOR_FORWARD_ORIGINAL, EVALUATOR_FORWARD_MARKER, 1
    )
    return path.read_text(encoding="utf-8") == expected


def _is_expected_retry_patch(root: Path, path: Path, git_name: str) -> bool:
    original = _git_blob(root, git_name).decode("utf-8")
    expected = original.replace(RETRY_ORIGINAL, RETRY_MARKER, 1)
    return path.read_text(encoding="utf-8") == expected


def _read_case_row(case_output: Path) -> dict[str, Any]:
    path = case_output / "per_question.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(rows) != 1:
        raise RuntimeError("official pilot case must produce exactly one result row")
    return rows[0]


def _reader_usage(row: dict[str, Any]) -> dict[str, int]:
    usage = row.get("usage") or {}
    result = {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
    }
    if result["prompt_tokens"] <= 0 or result["completion_tokens"] < 0:
        raise RuntimeError("official reader did not report valid token usage")
    return result


def _judge_usage(
    case_row: dict[str, Any], usage_path: Path, *, reservation_usd: float
) -> dict[str, Any]:
    if usage_path.is_file():
        return json.loads(usage_path.read_text(encoding="utf-8"))
    if case_row.get("eval_function") in LLM_EVALUATORS:
        return {
            "requests": 1,
            "prompt_tokens": None,
            "completion_tokens": None,
            "cost_usd": reservation_usd,
            "state": "usage_missing_after_required_judge",
        }
    return {
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
        "state": "not_required",
    }


def _is_expected_registry_patch(root: Path, path: Path) -> bool:
    expected = (
        _git_blob(root, "memory_modules/memory.py").decode("utf-8").rstrip()
        + "\n"
        + IMPORT_LINE
        + "\n"
    )
    return path.read_text(encoding="utf-8") == expected


def _verify_worktree_shape(root: Path) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--ignored", "--untracked-files=all"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    allowed = {
        " M evaluation/run_eval.py",
        " M evaluation/harness.py",
        " M evaluation/qa_eval_metrics.py",
        " M memory_modules/memory.py",
        "?? memory_modules/atmem.py",
    }
    dangerous_suffixes = (".pyc", ".pyo", ".so", ".pyd", ".dll", ".dylib")
    unexpected = sorted(
        line for line in status
        if line not in allowed
        and (
            not line.startswith("!! ")
            or line[3:].endswith(dangerous_suffixes)
            or line[3:].startswith(("lib/", "lib64/"))
        )
    )
    if unexpected:
        raise RuntimeError(
            "LongMemEval-V2 checkout has unexpected working-tree changes: "
            + ", ".join(unexpected)
        )


def _git_head(root: Path) -> str:
    import subprocess
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _git_blob(root: Path, name: str) -> bytes:
    import subprocess
    return subprocess.run(
        ["git", "show", f"HEAD:{name}"], cwd=root, check=True,
        capture_output=True,
    ).stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
