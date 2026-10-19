from hashlib import sha256
import json
import subprocess

import pytest

from atmem.code.identity import repository_key
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.extractor import ExtractionArtifacts
from atmem.knowledge.code.queries import query_current


def init_repository(env):
    subprocess.run(["git", "init", str(env.root)], check=True, capture_output=True)
    env.memory.store.bind_code_project(subject_id="local", repository_key=repository_key(env.root), project_id=env.project, remote_sha256=None)
    (env.root / "main.py").write_text("def main():\n    return 1\n")
    subprocess.run(["git", "-C", str(env.root), "add", "main.py"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(env.root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"], check=True, capture_output=True)
    env.app.settings(env.project, {"graph_enabled": True})


class FixtureWorker:
    """Boundary fixture only; not a qualified extractor or agent benchmark."""
    image_id = "sha256:" + "a" * 64
    def extract(self, snapshot, files, *, authorize):
        authorize(snapshot.scope)
        row = {"kind": "symbol", "name": "main", "file": "main.py", "line": 1, "repo": "repository"}
        row["id"] = sha256(b"repository\0symbol\0main\0main.py").hexdigest()[:32]
        return ExtractionArtifacts(json.dumps(row).encode() + b"\n", json.dumps({
            "format_version": 1, "enola_version": "0.4.26", "extractor_version": "v287", "fact_count": 1}).encode())


def test_atomic_current_unchanged_and_edit_invalidation(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    first = knowledge.index(str(env.root), FixtureWorker())
    assert first["status"] == "published" and first["generation"] == 1
    assert knowledge.index(str(env.root), FixtureWorker())["status"] == "unchanged"
    assert query_current(knowledge, str(env.root))["result"]["total"] == 1
    (env.root / "main.py").write_text("def changed(): pass\n")
    assert knowledge.current(str(env.root)) is None
    assert query_current(knowledge, str(env.root))["status"] == "not_current"
    assert knowledge.index(str(env.root), FixtureWorker())["generation"] == 2


def test_oversized_regular_source_is_explicitly_omitted_not_truncated(code_env):
    from atmem.knowledge.projections import read_authorized_file, SourceFileBudgetExceeded
    env = code_env
    init_repository(env)
    (env.root / 'generated.py').write_bytes(b'#' + b'x' * 300000)
    with pytest.raises(SourceFileBudgetExceeded):
        read_authorized_file(env.root, 'generated.py', 262144)
    class Checking(FixtureWorker):
        def extract(self, snapshot, files, *, authorize):
            assert 'generated.py' not in files and 'generated.py' not in dict(snapshot.files)
            return super().extract(snapshot, files, authorize=authorize)
    knowledge = CodeKnowledge(env.app, env.scope)
    result = knowledge.index(str(env.root), Checking())
    assert result['excluded_counts']['file_budget'] == 1
    assert knowledge.current(str(env.root))['excluded_counts']['file_budget'] == 1
    assert knowledge.context(str(env.root), 'main', budget=1024)['excluded_counts']['file_budget'] == 1
    assert query_current(knowledge, str(env.root))['excluded_counts']['file_budget'] == 1
    # Changing the omission set cannot retain the previous coverage receipt.
    (env.root / 'generated.py').unlink()
    assert knowledge.current(str(env.root)) is None


def test_new_oversized_file_invalidates_prior_complete_coverage(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    (env.root / 'large.py').write_bytes(b'#' + b'x' * 300000)
    assert knowledge.current(str(env.root)) is None
    assert knowledge.index(str(env.root), FixtureWorker())['excluded_counts']['file_budget'] == 1
    (env.root / 'large.py').write_text('def now_covered(): pass\n')
    assert knowledge.current(str(env.root)) is None


def test_omission_does_not_relax_aggregate_source_budget(code_env):
    env = code_env
    init_repository(env)
    (env.root / 'a.py').write_text('#' + 'a' * 100)
    (env.root / 'b.py').write_text('#' + 'b' * 100)
    knowledge = CodeKnowledge(env.app, env.scope)
    with pytest.raises(ValueError, match='generation budget'):
        knowledge.capture(str(env.root), 'a' * 64, max_file_bytes=200, max_source_bytes=150)


def test_index_admits_worker_sized_repository_and_revalidates_same_envelope(code_env):
    """A complete >6 MB graph is current, but strict identity stays bounded."""
    env = code_env
    init_repository(env)
    for index in range(25):
        (env.root / f'module_{index}.py').write_bytes(b'# ' + b'x' * 249998)
    knowledge = CodeKnowledge(env.app, env.scope)
    with pytest.raises(ValueError, match='generation budget'):
        knowledge.capture(str(env.root), 'a' * 64)
    class Checking(FixtureWorker):
        def extract(self, snapshot, files, *, authorize):
            assert len(files) == 26
            assert sum(map(len, files.values())) > 6_000_000
            return super().extract(snapshot, files, authorize=authorize)
    assert knowledge.index(str(env.root), Checking())['status'] == 'published'
    assert knowledge.current(str(env.root)) is not None
    assert knowledge.index(str(env.root), Checking())['status'] == 'unchanged'
    (env.root / 'module_0.py').write_text('def changed(): pass\n')
    assert knowledge.current(str(env.root)) is None


def test_non_source_assets_do_not_consume_eligible_file_budget(code_env, monkeypatch):
    import atmem.knowledge.projections as projections
    env = code_env
    init_repository(env)
    real_git = projections._git
    def git(root, *args):
        if args[0] == 'ls-files':
            return '\0'.join(['main.py', *(f'images/asset_{i}.png' for i in range(5001))])
        return real_git(root, *args)
    monkeypatch.setattr(projections, '_git', git)
    _, files, exclusions = CodeKnowledge(env.app, env.scope).capture(str(env.root), 'a' * 64)
    assert set(files) == {'main.py'}
    assert exclusions['unsupported_extension'] == 5001


def test_eligible_and_discovery_file_limits_are_still_enforced(code_env, monkeypatch):
    import atmem.knowledge.projections as projections
    env = code_env
    init_repository(env)
    real_git = projections._git
    monkeypatch.setattr(projections, 'INDEX_FILE_LIMIT', 1)
    (env.root / 'second.py').write_text('def second(): pass\n')
    knowledge = CodeKnowledge(env.app, env.scope)
    with pytest.raises(ValueError, match='eligible repository file budget'):
        knowledge.capture(str(env.root), 'a' * 64)
    monkeypatch.setattr(projections, '_git', lambda root, *args:
        '\0'.join(f'images/{i}.png' for i in range(50001)) if args[0] == 'ls-files' else real_git(root, *args))
    with pytest.raises(ValueError, match='discovery file budget'):
        knowledge.capture(str(env.root), 'a' * 64)


def test_omission_change_during_worker_cannot_publish_wrong_coverage(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    class RacingCoverage(FixtureWorker):
        def extract(self, *args, **kwargs):
            result = super().extract(*args, **kwargs)
            (env.root / 'large.py').write_bytes(b'#' + b'x' * 300000)
            return result
    with pytest.raises(ValueError, match='changed before publication'):
        knowledge.index(str(env.root), RacingCoverage())
    assert env.memory.store.code_documents('local', env.project, 'knowledge-generation') == []


def test_execution_identity_capture_stays_strict_when_graph_can_omit(code_env):
    from atmem.code.experience import CodeExperience
    from atmem.knowledge.projections import SourceFileBudgetExceeded
    env = code_env
    init_repository(env)
    (env.root / 'large.py').write_bytes(b'#' + b'x' * 2100000)
    knowledge = CodeKnowledge(env.app, env.scope)
    with pytest.raises(SourceFileBudgetExceeded):
        knowledge.capture(str(env.root), 'a' * 64)
    assert knowledge.index(str(env.root), FixtureWorker())['excluded_counts']['file_budget'] == 1
    experience = CodeExperience(env.app, env.scope, producer_keys={'fixture': b'0' * 32}, environment_sha256='a' * 64)
    with pytest.raises(SourceFileBudgetExceeded):
        experience.capture_snapshot(str(env.root))


def test_worker_failure_never_publishes_partial_generation(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    (env.root / "main.py").write_text("def new(): pass\n")
    class Broken(FixtureWorker):
        def extract(self, *args, **kwargs):
            raise RuntimeError("worker died")
    with pytest.raises(RuntimeError):
        knowledge.index(str(env.root), Broken())
    stored = env.memory.store.code_documents("local", env.project, "knowledge-generation")
    assert len(stored) == 1 and stored[0]["generation"] == 1
    assert knowledge.current(str(env.root)) is None


def test_unqueryable_projection_is_rejected_before_publication(code_env, monkeypatch):
    from atmem.knowledge.code import queries
    env = code_env
    init_repository(env)
    monkeypatch.setattr(queries, 'MAX_GRAPH_OBJECTS', 0)
    with pytest.raises(ValueError, match='execution budget'):
        CodeKnowledge(env.app, env.scope).index(str(env.root), FixtureWorker())
    assert env.memory.store.code_documents('local', env.project, 'knowledge-generation') == []


def test_racing_source_change_rejected_before_publication(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    class Racing(FixtureWorker):
        def extract(self, *args, **kwargs):
            result = super().extract(*args, **kwargs)
            (env.root / "main.py").write_text("def race(): pass\n")
            return result
    with pytest.raises(ValueError, match="changed before"):
        knowledge.index(str(env.root), Racing())
    assert env.memory.store.code_documents("local", env.project, "knowledge-generation") == []


def test_foreign_subject_denied_before_source_inspection(code_env):
    from dataclasses import replace
    with pytest.raises(PermissionError):
        CodeKnowledge(code_env.app, replace(code_env.scope, subject_id="stranger"))


def test_scoped_clear_removes_projections_and_stales_preview(code_env):
    from atmem.code.deletion import CodeDeletion
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    deletion = CodeDeletion(env.app)
    preview = deletion.preview(env.project)
    assert preview["knowledge_document_count"] == 2
    (env.root / "main.py").write_text("def changed(): pass\n")
    knowledge.index(str(env.root), FixtureWorker())
    with pytest.raises(ValueError, match="changed since preview"):
        deletion.clear(env.project, preview["preview_token"])
    preview = deletion.preview(env.project)
    assert deletion.clear(env.project, preview["preview_token"])["local_verified"]
    assert knowledge.current(str(env.root)) is None


def test_deleted_source_withholds_without_crashing_native_memory(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    (env.root / "main.py").unlink()
    assert knowledge.current(str(env.root)) is None
    assert query_current(knowledge, str(env.root))["status"] == "not_current"


def test_no_follow_reader_rejects_symlink_directory_escape(tmp_path):
    from atmem.knowledge.projections import read_authorized_file
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("OUTSIDE_SOURCE_CANARY")
    root = tmp_path / "project"
    root.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        read_authorized_file(root, "linked/secret.py", 1024)
