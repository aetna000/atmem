"""One retained, zero-inference source-to-grader control on the qualified task."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_qualification import worker_command, execute_worker


def bootstrap_source(control_source, *, result_transport=None, runtime_projection=False):
    if result_transport not in (None, "zlib-v1", "lzma-v2"):
        raise ValueError("unsupported operator result transport")
    if type(runtime_projection) is not bool:
        raise ValueError("operator runtime projection selector must be boolean")
    directory = Path(__file__).parent
    modules = [("atmem_external_control", control_source),
        ("benchmarks.code_replay.source_policy", (directory / "source_policy.py").read_text()),
        ("benchmarks.code_replay.source_capture", (directory / "source_capture.py").read_text())]
    if result_transport is not None:
        modules.append(("benchmarks.code_replay.result_transport",
                        (directory / "result_transport.py").read_text()))
    if runtime_projection:
        from benchmarks.code_replay.runtime_projection_control import projection_modules
        dependencies = projection_modules()
        names = {name for name, _ in dependencies}
        modules = dependencies + [(name, text) for name, text in modules if name not in names]
    worker = (directory / "external_candidate_worker.py").read_text()
    # Operator source is frozen in the command, never accepted from a solver
    # payload. Namespace packages permit unmodified imports of shared modules.
    worker_globals = "{'__name__':'__main__'}"
    if result_transport is not None:
        worker_globals = ("{'__name__':'__main__','print':"
            "sys.modules['benchmarks.code_replay.result_transport'].result_printer()}")
        if result_transport == "lzma-v2":
            worker_globals = worker_globals.replace("result_printer()", "result_printer(compression='lzma-v2')")
    if runtime_projection:
        worker_globals = worker_globals[:-1] + ",'PINNED_RUNTIME_PROJECTION':'v2'}"
    code = ("import sys,types\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name); module.__path__=[]; sys.modules[name]=module\n"
        "for name,source in " + repr(modules) + ":\n"
        " module=types.ModuleType(name); sys.modules[name]=module\n"
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n"
        "exec(compile(" + repr(worker) + ",'external_candidate_worker.py','exec')," + worker_globals + ")\n")
    return code


def boundary_qualified(results, *, expected_f2p=8, expected_p2p=61,
                       source_roots=("src/marshmallow/",), test_roots=("tests/",)):
    # Counts/roots are frozen operator metadata, never inferred from outcomes.
    if type(expected_f2p) is not int or expected_f2p < 1 or type(expected_p2p) is not int or expected_p2p < 0:
        return False
    if set(results) != {"unchanged", "reference_as_proposal"}:
        return False
    for phase, result in results.items():
        worker = result.get("worker", {})
        grading = worker.get("grading", {})
        if (result.get("reason") or result.get("exit_code") != 0 or worker.get("worker_failure")
            or worker.get("phase") != phase or worker.get("base_source_verified") is not True
            or worker.get("assembled_bytes_verified") is not True or not grading.get("results_found")
            or grading.get("expected_f2p") != expected_f2p or grading.get("expected_p2p") != expected_p2p
            or grading.get("p2p_success") != expected_p2p or grading.get("p2p_failure") != 0
            or grading.get("p2p_skipped") != 0 or worker.get("out_of_scope_changes")):
            return False
        if any(not isinstance(worker.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", worker[name])
               for name in ("original_sha256", "candidate_sha256", "assembled_sha256")):
            return False
        if worker.get("source_policy") != {"source_roots": list(source_roots), "test_roots": list(test_roots)}:
            return False
        if phase == "unchanged":
            if (grading.get("observed_f2p_failures") != expected_f2p or grading.get("f2p_failure") != expected_f2p
                or grading.get("f2p_success") != 0 or worker.get("changed_paths")
                or grading.get("resolution") != "RESOLVED_NO"
                or worker.get("original_sha256") != worker.get("assembled_sha256")):
                return False
        elif (grading.get("f2p_success") != expected_f2p or grading.get("f2p_failure") != 0
              or grading.get("resolution") != "RESOLVED_FULL"
              or not worker.get("changed_paths") or worker.get("original_sha256") == worker.get("assembled_sha256")):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    if Path("/Volumes") in args.state_root.resolve().parents:
        raise ValueError("private control state must stay internal")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "external-source-boundary-v1-20261017"
    if vault.inspect(principal, run_id):
        raise ValueError("control retained already; no silent retry")
    prior = [e["envelope"] for e in vault.inspect(principal, "external-reference-control-v2-20261017")]
    def only(kind):
        rows = [e["payload"] for e in prior if e["event_type"] == kind]
        if len(rows) != 1:
            raise ValueError("exact qualified predecessor required")
        return rows[0]
    completed, original_plan, material = only("external.reference_completed"), only("external.reference_planned"), only("external.private_material")
    if not completed.get("qualified") or completed.get("solver_calls") != 0 or material["instance_id"] != "marshmallow-code__marshmallow-1229":
        raise ValueError("first qualified zero-model task required")
    control_bytes = base64.b64decode(material["worker_source_base64"], validate=True)
    if sha256(control_bytes).hexdigest() != original_plan["source_sha256"]["external_qualify_worker.py"]:
        raise ValueError("qualified control implementation differs")
    source = bootstrap_source(control_bytes.decode())
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    plan = {"prior_run": "external-reference-control-v2-20261017", "instance_id": material["instance_id"],
        "image": original_plan["image"], "solver_calls": 0,
        "phases": ["unchanged", "reference_as_proposal"],
        "bootstrap_source_base64": base64.b64encode(source.encode()).decode(),
        "bootstrap_sha256": sha256(source.encode()).hexdigest(),
        "driver_source_base64": base64.b64encode(Path(__file__).read_bytes()).decode(),
        "policy_text": Path("specs/042-atmem-code/external-source-boundary-v1.md").read_text()}
    vault.capture(run_id=run_id, kind="external.boundary_planned", principal=principal, payload=plan)
    results = {}
    try:
        for phase in plan["phases"]:
            name = "atmem-reference-control-" + uuid4().hex
            command = worker_command(plan["image"], name, source)
            vault.capture(run_id=run_id, kind="external.boundary_dispatch", principal=principal,
                payload={"phase": phase, "command": command, "material_prior_run": plan["prior_run"]})
            result = execute_worker(command, {**material, "source_boundary_phase": phase}, name)
            results[phase] = result
            vault.capture(run_id=run_id, kind="external.boundary_attempt", principal=principal, payload={"phase": phase, **result})
            print(json.dumps({"phase": phase, "controller_exit_code": result.get("exit_code"), "reason": result.get("reason"),
                "grading": result.get("worker", {}).get("grading"),
                "assembled_bytes_verified": result.get("worker", {}).get("assembled_bytes_verified")}), flush=True)
        summary = {"qualified": boundary_qualified(results), "solver_calls": 0,
            "scope": "first_task_source_assembly_boundary_only", "instance_id": material["instance_id"]}
        vault.capture(run_id=run_id, kind="external.boundary_completed", principal=principal, payload=summary)
        with (args.state_root / "summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        vault.capture(run_id=run_id, kind="external.boundary_failed", principal=principal,
            payload={"exception_type": type(exc).__name__, "failure": str(exc), "completed_phases": sorted(results), "solver_calls": 0})
        raise


if __name__ == "__main__":
    main()
