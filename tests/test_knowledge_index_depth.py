"""Extractor contract controls, not coding-task or production-quality evidence."""
from hashlib import sha256
import json

import pytest

from atmem.knowledge.code.extractor import ExtractionArtifacts, insight_facts
from atmem.knowledge.code.mapping import map_facts
from atmem.knowledge.code.source_policy import eligible_source
from atmem.knowledge.code.queries import query_generation
from atmem.knowledge.projections import CodeKnowledge
from tests.test_knowledge_lifecycle import FixtureWorker, init_repository


@pytest.mark.parametrize("path", ["src/a.kt", "src/a.php", "src/a.scala", "src/a.dart", "api/a.proto",
    "infra/a.tf", "infra/a.hcl", "src/a.hpp", "src/a.cxx", "lib/a.mjs", "lib/a.cts", "lib/a.swift",
    "Cargo.lock", "Gemfile", "go.mod", "go.sum", "pom.xml", "project.csproj", "build.gradle.kts", "CMakeLists.txt",
    "app.vue", "app.svelte", "schema.graphql", "schema.prisma", "view.hbs", "lib.hpp", "lib.C", "web.PHP"])
def test_rich_source_envelope_admits_pinned_extractor_inputs(path):
    assert eligible_source(path)


def test_rich_capture_covers_more_than_syntax_fallback_and_keeps_secret_screen(code_env):
    init_repository(code_env)
    for name in ("app.kt", "app.php", "api.proto", "main.tf", "Gemfile", "Cargo.lock"):
        (code_env.root / name).write_text("// public contract fixture\n")
    (code_env.root / "private.kt").write_text('password = "not-a-real-production-secret"\n')
    snapshot, sources, exclusions = CodeKnowledge(code_env.app, code_env.scope).capture(str(code_env.root), "a" * 64)
    assert {"app.kt", "app.php", "api.proto", "main.tf", "Gemfile", "Cargo.lock"} <= set(sources)
    assert "private.kt" not in sources and exclusions["secret_screen"] == 1
    assert set(dict(snapshot.files)) == set(sources)


def test_upstream_insight_conversion_is_queryable_with_writer_bound_evidence(code_env):
    init_repository(code_env)
    class InsightWorker(FixtureWorker):
        def extract(self, snapshot, files, *, authorize):
            result = super().extract(snapshot, files, authorize=authorize)
            fact = json.loads(result.facts_jsonl)
            insights = [{"title": "Public source finding", "source": "cycles", "confidence": 1.0,
                "description": "Derived structural finding, not an execution result.", "informational": False,
                "metrics": {"nodes": 1}, "evidence": [{"symbol": "main", "fact_id": fact["id"]}]}]
            return ExtractionArtifacts(result.facts_jsonl, result.receipt_json, json.dumps(insights).encode())
    knowledge = CodeKnowledge(code_env.app, code_env.scope)
    knowledge.index(str(code_env.root), InsightWorker())
    generation = knowledge.current(str(code_env.root))
    result = query_generation(generation, operation="insights")["result"]
    assert result["total"] == 1
    assert result["insights"][0]["properties"]["metrics"] == {"nodes": 1}
    assert result["insights"][0]["evidence"][0]["name"] == "main"
    finding = next(row for row in generation["objects"] if row["kind"] == "insight")
    assert finding["assurance"] == "heuristic"


def test_finding_cannot_guess_unresolved_evidence_by_name(code_env):
    init_repository(code_env)
    knowledge = CodeKnowledge(code_env.app, code_env.scope)
    snapshot, files, _ = knowledge.capture(str(code_env.root), "a" * 64)
    raw = json.loads(FixtureWorker().extract(snapshot, files, authorize=lambda s: None).facts_jsonl)
    findings = insight_facts([{"title": "Finding", "evidence": [{"symbol": "main", "fact_id": "f" * 32}]}])
    mapped = map_facts(snapshot, [raw, *findings], source_bytes=files)
    assert mapped["relations"][0].target_id is None
    assert mapped["relations"][0].assurance == "unresolved"


def test_findings_are_screened_before_projection():
    with pytest.raises(ValueError):
        insight_facts([{"title": "password = not-a-real-production-secret"}])


@pytest.mark.parametrize("language,suffix", [("ruby", "rb"), ("php", "php")])
def test_coupling_virtual_location_is_not_an_invented_source_span(code_env, language, suffix):
    init_repository(code_env)
    folder = code_env.root / "ruby/examples"
    folder.mkdir(parents=True)
    (folder / "a.rb").write_text("def example; end\n")
    (code_env.root / "ruby/b.rb").write_text("def other; end\n")
    knowledge = CodeKnowledge(code_env.app, code_env.scope)
    snapshot, files, _ = knowledge.capture(str(code_env.root), "a" * 64)
    row = {"repo": "repository", "kind": "dependency", "name": "ruby/examples -> ruby",
        "file": "ruby/examples/_coupling." + suffix, "props": {"synthetic_coupling": True,
            "coupling_kind": "require", "source": "internal", "language": language}}
    row["id"] = sha256("\0".join((row["repo"], row["kind"], row["name"], row["file"])).encode()).hexdigest()[:32]
    mapped = map_facts(snapshot, [row], source_bytes=files)
    assert mapped["objects"][0].anchors == ()
    location = mapped["source_locations"]["fact-" + row["id"]][0]
    assert location["kind"] == "extractor_virtual" and location["content_sha256"] is None
    for bad in ({**row, "file": "outside/_coupling.rb"}, {**row, "name": "ruby/examples -> outside"},
                {**row, "props": {}}):
        with pytest.raises(ValueError, match="outside"):
            map_facts(snapshot, [bad], source_bytes=files)


def test_ansible_role_can_reference_an_admitted_directory_not_a_fake_file(code_env):
    init_repository(code_env)
    folder = code_env.root / "roles/app/tasks"
    folder.mkdir(parents=True)
    (folder / "main.yml").write_text("- name: Public task\n  debug:\n    msg: hello\n")
    snapshot, files, _ = CodeKnowledge(code_env.app, code_env.scope).capture(str(code_env.root), "a" * 64)
    row = {"id": "a" * 32, "repo": "repository", "kind": "symbol", "name": "roles/app.app",
           "file": "roles/app", "props": {"language": "ansible", "ansible_kind": "role", "symbol_kind": "type"}}
    mapped = map_facts(snapshot, [row], source_bytes=files)
    assert mapped["objects"][0].anchors == ()
    assert mapped["source_locations"]["fact-" + row["id"]][0]["kind"] == "directory"
    with pytest.raises(ValueError, match="outside"):
        map_facts(snapshot, [{**row, "file": "outside"}], source_bytes=files)


def test_delta_reports_real_generation_changes_and_unchanged_index_is_noop(code_env):
    from atmem.knowledge.code.queries import query_current
    init_repository(code_env)
    knowledge = CodeKnowledge(code_env.app, code_env.scope)
    first = knowledge.index(str(code_env.root), FixtureWorker())
    repo, = query_current(knowledge, str(code_env.root), operation="delta")["result"]["repositories"]
    assert repo["delta"]["nodes_added"] == 1 and repo["delta"]["nodes_updated"] == 0
    assert repo["receipt"]["extractor_version"] == "v287"
    assert knowledge.index(str(code_env.root), FixtureWorker())["status"] == "unchanged"
    assert query_current(knowledge, str(code_env.root), operation="delta")["result"]["repositories"][0] == repo
    (code_env.root / "main.py").write_text("def main():\n    return 2\n")
    assert query_current(knowledge, str(code_env.root), operation="delta")["status"] == "not_current"
    second = knowledge.index(str(code_env.root), FixtureWorker())
    assert second["generation"] == 2
    delta = query_current(knowledge, str(code_env.root), operation="delta")["result"]["repositories"][0]["delta"]
    assert delta["previous_snapshot_id"] == first["snapshot_id"]
    assert delta["files_changed"] == delta["nodes_updated"] == 1
    assert delta["nodes_removed"] == delta["nodes_added"] == 0


def test_repository_receipts_do_not_leak_restricted_graph_counts(code_env):
    init_repository(code_env)
    knowledge = CodeKnowledge(code_env.app, code_env.scope)
    knowledge.index(str(code_env.root), FixtureWorker())
    generation = knowledge.current(str(code_env.root))
    repository_id = generation["repository"]["id"]
    result = query_generation(generation, operation="delta", permitted_ids={repository_id})["result"]
    assert result["repositories"][0]["delta"] is None
    assert result["repositories"][0]["receipt"] is None
    legacy = dict(generation)
    del legacy["repository"]
    assert query_generation(legacy, operation="delta")["result"]["repositories"] == []
