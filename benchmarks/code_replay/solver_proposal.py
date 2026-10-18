"""Evaluator-only adapter over the already qualified source/grading boundaries."""
from pathlib import Path

from benchmarks.code_replay.public_test_control import public_modules, public_task_settings
from benchmarks.code_replay.external_source_boundary import boundary_qualified


def proposal_request(material, source, candidate):
    # The host supplies verified public base metadata, never the solver.
    return {"format": "atmem-private-proposal-evaluation-v1", "material": material,
        "proposal": {"format": "atmem-public-source-proposal-v1", "base_commit": source["base_commit"],
            "public_base_files_base64": source["files_base64"], "public_base_modes": source["modes"],
            "candidate_files_base64": candidate}}


def solver_bootstrap(control_source, task=None, *, operator_registration=None,
                     runtime_manifest=None, result_transport=None):
    if result_transport not in (None, "zlib-v1", "lzma-v2"):
        raise ValueError("unsupported operator result transport")
    directory = Path(__file__).parent
    modules = public_modules(runtime_projection=runtime_manifest is not None) + [
        ("atmem_external_control", control_source),
        ("atmem_external_boundary", (directory / "external_candidate_worker.py").read_text()),
        ("atmem_public_validation", (directory / "public_test_worker.py").read_text())]
    worker = (directory / "solver_proposal_worker.py").read_text()
    settings = public_task_settings(task, operator_registration=operator_registration, runtime_manifest=runtime_manifest)
    final_globals = repr({"__name__": "__main__", **settings})
    if result_transport:
        modules.append(("benchmarks.code_replay.result_transport", (directory / "result_transport.py").read_text()))
        final_globals = final_globals[:-1] + ",'print':sys.modules['benchmarks.code_replay.result_transport'].result_printer()}"
        if result_transport == 'lzma-v2':
            final_globals = final_globals.replace('result_printer()', "result_printer(compression='lzma-v2')")
    return ("import sys,types\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name); module.__path__=[]; sys.modules[name]=module\n"
        "for name,source in " + repr(modules) + ":\n"
        " module=types.ModuleType(name); sys.modules[name]=module\n"
        + (" module.__dict__.update(" + repr(settings) + ")\n" if settings else "") +
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n"
        "exec(compile(" + repr(worker) + ",'solver_proposal_worker.py','exec')," + final_globals + ")\n")


def proposal_controls_qualified(results, **expectations):
    if set(results) != {"unchanged", "reference_as_proposal"}:
        return False
    normalized = {}
    for phase, row in results.items():
        worker = row.get("worker", {})
        if (worker.get("phase") != "solver_proposal" or worker.get("public_base_verified") is not True
            or worker.get("image_only_bytes_preserved") is not True
            or worker.get("gold_patch_written") is not False or worker.get("policy_rejected")):
            return False
        # Only map the control role for the existing outcome verifier. Do not
        # mutate raw receipts, grades, digests or the original worker's policy.
        normalized[phase] = {**row, "worker": {**worker, "phase": phase}}
    return boundary_qualified(normalized, **expectations)
