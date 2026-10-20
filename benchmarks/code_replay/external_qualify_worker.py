"""Evaluator-only stdlib worker, shipped into the pinned disposable container.

No AtMem/runtime imports, model endpoint, owner paths or network are required.
Upstream grading functions are dependency-wired, never rewritten.
"""
import ast
import base64
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace


TASK_FILES = {"eval.sh", "gold.patch", "test.patch", "tests.json"}
HARNESS_FILES = {"constants.py", "python.py", "grading.py", "LICENSE"}

# This worker is shipped as one stdlib-only script. Keep the resource profile
# identical to source_policy; a fixture checks the two declarations agree.
ASSET_SUFFIXES = frozenset({".ai", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2"})


def file_byte_limit(name):
    return 4_000_000 if Path(name).suffix.lower() in ASSET_SUFFIXES else 1_000_000

# Fixed identity-only preflight selection. Never select a parser from source,
# a model response, test output or a caller-supplied Python expression.
TASK_BINDINGS = {
    "marshmallow-code__marshmallow-1229": ("456bacbbead4fa30a1a82892c9446ac9efb8055b", "parse_log_marshmallow"),
    "marshmallow-code__marshmallow-1810": ("23d0551569d748460c504af85996451edd685371", "parse_log_marshmallow"),
    "psf__requests-1327": ("e7786ec14fdf20e8c373eddc9ac0f67d211cb1b9", "parse_log_requests"),
    "psf__requests-4356": ("234f80af88ff2aab39bbd65a3131ae93e1917c25", "parse_log_requests"),
    "pylint-dev__astroid-934": ("4cfd9b6d1003b9912ab94538e1dfa5d734f55251", "parse_log_astroid"),
    "pylint-dev__astroid-1616": ("6280a758733434cba32b719519908314a5c2955b", "parse_log_astroid"),
}

# Separate prospective confirmation selection, persisted before any private
# material or model outcome. Do not extend the validation manifest implicitly.
CONFIRMATION_BINDINGS = {
    'pydicom__pydicom-1033': ('701c1062bf66de2b29df68fa5540be6009943885', 'parse_log_pydicom'),
    'pydicom__pydicom-1194': ('5e70c1dfe09820023fec519dac4c51bebcb7f60d', 'parse_log_pydicom'),
    'pydicom__pydicom-1439': ('506ecea8f378dc687d5c504788fc78810a190b7a', 'parse_log_pydicom'),
    'pydicom__pydicom-997': ('41e984c8df5533805ae13cbcf419e6c5f63da30c', 'parse_log_pydicom'),
    'sqlfluff__sqlfluff-4084': ('181918e9c2840dc3f5ff1c713bf6b5a00d0725b5', 'parse_log_sqlfluff'),
    'sqlfluff__sqlfluff-1763': ('a10057635e5b2559293a676486f0b730981f037a', 'parse_log_sqlfluff'),
    'sqlfluff__sqlfluff-3436': ('23cd31e77a712a210c734e38488d7a34afd83a25', 'parse_log_sqlfluff'),
    'sqlfluff__sqlfluff-4041': ('66fd602d0824138f212082c8fdf381266a9edad3', 'parse_log_sqlfluff'),
    'pvlib__pvlib-python-1181': ('8b98768818ee5ad85d9479877533651a2e9dc2cd', 'parse_log_pvlib'),
    'pvlib__pvlib-python-1737': ('5119b4281fa9de8a4dc97002b5c10a6d73c25a4f', 'parse_log_pvlib'),
    'pvlib__pvlib-python-1296': ('bc0f0ff4e8580797af6672ff7c590caa1c78d6ed', 'parse_log_pvlib'),
    'pvlib__pvlib-python-1448': ('8d0f863da92739669e01ac4da4145e4547638b50', 'parse_log_pvlib'),
    'pytest-dev__pytest-9646': ('6aaa017b1e81f6eccc48ee4f6b52d25c49747554', 'parse_log_pytest'),
    'pytest-dev__pytest-8861': ('6740fb9da6dd21b3f1d2f6c3980605f4f7c9e81d', 'parse_log_pytest'),
    'pytest-dev__pytest-9780': ('d52a6e6074844581f5f89653bd4071fb6ea847d3', 'parse_log_pytest'),
    'pytest-dev__pytest-5227': ('2051e30b9b596e944524ccb787ed20f9f5be93e3', 'parse_log_pytest'),
    'sphinx-doc__sphinx-10191': ('301c7bdf57eee47426c9ad4d96392bff623ee6c3', 'parse_log_sphinx'),
    'sphinx-doc__sphinx-7597': ('c13ecd243709d1e210a030be5aa09b7714e35730', 'parse_log_sphinx'),
    'sphinx-doc__sphinx-8679': ('b372a99c0158f5799338a9a1b8611626ff1d114f', 'parse_log_sphinx'),
    'sphinx-doc__sphinx-10457': ('34d6d3bc8d24b5213d0978e6c4d839340aaafbcd', 'parse_log_sphinx'),
}

CONFIRMATION_SOURCE_PROFILES = {
    'pydicom__pydicom-': (('pydicom/',), ('tests/', 'pydicom/tests/')),
    'sqlfluff__sqlfluff-': (('src/sqlfluff/',), ('test/', 'tests/')),
    'pvlib__pvlib-python-': (('pvlib/',), ('tests/', 'pvlib/tests/')),
    'pytest-dev__pytest-': (('src/',), ('testing/', 'tests/')),
    'sphinx-doc__sphinx-': (('sphinx/',), ('tests/',)),
}


def task_binding(instance_id, base_commit):
    binding = TASK_BINDINGS.get(instance_id) or CONFIRMATION_BINDINGS.get(instance_id)
    if binding is None or binding[0] != base_commit:
        raise ValueError("preselected task/base identity required")
    return binding


def task_source_roots(instance_id, base_commit):
    task_binding(instance_id, base_commit)
    if instance_id in CONFIRMATION_BINDINGS:
        profiles = [value for prefix, value in CONFIRMATION_SOURCE_PROFILES.items() if instance_id.startswith(prefix)]
        if len(profiles) != 1:
            raise ValueError('exact confirmation source profile required')
        return profiles[0]
    if instance_id.startswith("marshmallow-code__marshmallow-"):
        return ("src/marshmallow/",), ("tests/",)
    if instance_id.startswith("psf__requests-"):
        return ("requests/",), ("tests/",)
    return ("astroid/",), ("tests/", "astroid/tests/")


def task_runtime_exclusions(instance_id, base_commit):
    task_binding(instance_id, base_commit)
    return (".eggs/",) if instance_id.startswith("psf__requests-") else ()


def tracked_base(base):
    listing = subprocess.check_output(["git", "-C", "/testbed", "ls-tree", "-r", "-z", base])
    identities, total = {}, 0
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b"\t", 1)
        mode, kind, identity = metadata.split()
        name = encoded_path.decode()
        if mode not in {b"100644", b"100755"} or kind != b"blob" or name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("unsupported tracked base member")
        target = Path("/testbed") / name
        if target.is_symlink() or not target.is_file() or target.stat().st_size > file_byte_limit(name):
            raise ValueError("bounded regular tracked base required")
        raw = target.read_bytes()
        total += len(raw)
        if total > 40_000_000 or sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest().encode() != identity:
            raise ValueError("tracked base bytes differ")
        identities[name] = identity.decode()
    return {"files": len(identities), "bytes": total,
            "tree_fingerprint_sha256": sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()}


def validated_files(payload, *, task_identity=None):
    if payload.get("phase") not in {"parent", "reference"}:
        raise ValueError("parent/reference role required")
    expected_id = task_identity or "marshmallow-code__marshmallow-1229"
    if task_identity is not None:
        task_binding(task_identity, payload.get("base_commit"))
    if payload.get("instance_id") != expected_id or not re.fullmatch(r"[0-9a-f]{40}", payload.get("base_commit", "")):
        raise ValueError("fixed task/base required")
    result = {}
    for role, allowed in (("task_files", TASK_FILES), ("harness_files", HARNESS_FILES)):
        files = payload.get(role, {})
        if set(files) != allowed:
            raise ValueError("exact role-bound evaluator files required")
        result[role] = {}
        for name, entry in files.items():
            raw = base64.b64decode(entry["content_base64"], validate=True)
            if len(raw) > 262144 or sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("evaluator file identity/budget differs")
            result[role][name] = raw
    script, patch = result["task_files"]["eval.sh"], result["task_files"]["test.patch"]
    if patch.strip(b"\n") not in script:
        raise ValueError("verified hidden test patch is not embedded in upstream script")
    return result


def dependency_wired_tree(raw, filename):
    tree = ast.parse(raw, filename=filename)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    # All function/constant logic is retained verbatim as AST; only dependency
    # imports are supplied from the separately pinned upstream namespace.
    tree.body = [future] + [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    return ast.fix_missing_locations(tree)


def dependency_wired_module(raw, namespace, filename):
    exec(compile(dependency_wired_tree(raw, filename), filename, "exec"), namespace)
    return namespace


def grade(raw_log, expected, harness, directory, *, parser_name="parse_log_marshmallow"):
    if parser_name not in {binding[1] for binding in (*TASK_BINDINGS.values(), *CONFIRMATION_BINDINGS.values())}:
        raise ValueError("preselected upstream parser required")
    constants = {}
    exec(compile(harness["constants.py"], "pinned-upstream/constants.py", "exec"), constants)
    parsers = dependency_wired_module(harness["python.py"], {**constants, "re": re}, "pinned-upstream/python.py")
    namespace = dependency_wired_module(harness["grading.py"], {**constants, "re": re,
        "PARSER_REGISTRY": {parser_name: parsers[parser_name]}}, "pinned-upstream/grading.py")
    output = directory / "private-test.log"
    output.write_bytes(raw_log)
    statuses, found = namespace["get_logs_eval"](SimpleNamespace(log_parser=parser_name), str(output))
    report = namespace["get_eval_tests_report"](statuses, expected, eval_type=constants["EvalType"].PASS_AND_FAIL)
    actual_failures = 0
    skipped = 0
    for name in expected["FAIL_TO_PASS"]:
        key = namespace["_resolve_case"](name, statuses)
        actual_failures += key is not None and statuses[key] in {"FAILED", "ERROR"}
    for name in expected["PASS_TO_PASS"]:
        key = namespace["_resolve_case"](name, statuses)
        skipped += key is not None and statuses[key] == "SKIPPED"
    return {"results_found": found, "parsed_statuses": len(statuses),
        "expected_f2p": len(expected["FAIL_TO_PASS"]), "expected_p2p": len(expected["PASS_TO_PASS"]),
        "observed_f2p_failures": actual_failures, "p2p_skipped": skipped,
        "f2p_success": len(report["FAIL_TO_PASS"]["success"]), "f2p_failure": len(report["FAIL_TO_PASS"]["failure"]),
        "p2p_success": len(report["PASS_TO_PASS"]["success"]), "p2p_failure": len(report["PASS_TO_PASS"]["failure"]),
        "resolution": namespace["get_resolution_status"](report),
        "test_exit_marker": namespace["parse_test_exit_code"](raw_log.decode(errors="replace"))}


def execute_script(script, environment):
    try:
        result = subprocess.run(["/bin/bash", str(script)], cwd="/testbed", env=environment,
                                capture_output=True, timeout=120)
        return result.returncode, result.stdout, result.stderr, None
    except subprocess.TimeoutExpired as exc:
        return None, exc.stdout or b"", exc.stderr or b"", "script_timeout"


def main():
    payload = json.load(sys.stdin)
    _, parser_name = task_binding(payload.get("instance_id"), payload.get("base_commit"))
    files = validated_files(payload, task_identity=payload["instance_id"])
    directory = Path("/opt/atmem-evaluator")
    directory.mkdir(mode=0o700, exist_ok=False)
    for name, raw in files["task_files"].items():
        (directory / name).write_bytes(raw)
    expected = json.loads(files["task_files"]["tests.json"])
    if not isinstance(expected, dict) or any(not isinstance(expected.get(k), list) for k in ("FAIL_TO_PASS", "PASS_TO_PASS")) or not expected["FAIL_TO_PASS"]:
        raise ValueError("nonempty upstream F2P and declared P2P lists required")
    baseline = tracked_base(payload["base_commit"])
    if payload["phase"] == "reference":
        applied = subprocess.run(["git", "-C", "/testbed", "apply", "--whitespace=nowarn", str(directory / "gold.patch")], capture_output=True)
        if applied.returncode:
            raise ValueError("verified reference patch did not apply")
    environment = dict(os.environ)
    environment["PATH"] = "/opt/miniconda3/envs/testbed/bin:/opt/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code, stdout, stderr, failure = execute_script(directory / "eval.sh", environment)
    log = stdout + stderr
    result = {"phase": payload["phase"], "script_exit_code": exit_code,
        "base_source_verified": True, "tracked_base": baseline, "embedded_test_patch_verified": True,
        "stdout_base64": base64.b64encode(stdout).decode(), "stderr_base64": base64.b64encode(stderr).decode(),
        "worker_failure": failure,
        "assurance": "exact_upstream_script_and_dependency_wired_upstream_grading_not_full_harness_installation"}
    try:
        result["grading"] = grade(log, expected, files["harness_files"], directory, parser_name=parser_name)
    except Exception as exc:
        result["grading"] = {}
        result["grading_error"] = type(exc).__name__
        result["worker_failure"] = result["worker_failure"] or "upstream_grading_error"
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
