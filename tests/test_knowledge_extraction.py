"""Extractor contract/worker boundaries; live extraction is a separate gate."""
from hashlib import sha256
import io
import json
import subprocess
import tarfile

import pytest

from atmem.code.contracts import CodeScope
from atmem.knowledge.contracts import SourceSnapshot
from atmem.knowledge.code.extractor import ExtractionArtifacts, parse_artifacts
from atmem.knowledge.code.mapping import map_facts
from atmem.knowledge.worker import ExtractionWorker, source_archive

SCOPE = CodeScope("user", "project", "shared", "codex")
DATA = b"def main():\n    return 1\n"
DIGEST = sha256(DATA).hexdigest()
SNAPSHOT = SourceSnapshot(SCOPE, "worktree", "a" * 40, (("main.py", DIGEST),), "a" * 64)


def fact(name="main", file="main.py", **fields):
    result = {"kind": "symbol", "name": name, "repo": "repository", "file": file, "line": 1, **fields}
    result["id"] = sha256("\0".join(result[k] for k in ("repo", "kind", "name", "file")).encode()).hexdigest()[:32]
    return result


def artifacts(rows=None, **receipt_changes):
    rows = [fact()] if rows is None else rows
    raw = b"".join(json.dumps(r).encode() + b"\n" for r in rows)
    receipt = {"format_version": 1, "enola_version": "0.4.26", "extractor_version": "v287", "fact_count": len(rows), **receipt_changes}
    return ExtractionArtifacts(raw, json.dumps(receipt).encode())


def test_parse_map_bound_to_source_and_writer_id():
    rows, receipt, insights = parse_artifacts(artifacts())
    mapped = map_facts(SNAPSHOT, rows)
    assert mapped["objects"][0].anchors[0].content_sha256 == DIGEST
    assert mapped["objects"][0].object_id == "fact-" + rows[0]["id"]
    assert receipt["fact_count"] == 1 and insights == []
    with pytest.raises(ValueError, match="outside"):
        map_facts(SNAPSHOT, [fact(file="unknown.py")])


@pytest.mark.parametrize("changes", [{"format_version": True}, {"format_version": 2}, {"enola_version": "latest"},
                                      {"extractor_version": "future"}, {"fact_count": 0}, {"fact_count": True},
                                      {"providers": [{"name": "execute-command"}]}])
def test_receipt_failure_is_not_warning_and_partial_success(changes):
    with pytest.raises(ValueError):
        parse_artifacts(artifacts(**changes))


def test_corrupt_duplicate_nonfinite_and_identity_fail_closed():
    good = artifacts()
    for raw in [b"{}", b"{broken", b'{"x":1,"x":2}', b'{"x":NaN}', good.facts_jsonl.replace(b'"main"', b'"invented"')]:
        with pytest.raises(ValueError):
            parse_artifacts(ExtractionArtifacts(raw, good.receipt_json))


def test_missing_target_stays_unresolved_even_when_name_matches():
    first = fact(relations=[{"kind": "calls", "target": "other"}])
    second = fact("other")
    mapped = map_facts(SNAPSHOT, parse_artifacts(artifacts([first, second]))[0])
    assert mapped["relations"][0].target_id is None
    first["relations"][0]["target_id"] = second["id"]
    mapped = map_facts(SNAPSHOT, parse_artifacts(artifacts([first, second]))[0])
    assert mapped["relations"][0].target_id == "fact-" + second["id"]


def test_duplicate_writer_records_combine_locations_keep_conflicts():
    rows = [fact(props={"role": "first"}), fact(line=2, props={"role": "second"})]
    mapped = map_facts(SNAPSHOT, parse_artifacts(artifacts(rows))[0])
    assert len(mapped["objects"]) == 1
    assert len(mapped["objects"][0].anchors) == 2
    assert len(mapped["property_variants"][mapped["objects"][0].object_id]) == 2
    assert mapped["conflicts"]


def test_same_name_different_files_never_collapses():
    snapshot = SourceSnapshot(SCOPE, "worktree", "a" * 40, (("a.py", DIGEST), ("b.py", DIGEST)), "a" * 64)
    mapped = map_facts(snapshot, parse_artifacts(artifacts([fact(file="a.py"), fact(file="b.py")]))[0])
    assert len({obj.object_id for obj in mapped["objects"]}) == 2


def test_mapping_computes_snapshot_identity_once_not_per_symbol(monkeypatch):
    original = SourceSnapshot.snapshot_id.fget
    calls = []
    def measured(snapshot):
        calls.append(snapshot)
        return original(snapshot)
    monkeypatch.setattr(SourceSnapshot, 'snapshot_id', property(measured))
    rows = [fact(f'method_{i}') for i in range(30)]
    mapped = map_facts(SNAPSHOT, rows, source_bytes={'main.py': DATA})
    assert len(mapped['objects']) == 30 and len(calls) == 1
    assert {obj.snapshot_id for obj in mapped['objects']} == {original(SNAPSHOT)}


def test_root_module_is_directory_not_an_invented_file_anchor():
    row = fact(name=".", file=".", kind="module")
    mapped = map_facts(SNAPSHOT, parse_artifacts(artifacts([row]))[0])
    assert mapped["objects"][0].kind == "module"
    assert mapped["objects"][0].anchors == ()


def test_derived_module_rollup_can_name_authorized_package_without_anchor():
    path = "package/nodes/__init__.py"
    snapshot = SourceSnapshot(SCOPE, "worktree", "a" * 40, ((path, DIGEST),), "a" * 64)
    row = fact(name="module-edge: package/nodes -> package/interpreter", file="package/nodes", kind="dependency",
        props={"coupling_kind": "symbol-rollup", "derived": "symbol-rollup", "symbol_edges": 2})
    rows = parse_artifacts(artifacts([row]))[0]
    mapped = map_facts(snapshot, rows, source_bytes={path: DATA})
    assert mapped["objects"][0].object_id == "fact-" + row["id"]
    assert mapped["objects"][0].anchors == ()
    location = mapped["source_locations"]["fact-" + row["id"]][0]
    assert location["path"] == "package/nodes" and location["kind"] == "directory"
    assert location["content_sha256"] is None and location["line"] is None


def test_root_module_rollup_preserves_writer_identity_and_is_not_a_file_anchor():
    row = fact(name='module-edge: . -> package', file='.', kind='dependency',
        props={'coupling_kind': 'symbol-rollup', 'derived': 'symbol-rollup'})
    parsed = parse_artifacts(artifacts([row]))[0]
    mapped = map_facts(SNAPSHOT, parsed, source_bytes={'main.py': DATA})
    assert mapped['objects'][0].object_id == 'fact-' + row['id']
    assert mapped['objects'][0].anchors == ()
    assert mapped['source_locations']['fact-' + row['id']][0]['kind'] == 'directory'
    # A root path alone does not grant a dependency directory authority.
    with pytest.raises(ValueError, match='outside'):
        map_facts(SNAPSHOT, [fact(name='unproven', file='.', kind='dependency')])


@pytest.mark.parametrize("change", ["unknown_directory", "symbol_claim", "not_derived", "untyped_name"])
def test_module_rollup_does_not_authorize_arbitrary_source(change):
    snapshot = SourceSnapshot(SCOPE, "worktree", "a" * 40, (("package/nodes/a.py", DIGEST),), "a" * 64)
    row = fact(name="module-edge: package/nodes -> other", file="package/nodes", kind="dependency",
        props={"coupling_kind": "symbol-rollup", "derived": "symbol-rollup"})
    if change == "unknown_directory":
        row.update(file="outside", name="module-edge: outside -> other")
    elif change == "symbol_claim":
        row["kind"] = "symbol"
    elif change == "not_derived":
        row["props"] = {}
    else:
        row["name"] = "arbitrary dependency"
    with pytest.raises(ValueError, match="outside"):
        map_facts(snapshot, [row])


def test_extraction_coverage_account_names_repository_not_a_source_file():
    row = fact(kind="extraction", name="mdintent:links", file="repository")
    mapped = map_facts(SNAPSHOT, parse_artifacts(artifacts([row]))[0])
    assert mapped["objects"][0].kind == "extraction"
    assert mapped["objects"][0].assurance == "declared"
    assert mapped["objects"][0].anchors == ()
    with pytest.raises(ValueError, match="outside"):
        map_facts(SNAPSHOT, [fact(kind="extraction", name="mdintent:links", file="outside.py")])


def test_unknown_line_is_not_invented_and_measured_span_must_fit_source():
    row = fact()
    del row["line"]
    mapped = map_facts(SNAPSHOT, [row], source_bytes={"main.py": DATA})
    assert mapped["objects"][0].anchors == ()
    assert mapped["source_locations"][mapped["objects"][0].object_id][0]["line"] is None
    with pytest.raises(ValueError, match="exceeds actual file"):
        map_facts(SNAPSHOT, [fact(line=500)], source_bytes={"main.py": DATA})


def test_worker_input_no_config_or_unbound_bytes():
    output = source_archive(SNAPSHOT, {"main.py": DATA})
    with tarfile.open(fileobj=io.BytesIO(output)) as tar:
        assert tar.getnames() == ["main.py"]
        assert tar.extractfile("main.py").read() == DATA
    for files in [{"main.py": b"changed"}, {"main.py": DATA, "mcp-arch.yaml": b"providers: []"}]:
        with pytest.raises(ValueError):
            source_archive(SNAPSHOT, files)


def test_authorization_before_launch_and_immutable_image(monkeypatch):
    with pytest.raises(ValueError):
        ExtractionWorker("image:latest")
    def no_launch(*args, **kwargs):
        pytest.fail("unauthorized request reached subprocess")
    monkeypatch.setattr(subprocess, "run", no_launch)
    def deny(scope):
        raise PermissionError("scope denied")
    with pytest.raises(PermissionError):
        ExtractionWorker("sha256:" + "a" * 64).extract(SNAPSHOT, {"main.py": DATA}, authorize=deny)


def test_worker_has_no_host_mounts_network_or_credential_environment(monkeypatch):
    captured = []
    def run(command, **kwargs):
        captured.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, b"", b"failure")
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError):
        ExtractionWorker("sha256:" + "a" * 64).extract(SNAPSHOT, {"main.py": DATA}, authorize=lambda scope: None)
    command, kwargs = captured[0]
    assert "--network=none" in command and "--read-only" in command and "--pull=never" in command
    assert "--log-driver=none" in command and "--cap-drop=ALL" in command
    assert not any(arg in command for arg in ("-v", "--volume", "--mount", "-e", "--env", "--privileged"))
    assert kwargs["timeout"] == 150


def test_worker_failure_diagnostics_do_not_reflect_source_or_secret_stderr(monkeypatch):
    marker = b'PRIVATE_SOURCE_MARKER'
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs:
        subprocess.CompletedProcess(command, 1, b'', marker + b' invalid extraction output'))
    with pytest.raises(RuntimeError, match='reason=artifact_envelope') as error:
        ExtractionWorker('sha256:' + 'a' * 64).extract(SNAPSHOT, {'main.py': DATA}, authorize=lambda scope: None)
    assert marker.decode() not in str(error.value)


def test_large_insight_artifact_is_bounded_not_silently_discarded():
    good = artifacts()
    raw = json.dumps([{'title': 'Public structural finding', 'description': 'x' * 300000}]).encode()
    _, _, insights = parse_artifacts(ExtractionArtifacts(good.facts_jsonl, good.receipt_json, raw))
    assert insights[0]['description'] == 'x' * 300000
    with pytest.raises(ValueError, match='insights'):
        parse_artifacts(ExtractionArtifacts(good.facts_jsonl, good.receipt_json,
            json.dumps([{'description': 'x' * 2_000_000}]).encode()))
    with pytest.raises(ValueError, match='artifact budget'):
        parse_artifacts(good, max_bytes=1)
    with pytest.raises(ValueError, match='fact budget'):
        parse_artifacts(artifacts([fact('one'), fact('two')]), max_facts=1)


def test_high_fanout_fact_is_not_confused_with_unbounded_traversal():
    relations = [{'kind': 'calls', 'target': f'public_api_{i}'} for i in range(2100)]
    parsed, _, _ = parse_artifacts(artifacts([fact(relations=relations)]))
    assert parsed[0]['relations'] == relations
    assert map_facts(SNAPSHOT, parsed)['relations'][0].target_id is None
