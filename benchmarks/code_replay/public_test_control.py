"""Qualify public development-test execution before any external model solve."""
import argparse
import ast
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_qualification import worker_command, execute_worker


def public_task_settings(task, *, operator_registration=None, runtime_manifest=None):
    """Bind operator metadata in code, never accept settings in model input."""
    if operator_registration is not None:
        from benchmarks.code_replay.eligibility_binding import registered_public_settings
        settings = registered_public_settings(task, operator_registration)
        if runtime_manifest is not None:
            from benchmarks.code_replay.runtime_fixtures import validate_manifest
            from benchmarks.code_replay.source_policy import SourcePolicy
            policy = SourcePolicy(settings["PINNED_SOURCE_ROOTS"], test_roots=settings["PINNED_TEST_ROOTS"])
            settings.update(PINNED_RUNTIME_MANIFEST=validate_manifest(runtime_manifest, policy),
                            PINNED_RUNTIME_PROJECTION="v2")
        return settings
    if runtime_manifest is not None:
        raise ValueError("runtime projection requires operator eligibility registration")
    if task is None:
        return {}
    from benchmarks.code_replay.external_qualify_worker import task_binding, task_runtime_exclusions, task_source_roots
    from benchmarks.code_replay.source_policy import path_name
    if not isinstance(task, dict) or set(task) != {"instance_id", "base_commit", "image_extras_sha256"}:
        raise ValueError("exact pinned public task settings required")
    task_binding(task["instance_id"], task["base_commit"])
    extras = task["image_extras_sha256"]
    if not isinstance(extras, dict) or len(extras) > 10000:
        raise ValueError("bounded pinned image artifact map required")
    for name, identity in extras.items():
        path_name(name)
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise ValueError("exact image artifact digest required")
    roots, tests = task_source_roots(task["instance_id"], task["base_commit"])
    # Operator-bound repository layout, never chosen by a model request. These
    # profiles still require actual source/import/runtime qualification.
    layouts = {
        'pydicom__pydicom-': (('pydicom/tests', 'tests'), ('pydicom/tests',), '.'),
        'sqlfluff__sqlfluff-': (('test', 'tests'), ('test',), 'src'),
        'pvlib__pvlib-python-': (('pvlib/tests', 'tests'), ('pvlib/tests',), '.'),
        'pytest-dev__pytest-': (('testing', 'tests'), ('testing',), 'src'),
        'sphinx-doc__sphinx-': (('tests',), ('tests',), '.'),
    }
    paths = ("tests", "test_requests.py") if task["instance_id"] == "psf__requests-1327" else ("tests",)
    default_paths = ("test_requests.py",) if task["instance_id"] == "psf__requests-1327" else ("tests",)
    source_subdir = "src" if task["instance_id"].startswith("marshmallow-code__") else "."
    for prefix, layout in layouts.items():
        if task['instance_id'].startswith(prefix):
            paths, default_paths, source_subdir = layout
    return {"PINNED_TASK_ID": task["instance_id"], "PINNED_BASE": task["base_commit"],
        "PINNED_SOURCE_ROOTS": roots, "PINNED_TEST_ROOTS": tests,
        "PINNED_TEST_PATHS": paths,
        "PINNED_DEFAULT_TEST_PATHS": default_paths,
        "PINNED_SOURCE_SUBDIR": source_subdir,
        "PINNED_IMAGE_EXTRAS": extras,
        "PINNED_RUNTIME_EXCLUSIONS": task_runtime_exclusions(task["instance_id"], task["base_commit"])}


def public_modules(*, runtime_projection=False):
    directory = Path(__file__).parent
    grade = (directory / "grade.py").read_text()
    nodes = [node for node in ast.parse(grade).body if isinstance(node, ast.FunctionDef) and node.name == "write_new_tree"]
    if len(nodes) != 1:
        raise ValueError("existing source writer required")
    writer = "from pathlib import Path, PurePosixPath\n" + ast.get_source_segment(grade, nodes[0]) + "\n"
    modules = [("atmem_native_tree", writer),
        ("benchmarks.code_replay.source_policy", (directory / "source_policy.py").read_text()),
        ("benchmarks.code_replay.source_capture", (directory / "source_capture.py").read_text())]
    if runtime_projection:
        modules.append(("benchmarks.code_replay.runtime_fixtures",
                        (directory / "runtime_fixtures.py").read_text()))
    return modules


def public_bootstrap(task=None, *, operator_registration=None, runtime_manifest=None, result_transport=None):
    if result_transport not in (None, 'lzma-v2'):
        raise ValueError('explicit supported public result transport required')
    directory = Path(__file__).parent
    modules = public_modules(runtime_projection=runtime_manifest is not None)
    if result_transport:
        modules.append(('benchmarks.code_replay.result_transport', (directory/'result_transport.py').read_text()))
    worker = (directory / "public_test_worker.py").read_text()
    final_globals = repr({"__name__": "__main__", **public_task_settings(task, operator_registration=operator_registration, runtime_manifest=runtime_manifest)})
    if result_transport:
        final_globals = final_globals[:-1] + ",'print':sys.modules['benchmarks.code_replay.result_transport'].result_printer(compression='lzma-v2')}"
    return ("import sys,types\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name); module.__path__=[]; sys.modules[name]=module\n"
        "for name,source in " + repr(modules) + ":\n"
        " module=types.ModuleType(name); sys.modules[name]=module\n"
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n"
        "exec(compile(" + repr(worker) + ",'public_test_worker.py','exec')," + final_globals + ")\n")


def public_command(image, name, source):
    command = worker_command(image, name, source)
    command[command.index("--label") + 1] = "atmem.benchmark=external-public-tests-v1"
    return command


def public_request(source, candidate, *, paths, keyword=None, max_failures=0):
    # Construct a NEW allowlisted role envelope; never pass an evaluator event.
    return {"format": "atmem-public-pytest-request-v1", "base_commit": source["base_commit"],
        "public_base_files_base64": source["files_base64"], "public_base_modes": source["modes"],
        "candidate_files_base64": candidate,
        "pytest": {"paths": paths, "keyword": keyword, "max_failures": max_failures}}


def success(result):
    worker = result.get("worker", {})
    raw = base64.b64decode(worker.get("output_base64", ""), validate=True)
    return (not result.get("reason") and result.get("exit_code") == 0 and not worker.get("reason")
        and worker.get("exit_code") == 0 and worker.get("output_truncated") is False
        and worker.get("original_git_object_store_removed") is True
        and worker.get("evaluator_material_received") is False
        and bool(re.search(rb"\b[1-9][0-9]* passed\b", raw)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    if Path("/Volumes") in args.state_root.resolve().parents:
        raise ValueError("control state must stay internal")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "external-public-tests-v1-20261017"
    if vault.inspect(principal, run_id):
        raise ValueError("public control retained already; no silent retry")
    exported = [e["envelope"]["payload"] for e in vault.inspect(principal, "external-solver-source-v1-20261017")
        if e["envelope"]["event_type"] == "external.solver_source_exported"]
    prior = [e["envelope"]["payload"] for e in vault.inspect(principal, "external-reference-control-v2-20261017")
        if e["envelope"]["event_type"] == "external.reference_planned"]
    if len(exported) != 1 or len(prior) != 1 or exported[0]["git_history_exported"] is not False or exported[0]["untracked_files_exported"] != 0:
        raise ValueError("verified first-task public export required")
    source, image = exported[0], prior[0]["image"]
    bootstrap = public_bootstrap()
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    canary = args.state_root / "private-canary.txt"
    nonce = "ATMEM_PUBLIC_JOB_DENIED_" + uuid4().hex
    canary.write_text(nonce); canary.chmod(0o600)
    probe = ("from pathlib import Path\nimport socket\nimport marshmallow\n"
        "def test_source_and_git_boundary():\n"
        " assert Path(marshmallow.__file__).resolve().is_relative_to(Path('/work/src'))\n"
        " assert not Path('/testbed/.git').exists()\n"
        " assert not Path('/opt/atmem-evaluator').exists()\n"
        "def test_owner_canary_inaccessible():\n"
        " try:\n  observed=Path(" + repr(str(canary)) + ").read_text()\n"
        " except (FileNotFoundError,PermissionError):\n  return\n"
        " raise AssertionError('owner canary accessible')\n"
        "def test_no_external_network():\n"
        " with socket.socket() as channel:\n"
        "  channel.settimeout(0.2)\n"
        "  try:\n   channel.connect(('1.1.1.1',443))\n"
        "  except OSError:\n   return\n"
        "  raise AssertionError('external network available')\n")
    candidate = {**source["files_base64"], "tests/test_atmem_environment_probe.py": base64.b64encode(probe.encode()).decode()}
    phases = [("isolation_probe", public_request(source, candidate, paths=["tests/test_atmem_environment_probe.py"])),
              ("public_base_tests", public_request(source, source["files_base64"], paths=["tests"]))]
    vault.capture(run_id=run_id, kind="external.public_tests_planned", principal=principal, payload={
        "policy_text": Path("specs/042-atmem-code/external-public-tests-v1.md").read_text(), "image": image,
        "bootstrap_source_base64": base64.b64encode(bootstrap.encode()).decode(), "bootstrap_sha256": sha256(bootstrap.encode()).hexdigest(),
        "driver_source_base64": base64.b64encode(Path(__file__).read_bytes()).decode(), "solver_calls": 0,
        "canary_bytes_base64": base64.b64encode(nonce.encode()).decode(), "phases": [name for name, _ in phases]})
    results = {}
    try:
        for phase, payload in phases:
            name = "atmem-reference-control-" + uuid4().hex
            command = public_command(image, name, bootstrap)
            vault.capture(run_id=run_id, kind="external.public_tests_dispatch", principal=principal,
                payload={"phase": phase, "command": command, "public_request": payload})
            result = execute_worker(command, payload, name)
            results[phase] = result
            vault.capture(run_id=run_id, kind="external.public_tests_attempt", principal=principal, payload={"phase": phase, **result})
            worker = result.get("worker", {})
            print(json.dumps({"phase": phase, "controller_exit_code": result.get("exit_code"), "reason": result.get("reason"),
                "public_test_exit_code": worker.get("exit_code"), "public_test_reason": worker.get("reason"),
                "git_object_store_removed": worker.get("original_git_object_store_removed"), "qualified": success(result)}), flush=True)
            if not success(result):
                break
        summary = {"qualified": len(results) == 2 and all(success(row) for row in results.values()),
            "scope": "first_task_public_development_tests_only", "solver_calls": 0, "completed_phases": sorted(results)}
        vault.capture(run_id=run_id, kind="external.public_tests_completed", principal=principal, payload=summary)
        with (args.state_root / "summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        vault.capture(run_id=run_id, kind="external.public_tests_failed", principal=principal,
            payload={"exception_type": type(exc).__name__, "failure": str(exc), "completed_phases": sorted(results), "solver_calls": 0})
        raise


if __name__ == "__main__":
    main()
