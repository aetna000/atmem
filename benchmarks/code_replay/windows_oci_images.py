"""Revalidate retained registry representations; qualify only new original images."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import digest
from benchmarks.code_replay.external_qualification import task_material
from benchmarks.code_replay.external_runtime import command as runtime_command
from benchmarks.code_replay.registry_platform import bound_native_descriptor
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, runtime_program, runtime_evidence_qualifies
from benchmarks.code_replay.windows_eligibility_images import PREFLIGHT, RUN as PRIOR_IMAGES, validate_pool
from benchmarks.code_replay.windows_runtime_projection import PRIOR as PRIOR_REFERENCE
from benchmarks.code_replay.windows_transport import framed_command, framed_input


RUN = "external-windows-eligibility-oci-images-v1-20261018"


def main():
    selection = json.loads((PREFLIGHT / "selection.json").read_bytes())
    metadata = json.loads((PREFLIGHT / "metadata.json").read_bytes())
    validate_pool(selection, metadata)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id="confirmation-v1", scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError("registry correction retained already; do not repeat")
    prior = vault.inspect(principal, PRIOR_IMAGES)
    if sum(e["envelope"]["event_type"] == "external.eligibility_images_completed" for e in prior) != 1:
        raise ValueError("original image checks must be terminal")
    registry = [e for e in prior if e["envelope"]["event_type"] == "external.eligibility_registry_result"]
    prior_runtimes = {e["envelope"]["payload"]["instance_id"]: e["envelope"]["payload"] for e in prior
                      if e["envelope"]["event_type"] == "external.eligibility_runtime_result"}
    if len(registry) != 40 or len({e["envelope"]["payload"]["instance_id"] for e in registry}) != 40:
        raise ValueError("all forty original registry responses required")
    reference = vault.inspect(principal, PRIOR_REFERENCE)
    reference_plan = next(e["envelope"]["payload"] for e in reference
                          if e["envelope"]["event_type"] == "external.confirmation_reference_planned")
    material_by_id = {e["envelope"]["payload"]["instance_id"]: e["envelope"]["payload"] for e in reference
                      if e["envelope"]["event_type"] == "external.confirmation_private_material"}
    namespace = {"__name__": "oci_operator_material_validation"}
    exec(compile(reference_plan["worker_source"], "retained_operator_worker.py", "exec"), namespace)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    program = runtime_program()
    save("external.oci_images_planned", {
        "prior_images": PRIOR_IMAGES, "prior_reference": PRIOR_REFERENCE,
        "selection_sha256": digest(selection), "driver_source": Path(__file__).read_text(),
        "parser_source": Path(__file__).with_name("registry_platform.py").read_text(),
        "runtime_program": program, "original_pool": [r["instance_id"] for r in selection["selected"]],
        "protocol": Path("specs/042-atmem-code/source-runtime-projection-v2.md").read_text(),
        "registry_queries_repeated": False, "new_model_calls": 0,
        "max_parallel_new_pulls": 2, "prior_failures_preserved": True,
    })
    rows, new = [], []
    for event in registry:
        old = event["envelope"]["payload"]
        row = {"instance_id": old["instance_id"], "repo": old["repo"],
               "image_tag": old["image_tag"], "prior_registry_receipt": event["object_id"]}
        try:
            outer = json.loads(base64.b64decode(old["transport_stdout_base64"], validate=True))
            if old["transport_exit"] != 0 or outer["exit_code"] != 0:
                raise ValueError("original registry transport/command failed")
            raw = base64.b64decode(outer["stdout_base64"], validate=True)
            descriptor = bound_native_descriptor(raw)
            row.update(descriptor=descriptor, image=old["image_tag"].rsplit(":", 1)[0] + "@" + descriptor["digest"])
            previous = prior_runtimes.get(old["instance_id"])
            if previous is not None:
                if (not runtime_evidence_qualifies(previous, descriptor)
                    or previous["image"] != row["image"]):
                    raise ValueError("existing runtime proof does not bind corrected descriptor")
                row.update(runtime_qualified=True, runtime_reused=True)
            else:
                row.update(runtime_qualified=False, runtime_reused=False)
                new.append(row)
        except (ValueError, KeyError) as exc:
            row["failure"] = type(exc).__name__ + ": " + str(exc)
        save("external.oci_registry_result", row)
        rows.append(row)
    selected = {r["instance_id"]: r for r in selection["selected"]}
    tasks = {r["instance_id"]: r["metadata"] for r in metadata["reports"]}
    def fetch(row):
        identity = row["instance_id"]
        try:
            material = {"instance_id": identity, "base_commit": tasks[identity]["base_commit"],
                        "task_files": task_material(selected[identity]), "harness_files": reference_plan["harness_files"]}
            namespace["validated_files"]({**material, "phase": "parent"}, task_identity=identity)
            return {"instance_id": identity, "verified": True, "material": material,
                    "material_sha256": digest(material)}
        except Exception as exc:
            return {"instance_id": identity, "verified": False, "failure": type(exc).__name__ + ": " + str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, row) for row in new]):
            result = future.result()
            save("external.oci_material_result", result)
            print(json.dumps({"phase": "material", "instance_id": result["instance_id"], "verified": result["verified"]}), flush=True)
    jobs = []
    for row in new:
        name = "atmem-runtime-control-" + uuid4().hex
        job = {"program": program, "image": row["image"], "runtime_command": runtime_command(row["image"], name)}
        save("external.oci_runtime_dispatch", {"instance_id": row["instance_id"], "job": job})
        jobs.append((row, job))
    def execute(item):
        row, job = item
        result = {"instance_id": row["instance_id"], "image": row["image"], "qualified": False}
        try:
            proc = subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=300)
            result.update(transport_exit=proc.returncode,
                transport_stdout_base64=base64.b64encode(proc.stdout).decode(),
                transport_stderr_base64=base64.b64encode(proc.stderr).decode())
            if proc.returncode == 0:
                result["result"] = json.loads(proc.stdout)
                result["qualified"] = runtime_evidence_qualifies(result, row["descriptor"])
        except subprocess.TimeoutExpired as exc:
            result.update(transport_exit=None, failure="transport_timeout",
                transport_stdout_base64=base64.b64encode(exc.stdout or b"").decode(),
                transport_stderr_base64=base64.b64encode(exc.stderr or b"").decode())
        except (ValueError, OSError) as exc:
            result["failure"] = type(exc).__name__ + ": " + str(exc)
        return result
    qualified_new = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(execute, item) for item in jobs]):
            result = future.result()
            save("external.oci_runtime_result", result)
            if result["qualified"]:
                qualified_new.append(result["instance_id"])
            print(json.dumps({"phase": "runtime", "instance_id": result["instance_id"],
                              "qualified": result["qualified"], "failure": result.get("failure")}), flush=True)
    summary = {"original_candidates": 40, "registry_resolved": sum("descriptor" in row for row in rows),
               "reused_exact_runtime": sum(row.get("runtime_reused", False) for row in rows),
               "new_runtime_qualified": sorted(qualified_new), "new_model_calls": 0,
               "final_model_selection": False, "original_negative_records_preserved": True}
    save("external.oci_images_completed", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
