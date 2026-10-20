"""Recorded same-pool source/runtime controls on Windows; no model inference."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_qualification import worker_command
from benchmarks.code_replay.external_source_boundary import bootstrap_source, boundary_qualified
from benchmarks.code_replay.result_transport import decode_result
from benchmarks.code_replay.runtime_projection_control import projected_control_source, projection_program, projection_modules
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_confirmation_reference import strict_reference_qualified
from benchmarks.code_replay.windows_transport import framed_command, framed_input, worker_program


PRIOR = "external-windows-confirmation-eligibility-reference-v2-20261018"
PREFIX = "external-windows-runtime-projection"


def codec_only_program(prior_plan, codec):
    """Prove that an explicit repair changes only the response codec/sink."""
    old = [source for name, source in prior_plan['modules']
           if name == 'benchmarks.code_replay.result_transport']
    program = prior_plan['program']
    if len(old) != 1 or program.count(repr(old[0])) != 1 or program.count('.result_printer()') != 1:
        raise ValueError('exact prior embedded codec and single output sink required')
    return program.replace(repr(old[0]), repr(codec)).replace(
        '.result_printer()', ".result_printer(compression='lzma-v2')")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("inventory", "reference", "boundary"), default="inventory")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--supplemental-oci", action="store_true",
                        help="Only the newly resolved original OCI candidates, never replacements")
    group.add_argument("--pyvista-derived", action="store_true",
                       help="Uniform fixed-VTK derived images for all eight original PyVista tasks")
    parser.add_argument("--operator-v2", action="store_true",
                        help="Windows-local per-run bookkeeping after the recorded Mac resource stop")
    parser.add_argument("--lossless-v3", action="store_true",
                        help="Only the proved PyVista response-encoding failures; no grade retry")
    parser.add_argument('--codec-guard-v4', action='store_true',
                        help='Explicit zero-worker guard correction, not a model/test retry')
    args = parser.parse_args()
    suffix = ("-pyvista-vtk931-v1-20261018" if args.pyvista_derived else
              "-oci-v1-20261018" if args.supplemental_oci else "-v1-20261018")
    prerequisite_suffix = suffix
    if args.operator_v2 and not args.pyvista_derived:
        if args.phase != "boundary":
            raise ValueError("existing complete inventory/reference stages are not repeated by operator-v2")
        suffix = suffix.replace("-v1-", "-operator-v2-")
    elif args.operator_v2:
        suffix = suffix.replace("-v1-", "-operator-v2-")
        prerequisite_suffix = suffix
    run = PREFIX + "-" + args.phase + suffix
    if args.lossless_v3:
        if not args.operator_v2 or not args.pyvista_derived or args.phase != 'boundary':
            raise ValueError('lossless repair is only the original derived PyVista boundary')
        run += '-lossless-v3'
    if args.codec_guard_v4:
        if not args.lossless_v3:
            raise ValueError('guard correction requires explicit lossless repair')
        run = run.replace('-lossless-v3', '-lossless-v4')
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    if args.operator_v2 and (os.environ.get("ATMEM_BENCHMARK_LOCAL_WSL") != "1"
                            or os.environ.get("ATMEM_BENCHMARK_PER_RUN_VAULTS") != "1"):
        raise ValueError("operator-v2 requires Windows-local per-run evidence")
    from benchmarks.code_replay.run_evidence import operational_evidence
    vault = operational_evidence(EVIDENCE_ROOT, vault_id="confirmation-v1", scope=scope, writing_run=run)
    if vault.inspect(principal, run):
        raise ValueError("control exists; inspect its original handle, never implicitly restart")
    if args.codec_guard_v4:
        stopped = vault.inspect(principal, run.replace('-lossless-v4', '-lossless-v3'))
        kinds = [event['envelope']['event_type'] for event in stopped]
        if kinds != ['external.runtime_projection_planned']:
            raise ValueError('guard repair requires the proved one-plan zero-worker stop')
    prior = [event["envelope"] for event in vault.inspect(principal, PRIOR)]
    def only(kind):
        found = [row["payload"] for row in prior if row["event_type"] == kind]
        if len(found) != 1:
            raise ValueError("one terminal predecessor and exact plan required: " + kind)
        return found[0]
    plan = only("external.confirmation_reference_planned")
    terminal = only("external.confirmation_reference_completed")
    source = plan["worker_source"]
    if sha256(source.encode()).hexdigest() != plan["worker_sha256"]:
        raise ValueError("retained predecessor source digest differs")
    source, registration = projected_control_source(source, plan["operator_task_registration"])
    materials, images = {}, {}
    for row in prior:
        if row["event_type"] == "external.confirmation_private_material":
            material = row["payload"]
            if material["instance_id"] in materials:
                raise ValueError("duplicate private material")
            materials[material["instance_id"]] = material
        elif row["event_type"] == "external.confirmation_reference_dispatch":
            item = row["payload"]
            image = next(value for value in item["job"]["command"]
                         if value.startswith("swebench/") and "@sha256:" in value)
            previous = images.setdefault(item["instance_id"], image)
            if previous != image:
                raise ValueError("image identity changed between predecessor phases")
    identities = plan["runtime_eligible"]
    if len(identities) != len(set(identities)) or set(identities) != set(materials) or set(identities) != set(images):
        raise ValueError("complete immutable same-pool material/image inventory required")
    if args.supplemental_oci:
        from benchmarks.code_replay.external_catalog import digest
        from benchmarks.code_replay.windows_oci_images import RUN as OCI_RUN
        from benchmarks.code_replay.windows_confirmation_images import runtime_evidence_qualifies
        oci = [event["envelope"] for event in vault.inspect(principal, OCI_RUN)]
        endings = [row["payload"] for row in oci if row["event_type"] == "external.oci_images_completed"]
        if len(endings) != 1:
            raise ValueError("supplemental OCI image controls must be terminal")
        supplemental = endings[0]["new_runtime_qualified"]
        if set(supplemental) & set(identities) or len(supplemental) != len(set(supplemental)):
            raise ValueError("supplemental identities overlap existing runtime controls")
        registry = {row["payload"]["instance_id"]: row["payload"] for row in oci
                    if row["event_type"] == "external.oci_registry_result"}
        runtimes = {row["payload"]["instance_id"]: row["payload"] for row in oci
                    if row["event_type"] == "external.oci_runtime_result"}
        added = {row["payload"]["instance_id"]: row["payload"] for row in oci
                 if row["event_type"] == "external.oci_material_result"}
        for identity in supplemental:
            if (identity not in plan["operator_task_registration"]["bindings"]
                or not runtime_evidence_qualifies(runtimes[identity], registry[identity]["descriptor"])
                or runtimes[identity]["image"] != registry[identity]["image"]
                or added[identity].get("verified") is not True
                or digest(added[identity]["material"]) != added[identity]["material_sha256"]):
                raise ValueError("supplemental image/material identity differs")
            materials[identity] = added[identity]["material"]
            images[identity] = registry[identity]["image"]
        identities = supplemental
    derived_build_run = None
    if args.pyvista_derived:
        from benchmarks.code_replay.derived_runtime import verified_build_result, qualified_build_records
        from benchmarks.code_replay.windows_pyvista_build import RUN, OPERATOR_RUN
        BUILD_RUN = OPERATOR_RUN if args.operator_v2 else RUN
        derived_build_run = BUILD_RUN
        builds = [event["envelope"] for event in vault.inspect(principal, BUILD_RUN)]
        endings = [row["payload"] for row in builds if row["event_type"] == "external.pyvista_build_completed"]
        expected = {identity for identity in identities if identity.startswith("pyvista__")}
        if len(endings) != 1:
            raise ValueError("all original PyVista build attempts must be terminal before controls")
        records = [row["payload"] for row in builds if row["event_type"] == "external.pyvista_build_result"]
        qualified_records = qualified_build_records(records, endings[0], expected)
        for row in qualified_records:
            identity = row["instance_id"]
            result = verified_build_result(row, images[identity])
            images[identity] = result["derived_image_id"]
        admitted = {row["instance_id"] for row in qualified_records}
        identities = [identity for identity in identities if identity in admitted]
    if args.phase != "inventory":
        inventory = [event["envelope"] for event in vault.inspect(principal, PREFIX + "-inventory" + prerequisite_suffix)]
        endings = [row for row in inventory if row["event_type"] == "external.runtime_projection_completed"]
        if len(endings) != 1:
            raise ValueError("inventory must be terminal")
        qualified = endings[0]["payload"]["qualified_identities"]
        identities = [identity for identity in identities if identity in qualified]
    reference_run = None
    if args.phase == "boundary":
        reference_run = PREFIX + "-reference" + prerequisite_suffix
        reference = [event["envelope"] for event in vault.inspect(principal, reference_run)]
        endings = [row["payload"] for row in reference if row["event_type"] == "external.runtime_projection_completed"]
        if len(endings) != 1:
            raise ValueError("source assembly requires terminal same-projection reference qualification")
        identities = [identity for identity in identities if identity in endings[0]["qualified_identities"]]
    phases = {"inventory": ("inventory",), "reference": ("parent", "reference"),
              "boundary": ("unchanged", "reference_as_proposal")}[args.phase]
    program = (bootstrap_source(source, result_transport="lzma-v2" if args.lossless_v3 else "zlib-v1", runtime_projection=True)
               if args.phase == "boundary" else projection_program(source, diagnostic=args.phase == "inventory"))
    def save(kind, payload):
        return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    save("external.runtime_projection_planned", {
        "prior_run": PRIOR, "predecessor_terminal": terminal,
        "phase": args.phase, "identities": identities, "phases": list(phases),
        "supplemental_original_oci_candidates": args.supplemental_oci,
        "derived_build_prerequisite": derived_build_run,
        "reference_prerequisite": reference_run,
        "original_runtime_eligible": plan["runtime_eligible"], "model_calls": 0,
        "driver_source": Path(__file__).read_text(), "program": program,
        "program_sha256": sha256(program.encode()).hexdigest(),
        "projection_registration": registration, "modules": projection_modules(),
        "source_capture_source": Path(__file__).with_name("source_capture.py").read_text(),
        "source_boundary_source": Path(__file__).with_name("external_candidate_worker.py").read_text(),
        "spec": Path("specs/042-atmem-code/source-runtime-projection-v2.md").read_text(),
        "all_previous_failures_preserved": True, "max_workers": 4,
        "network": False, "test_sets_changed": False,
    })
    results = {}
    reused_cells = set()
    if args.operator_v2 and (not args.pyvista_derived or args.lossless_v3):
        from atmem.core.canonical import canonical_json
        from benchmarks.code_replay.projection_evidence import recover_projection_stream, verified_projection_controller
        predecessor_run = PREFIX + "-boundary" + prerequisite_suffix
        predecessor = vault.inspect(principal, predecessor_run)
        before_plans = [event["envelope"]["payload"] for event in predecessor
                        if event["envelope"]["event_type"] == "external.runtime_projection_planned"]
        expected_program = before_plans[0]['program'] if len(before_plans) == 1 else None
        if args.lossless_v3 and expected_program:
            expected_program = codec_only_program(before_plans[0], Path(__file__).with_name('result_transport.py').read_text())
        if len(before_plans) != 1 or expected_program != program:
            raise ValueError("resource handoff requires the identical prior worker program")
        by_id = {event["object_id"]: event for event in predecessor}
        for event in predecessor:
            envelope = event["envelope"]
            if envelope["event_type"] != "external.runtime_projection_result":
                continue
            row = envelope["payload"]
            identity, phase = row["instance_id"], row["phase"]
            if identity not in identities or phase not in phases or (identity, phase) in reused_cells:
                raise ValueError("prior completed source cells differ from the fixed handoff")
            for descriptor in row["streams"].values():
                recover_projection_stream(by_id, descriptor)
            controller = row.get("controller", {})
            if args.lossless_v3 and controller.get('exit_code') != 0:
                raw = recover_projection_stream(by_id, row['streams']['stdout'])
                observed = json.loads(raw)
                failure = base64.b64decode(observed.get('raw_output_base64', ''), validate=True)
                if (identity != 'pyvista__pyvista-4853' or observed.get('exit_code') != 1
                    or observed.get('reason') or observed.get('raw_output_truncated') is not False
                    or not failure.endswith(b'ValueError: encoded result budget exceeded\n')):
                    raise ValueError('only proved response-encoding failures can execute again')
                save('external.runtime_projection_encoding_failure_preserved', {
                    'instance_id': identity, 'phase': phase, 'prior_run': predecessor_run,
                    'prior_object_id': event['object_id'], 'not_a_model_or_grade_retry': True})
                continue
            if (row.get("transport_exit") == 0 and not row.get("transport_failure")
                and not row.get("decode_failure") and controller.get("exit_code") == 0
                and not controller.get("reason") and not controller.get("raw_output_truncated")):
                verified_projection_controller(predecessor, row)
            results.setdefault(identity, {})[phase] = row
            reused_cells.add((identity, phase))
            save("external.runtime_projection_reused_result", {
                "instance_id": identity, "phase": phase, "prior_run": predecessor_run,
                "prior_object_id": event["object_id"],
                "prior_payload_sha256": sha256(canonical_json(row).encode()).hexdigest(),
                "complete_record_reused": True, "new_test_execution": False,
                "negative_records_not_retried": True})
    jobs = []
    for identity in identities:
        for phase in phases:
            if (identity, phase) in reused_cells:
                continue
            name = "atmem-reference-control-" + uuid4().hex
            if args.pyvista_derived:
                from benchmarks.code_replay.derived_runtime import local_worker_command
                command = local_worker_command(images[identity], name, program)
            else:
                command = worker_command(images[identity], name, program)
            if args.phase == "inventory":
                command.insert(3, "--read-only")
                payload = {"instance_id": identity, "base_commit": materials[identity]["base_commit"]}
            elif args.phase == "reference":
                payload = {**materials[identity], "phase": phase}
            else:
                payload = {**materials[identity], "source_boundary_phase": phase,
                           "task_profile": "registered-eligibility-v2"}
            job = {"program": worker_program(), "name": name, "command": command, "payload": payload}
            save("external.runtime_projection_dispatch", {"instance_id": identity, "phase": phase, "job": job})
            jobs.append((identity, phase, job))
    def execute(item):
        identity, phase, job = item
        try:
            proc = subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=205)
            stdout, stderr, status, failure = proc.stdout, proc.stderr, proc.returncode, None
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, status, failure = exc.stdout or b"", exc.stderr or b"", None, "transport_timeout"
        except OSError as exc:
            stdout, stderr, status, failure = b"", b"", None, type(exc).__name__ + ": " + str(exc)
        row = {"instance_id": identity, "phase": phase, "transport_exit": status,
               "transport_failure": failure, "streams": {}}
        for stream, raw in (("stdout", stdout), ("stderr", stderr)):
            parts = []
            for offset in range(0, len(raw), 3_000_000):
                parts.append(save("external.runtime_projection_chunk", {"instance_id": identity,
                    "phase": phase, "stream": stream, "offset": offset,
                    "bytes_base64": base64.b64encode(raw[offset:offset + 3_000_000]).decode()}))
            row["streams"][stream] = {"sha256": sha256(raw).hexdigest(), "bytes": len(raw), "receipts": parts}
        if status == 0:
            try:
                controller = json.loads(stdout)
                if (not controller.get("reason") and controller.get("exit_code") == 0
                    and not controller.get("raw_output_truncated")):
                    wire = base64.b64decode(controller["raw_output_base64"], validate=True)
                    controller["worker"] = decode_result(wire)
                    decoded = json.dumps(controller["worker"], sort_keys=True, separators=(",", ":")).encode()
                    if len(decoded) > 3_000_000:
                        receipts = []
                        for offset in range(0, len(decoded), 3_000_000):
                            receipts.append(save("external.runtime_projection_decoded_chunk", {
                                "instance_id": identity, "phase": phase, "offset": offset,
                                "bytes_base64": base64.b64encode(decoded[offset:offset + 3_000_000]).decode()}))
                        row["decoded_worker_stream"] = {
                            "bytes": len(decoded), "sha256": sha256(decoded).hexdigest(), "receipts": receipts,
                            "encoding": "complete-canonical-json-not-a-source-subset"}
                        heavy = {"original_files_base64", "candidate_files_base64", "assembled_files_base64",
                                 "public_candidate_files_base64", "original_files_sha256"}
                        controller["worker"] = {key: value for key, value in controller["worker"].items() if key not in heavy}
                        row["worker_fields_projection"] = {
                            "omitted_from_inline_only": sorted(heavy & set(json.loads(decoded))),
                            "complete_result_retained": True}
                row["controller"] = controller
            except (ValueError, KeyError) as exc:
                row["decode_failure"] = type(exc).__name__ + ": " + str(exc)
        return row
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(execute, item) for item in jobs]):
            row = future.result()
            save("external.runtime_projection_result", row)
            results.setdefault(row["instance_id"], {})[row["phase"]] = row
            controller = row.get("controller", {})
            worker = controller.get("worker", {})
            print(json.dumps({"instance_id": row["instance_id"], "phase": row["phase"],
                "transport_exit": row["transport_exit"], "reason": controller.get("reason"),
                "decode_failure": row.get("decode_failure"), "summary": worker.get("summary"),
                "worker_failure": worker.get("worker_failure"), "grading": worker.get("grading")}), flush=True)
    qualified = []
    for identity, rows in results.items():
        valid = all(row.get("transport_exit") == 0 and not row.get("transport_failure")
                    and not row.get("decode_failure") for row in rows.values())
        controls = {phase: row.get("controller", {}) for phase, row in rows.items()}
        if args.phase == "inventory":
            worker = controls["inventory"].get("worker", {})
            valid = (valid and controls["inventory"].get("exit_code") == 0
                and not controls["inventory"].get("reason")
                and worker.get("summary", {}).get("format") == "atmem-source-runtime-projection-v2"
                and worker.get("tests_run") is False and worker.get("model_calls") == 0)
        elif args.phase == "reference":
            valid = valid and strict_reference_qualified(controls["parent"], controls["reference"])
        else:
            roots, tests = plan["operator_task_registration"]["source_profiles"][identity]
            # Expectations remain metadata-bound; never infer counts from observed outcomes.
            tests_json = json.loads(base64.b64decode(materials[identity]["task_files"]["tests.json"]["content_base64"]))
            valid = valid and boundary_qualified(controls, expected_f2p=len(tests_json["FAIL_TO_PASS"]),
                expected_p2p=len(tests_json["PASS_TO_PASS"]), source_roots=tuple(roots), test_roots=tuple(tests))
            valid = valid and all(row.get("worker", {}).get("runtime_fixtures_verified") is True
                                 for row in controls.values())
        if valid:
            qualified.append(identity)
    summary = {"phase": args.phase, "attempts": len(jobs), "candidate_results": len(results),
               "completed_phase_records_reused": len(reused_cells),
               "qualified_identities": sorted(qualified), "model_calls": 0,
               "confirmation_complete": False, "original_pool_unchanged": True}
    save("external.runtime_projection_completed", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
