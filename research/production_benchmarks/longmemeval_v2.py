"""Reproducible installer for the official inert LongMemEval-V2 adapter."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
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
                "trajectory_pool_root": str(data_root / "trajectories"),
                "require_encrypted": True,
            },
        }
'''
CONFIG_ORIGINAL = (
    "def build_memory_config(args: argparse.Namespace, data_root: Path) -> dict[str, object]:\n"
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
    runner.write_text(runner_text, encoding="utf-8")
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
    return {**verification, "runtime_verified": True}


def run_official_pilot_case(
    checkout: str | Path, *, data_root: str | Path, output_root: str | Path,
    question_id: str, domain: str, method: str,
    protocol_path: str | Path, question_split: dict, pilot: dict,
    dolphin_split: dict, route_probe: dict, environment: dict[str, str] | None = None,
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
    verify_installed_adapter(root)
    allowed = set(pilot["question_ids"])
    if question_id not in allowed:
        raise ValueError("question is not in the frozen development pilot")
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
    proxy_source = Path(__file__).with_name("hf_embedding_proxy.py")
    proxy_digest = hashlib.sha256(proxy_source.read_bytes()).hexdigest()
    if proxy_digest != requirements.get("embedding_proxy_sha256"):
        raise RuntimeError("HF embedding proxy differs from the frozen protocol")
    case_key = f"longmem:{question_id}:{method}"
    hf_ledger = DurableCostLedger(
        output / "evidence" / "longmem-hf-cost-ledger.json",
        total_cap_usd=float(requirements["pilot_hf_cost_cap_usd"]),
    )
    openai_ledger = DurableCostLedger(
        output / "evidence" / "longmem-openai-cost-ledger.json",
        total_cap_usd=float(requirements["pilot_openai_cost_cap_usd"]),
    )
    hf_key = f"{case_key}:hf"
    judge_key = f"{case_key}:openai"
    hf_max = float(requirements["pilot_hf_case_reservation_usd"])
    judge_max = float(requirements["pilot_openai_case_reservation_usd"])
    hf_ledger.reserve(hf_key, provider="huggingface", maximum_usd=hf_max)
    openai_ledger.reserve(judge_key, provider="openai", maximum_usd=judge_max)
    case_output = output / "runs" / question_id / method
    case_output.mkdir(parents=True, exist_ok=False)
    allowed_environment = {
        "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
        "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "HF_TOKEN", "OPENAI_API_KEY",
    }
    supplied = dict(environment or {})
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
    models = protocol["models"]
    run_environment.update({
        "ATMEM_LME_DATABASE_PATH": str(case_output / "atmem.db"),
        "ATMEM_LME_SUBJECT_ID": "longmemeval-public",
        "ATMEM_LME_AGENT_ID": "longmemeval-v2",
        "ATMEM_LME_WORKSPACE_ID": f"{domain}-small",
    })
    if method == "typed-local":
        HouseholdApplication.initialize(
            case_output / "atmem.db", encrypted=True, backend="file"
        )
    embedding_base_url = models["official_rag_embedding"]["base_url"]
    proxy: subprocess.Popen[bytes] | None = None
    if method == "official-rag-query-to-slice-notes":
        ready_file = case_output / "embedding-proxy-ready.json"
        proxy = subprocess.Popen(
            [os.sys.executable, os.fspath(proxy_source), "--ready-file", os.fspath(ready_file)],
            cwd=case_output, env=run_environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if ready_file.is_file():
                break
            if proxy.poll() is not None:
                raise RuntimeError("HF embedding proxy exited before readiness")
            time.sleep(0.05)
        else:
            proxy.terminate()
            raise RuntimeError("HF embedding proxy did not become ready")
        embedding_base_url = json.loads(
            ready_file.read_text(encoding="utf-8")
        )["base_url"]
    command = [
        os.fspath(Path(os.sys.executable)), os.fspath(root / "evaluation/run_eval.py"),
        "--data-root", os.fspath(Path(data_root).expanduser().resolve()),
        "--domain", domain, "--tier", "small", "--method", method_map[method],
        "--output-dir", os.fspath(case_output), "--question-ids", question_id,
        "--reader-model", models["longmemeval_reader"]["model"],
        "--reader-base-url", models["longmemeval_reader"]["base_url"],
        "--reader-api-key-env", "HF_TOKEN",
        "--reader-temperature", str(models["longmemeval_reader"]["temperature"]),
        "--reader-top-p", str(models["longmemeval_reader"]["top_p"]),
        "--reader-top-k", str(models["longmemeval_reader"]["top_k"]),
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
        "--evaluator-api-key-env", "OPENAI_API_KEY",
    ]
    try:
        completed = subprocess.run(command, cwd=root, env=run_environment, check=False)
    finally:
        if proxy is not None:
            proxy.terminate()
            try:
                proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy.kill()
                proxy.wait(timeout=5)
    if completed.returncode != 0:
        raise RuntimeError(
            f"official LongMemEval case failed with exit code {completed.returncode}; "
            "reservations remain consumed and retry requires explicit reconciliation"
        )
    # Providers do not expose a transactional debit API.  Charge the complete
    # reserved upper bound in evidence; this is conservative and keeps a crash
    # or missing usage field from silently reopening budget.
    hf_ledger.complete(hf_key, cost_usd=hf_max)
    openai_ledger.complete(judge_key, cost_usd=judge_max)
    return {
        "format": "atmem-longmemeval-pilot-case-v1",
        "question_id": question_id, "domain": domain, "method": method,
        "output_dir": str(case_output), "cost_accounting": "reserved-upper-bound",
        "hf_cost_usd": hf_max, "openai_cost_usd": judge_max,
    }


def _is_expected_runner_patch(root: Path, path: Path) -> bool:
    original = _git_blob(root, "evaluation/run_eval.py").decode("utf-8")
    expected = original.replace(METHOD_ORIGINAL, METHOD_MARKER, 1).replace(
        CONFIG_ORIGINAL, CONFIG_MARKER, 1
    )
    return path.read_text(encoding="utf-8") == expected


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
