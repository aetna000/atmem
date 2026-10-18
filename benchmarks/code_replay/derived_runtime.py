"""Explicit operator-only local-image binding; ordinary image policy stays strict."""
import re

from benchmarks.code_replay.external_qualification import worker_command


def local_worker_command(image_id, name, source):
    if type(image_id) is not str or re.fullmatch("sha256:[0-9a-f]{64}", image_id) is None:
        raise ValueError("verified local image content ID required")
    placeholder = "swebench/sweb.eval.x86_64.operator-local@sha256:" + "0" * 64
    command = worker_command(placeholder, name, source)
    command[command.index(placeholder)] = image_id
    command[command.index("--label") + 1] = "atmem.benchmark=derived-runtime-control-v1"
    return command


def vtk_recipe(image, wheels):
    if re.fullmatch(r"swebench/sweb\.eval\.x86_64\.pyvista_1776_pyvista-[0-9]+@sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("original immutable PyVista image required")
    expected = {"vtk": "9.3.1", "setuptools": "78.1.1", "wheel": "0.45.1"}
    if len(wheels) != 3 or {item["package"]: item["version"] for item in wheels} != expected:
        raise ValueError("exact fixed offline wheel versions required")
    for item in wheels:
        if (re.fullmatch("[A-Za-z0-9_.-]+[.]whl", item["filename"]) is None
            or re.fullmatch("[0-9a-f]{64}", item["sha256"]) is None
            or type(item["bytes"]) is not int or not 1 <= item["bytes"] <= 128_000_000):
            raise ValueError("bounded verified offline wheel artifact required")
    vtk = next(item["filename"] for item in wheels if item["package"] == "vtk")
    return ("FROM " + image + "\n"
        "COPY " + " ".join(item["filename"] for item in wheels) + " /opt/atmem-benchmark-wheels/\n"
        "ENV PIP_NO_INDEX=1 PIP_FIND_LINKS=/opt/atmem-benchmark-wheels\n"
        "RUN /opt/miniconda3/envs/testbed/bin/python -I -m pip install "
        "--no-index --no-deps --no-cache-dir --disable-pip-version-check "
        "/opt/atmem-benchmark-wheels/" + vtk + "\n")


def distribution_change_qualified(before, after):
    """Complete installed distribution inventories may differ only in fixed VTK."""
    def inventory(rows):
        result = {}
        for row in rows:
            if (set(row) != {"name", "version"} or type(row["name"]) is not str
                or type(row["version"]) is not str or not row["name"] or not row["version"]):
                raise ValueError("exact installed distribution identity required")
            name = re.sub("[-_.]+", "-", row["name"]).lower()
            if name in result:
                raise ValueError("duplicate installed distribution identity")
            result[name] = row["version"]
        return result
    a, b = inventory(before), inventory(after)
    return bool(a.get("vtk") == "9.4.2" and b.get("vtk") == "9.3.1"
                and a.get("setuptools") == b.get("setuptools") == "78.1.1"
                and a.get("wheel") == b.get("wheel") == "0.45.1"
                and {k: v for k, v in a.items() if k != "vtk"}
                    == {k: v for k, v in b.items() if k != "vtk"})


def verified_build_result(row, original_image):
    """Recheck recorded transport and audit bytes before admitting a local image."""
    import base64
    import json
    from benchmarks.code_replay.result_transport import decode_result
    if row.get("transport_exit") != 0:
        raise ValueError("complete derived build transport required")
    result = json.loads(base64.b64decode(row["stdout_base64"], validate=True))
    if result != row["result"] or result.get("original_image") != original_image:
        raise ValueError("derived build metadata differs from retained transport")
    if any(result.get(key) is not True for key in (
        "qualified", "installed_distributions_verified", "source_runtime_unchanged", "original_image_retained"
    )) or result.get("tests_changed") is not False or result.get("cleanup_error"):
        raise ValueError("derived build did not qualify")
    image = result.get("derived_image_id")
    actual = result.get("derived_image", {})
    if (type(image) is not str or re.fullmatch("sha256:[0-9a-f]{64}", image) is None
        or actual.get("Id") != image or actual.get("Architecture") != "amd64" or actual.get("Os") != "linux"):
        raise ValueError("derived image content/platform identity differs")
    for role in ("before", "after"):
        audit = result[role]
        if audit.get("exit_code") != 0 or audit.get("reason") or audit.get("raw_output_truncated") is not False:
            raise ValueError("complete installed source/package audit required")
        raw = base64.b64decode(audit["raw_output_base64"], validate=True)
        if len(raw) != audit["output_bytes"] or decode_result(raw) != audit["worker"]:
            raise ValueError("derived source/package audit differs from retained bytes")
    before, after = result["before"]["worker"], result["after"]["worker"]
    if (not distribution_change_qualified(before["distributions"], after["distributions"])
        or before["summary"] != after["summary"] or before["runtime_manifest"] != after["runtime_manifest"]
        or before["pip_check"] != after["pip_check"]):
        raise ValueError("unexpected source/runtime/distribution change")
    if before["summary"].get("format") != "atmem-source-runtime-projection-v2":
        raise ValueError("verified source/runtime projection missing")
    environment = actual.get("Config", {}).get("Env", [])
    if (environment.count("PIP_NO_INDEX=1") != 1
        or environment.count("PIP_FIND_LINKS=/opt/atmem-benchmark-wheels") != 1):
        raise ValueError("offline setup environment missing")
    return result


def qualified_build_records(records, summary, expected):
    """Require a complete original pool, not success-impute failed environments."""
    expected = set(expected)
    identities = [row["instance_id"] for row in records]
    if (len(expected) != 8 or len(identities) != 8 or len(set(identities)) != 8
        or set(identities) != expected or summary.get("original_candidates") != 8):
        raise ValueError("exact eight terminal original build records required")
    qualified = [row for row in records
                 if row.get("transport_exit") == 0 and row.get("result", {}).get("qualified") is True]
    declared = summary.get("qualified_identities", [])
    if (len(declared) != len(set(declared))
        or set(declared) != {row["instance_id"] for row in qualified}):
        raise ValueError("derived build summary differs from complete records")
    # Every admitted record is still byte-verified by verified_build_result.
    # Failed candidates remain in the original pool and attrition report.
    return qualified
