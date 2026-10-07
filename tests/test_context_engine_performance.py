from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import urllib.request

from atmem import Memory


def test_local_embedding_route_is_deterministic_and_openai_compatible() -> None:
    from research.production_benchmarks.local_embedding_proxy import Handler, MODEL

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    body = json.dumps({"model": MODEL, "input": ["same text", "same text"]}).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/v1/embeddings",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert result["model"] == MODEL
    assert len(result["data"][0]["embedding"]) == 768
    assert result["data"][0]["embedding"] == result["data"][1]["embedding"]


def test_matched_longmem_report_rejects_unmatched_questions() -> None:
    from research.production_benchmarks.matched_results import aggregate_longmem

    rows = [
        {"method": "typed-local", "question_id": "a", "score_bool": True},
        {"method": "mem0-oss", "question_id": "b", "score_bool": True},
    ]
    try:
        aggregate_longmem(rows, ("typed-local", "mem0-oss"))
    except ValueError as exc:
        assert "not matched" in str(exc)
    else:
        raise AssertionError("unmatched arms must fail closed")


def test_controlled_reader_report_requires_matched_three_way_inputs() -> None:
    from research.production_benchmarks.matched_results import aggregate_longmem_controls

    base = {
        "question_id": "case-1",
        "reader_identity_sha256": "reader",
        "reader_prompt_sha256": "prompt",
        "memory_context_was_truncated": False,
    }
    rows = [
        {**base, "method": "typed-local", "score_bool": False,
         "memory_post_query_metadata": {"sufficiency": {"status": "partial"}}},
        {**base, "method": "verified-evidence", "score_bool": True},
        {**base, "method": "no-retrieval", "score_bool": False},
    ]
    report = aggregate_longmem_controls(rows)
    assert report["case_count"] == 1
    assert report["results"][0]["preliminary_contrast"] == "memory_pipeline_candidate"
    assert report["results"][0]["terminal_outcome"] is None

    try:
        aggregate_longmem_controls(rows[:-1])
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("missing no-memory control must fail closed")


def test_dolphin_removal_matching_is_conservative() -> None:
    from research.production_benchmarks.run_dolphin_removal_controls import (
        _atomic_removal_records,
        _gate_blocks_removed_requirement,
        _matching_records,
    )

    requirement = {
        "expected": "Deployment updates must go to the eng-releases channel.",
        "source_refs": ["registry/facts.yaml#fact:1"],
    }
    records = [
        {"id": "right", "content": "Deployment updates must go to eng-releases."},
        {"id": "wrong", "content": "The engineering team discussed deployment."},
    ]
    assert [row["id"] for row in _matching_records(records, requirement)] == ["right"]
    provenance_requirement = {
        "expected": "Canonical wording not present in the source.",
        "source_refs": ["session:004978"],
    }
    provenance_records = [
        {"id": "right", "source_session_id": "004978", "content": "raw words"},
        {"id": "wrong", "source_session_id": "004977", "content": "canonical wording"},
    ]
    assert [
        row["id"] for row in _matching_records(provenance_records, provenance_requirement)
    ] == ["right"]
    source_statement = lambda value: {
        "typed_unit": {
            "kind": "environment_state",
            "payload": {
                "entity": "source episode", "relation": "source statement",
                "value": value,
            },
        }
    }
    atomic_records = [
        {
            "id": "blue", "source_session_id": "004978",
            "content": "The deployment channel is eng-releases.",
            "raw": source_statement("The deployment channel is eng-releases."),
        },
        {
            "id": "timezone", "source_session_id": "004978",
            "content": "The timezone is UTC.",
            "raw": source_statement("The timezone is UTC."),
        },
    ]
    removal = {
        "expected": "Deployment updates go to eng-releases.",
        "source_refs": ["session:004978"],
    }
    selected, failure = _atomic_removal_records(atomic_records, removal, [removal])
    assert failure is None
    assert [row["id"] for row in selected] == ["blue"]
    selected, failure = _atomic_removal_records(
        provenance_records, provenance_requirement, [provenance_requirement]
    )
    assert selected == []
    assert failure == "non_atomic_removal_target"
    spanning = {
        "expected": "Honeycomb was chosen because tracing follows requests end to end.",
        "source_refs": ["session:004978"],
    }
    spanning_records = [
        {
            "id": "choice", "source_session_id": "004978",
            "content": "Honeycomb was chosen.",
            "raw": source_statement("Honeycomb was chosen."),
        },
        {
            "id": "reason", "source_session_id": "004978",
            "content": "Tracing follows requests end to end.",
            "raw": source_statement("Tracing follows requests end to end."),
        },
    ]
    selected, failure = _atomic_removal_records(
        spanning_records, spanning, [spanning]
    )
    assert failure is None
    assert {row["id"] for row in selected} == {"choice", "reason"}
    requirement = {"expected": "Deployment updates must go to eng-releases."}
    assert _gate_blocks_removed_requirement({
        "outcome": "blocked_missing_requirement",
        "missing_obligations": [{
            "entity": "deployment updates",
            "relation_or_action": "required channel for eng-releases deployment updates",
        }],
    }, requirement)
    assert not _gate_blocks_removed_requirement({
        "outcome": "blocked_missing_requirement",
        "missing_obligations": [{
            "entity": "timezone",
            "relation_or_action": "which timezone is configured",
        }],
    }, requirement)


def test_performance_qualification_freezes_50k_and_100k_gates() -> None:
    from benchmarks.retrieval_quality.qualify_context_performance import _parts

    source = Path(
        "benchmarks/retrieval_quality/qualify_context_performance.py"
    ).read_text(encoding="utf-8")
    assert "MILESTONES = (50_000, 100_000)" in source
    assert '"warm_p50_ms"] <= 500' in source
    assert '"warm_p95_ms"] <= 2_000' in source
    assert '"warm_p95_ms"] <= 3_000' in source
    assert '"cold_p95_ms"' in source
    assert '"warm_latencies_ms"' in source
    assert 'for value in row["latencies_ms"]' not in source
    assert '512 * 1024 * 1024' in source
    assert "performance evidence must be outside the repository" in source
    assert len(_parts(0, 5_000)) == 1_250
    assert len(_parts(0, 5_001)) == 1_251
    assert _parts(0, 5_001)[-1].kind == "file"


def test_authorized_recency_path_uses_scope_index(tmp_path: Path) -> None:
    memory = Memory(tmp_path / "plan.db", auto_vectors=False)
    try:
        plan = memory.store._conn.execute(  # qualification of shipped SQL indexes
            "EXPLAIN QUERY PLAN SELECT id FROM records "
            "WHERE subject_id=? AND status='active' "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            ("subject", 20),
        ).fetchall()
    finally:
        memory.close()
    detail = " ".join(str(row[3]) for row in plan)
    assert "idx_records_subject_recent" in detail
    assert "SCAN records" not in detail
