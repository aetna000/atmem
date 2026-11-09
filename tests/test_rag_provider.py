"""Reference retrieval uses a real encrypted store and an in-RAM FTS index."""

from dataclasses import replace
import sqlite3
import time

import pytest

from atmem.feedback.store import FeedbackError
from atmem.knowledge.rag.contracts import RagQuery
from rag_fixtures import hit, setup_rag


def test_real_fts_retrieves_exact_cited_effective_document(tmp_path):
    env = setup_rag(tmp_path)
    result = env.provider.search(env.source, RagQuery("law", "filing deadline", jurisdiction="XX", as_of="2025-01-01"), deadline=time.monotonic()+5)
    assert [h.chunk_id for h in result] == ["current"]
    assert result[0].text == env.hits[0].text
    assert result[0].citation == "urn:fixture:filing-act"
    assert env.provider.inspect(env.source, "fictional-act", "current", deadline=time.monotonic()+5) == result[0]
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"fictional filing deadline" not in path.read_bytes()
    with sqlite3.connect(env.evidence.vault_path) as db:
        assert not any("fts" in r[0] or "passages" in r[0] for r in db.execute("SELECT name FROM sqlite_master"))


@pytest.mark.parametrize("query", ['" OR 1=1 --', "deadline AND NOT missing", "deadline* NEAR(secret)", "\"; DROP TABLE passages; --"])
def test_query_text_is_literal_not_fts_or_sql_code(tmp_path, query):
    env = setup_rag(tmp_path)
    result = env.provider.search(env.source, RagQuery("law", query), deadline=time.monotonic()+5)
    assert all(h.scope == env.scope and h.source_id == "law" for h in result)
    # A subsequent normal query and the encrypted persistent store remain usable.
    assert env.provider.search(env.source, RagQuery("law", "deadline"), deadline=time.monotonic()+5)


def test_owner_only_immutable_ingestion_is_atomic_and_idempotent(tmp_path):
    env = setup_rag(tmp_path)
    assert env.provider.put_documents(env.owner["token"], env.source, env.hits) == {"added": 0, "unchanged": 4, "revision": "collection-v1"}
    with pytest.raises(FeedbackError, match="denied"):
        env.provider.put_documents(env.user["token"], env.source, (hit(env.source, "new"),))
    with pytest.raises(FeedbackError, match="source_revision_conflict"):
        env.provider.put_documents(env.owner["token"], env.source,
                                   (hit(env.source, "new"), hit(env.source, text="Changed edition under the same ID.")))
    with pytest.raises(FeedbackError, match="denied"):
        env.provider.inspect(env.source, "fictional-act", "new", deadline=time.monotonic()+5)
    wrong = replace(env.source, scope=replace(env.scope, subject_id="bob"))
    with pytest.raises(FeedbackError, match="invalid_document_scope"):
        env.provider.put_documents(env.owner["token"], env.source, (hit(wrong),))


def test_source_change_and_deadline_refuse_old_provider_requests(tmp_path):
    env = setup_rag(tmp_path)
    with pytest.raises(FeedbackError, match="provider_timeout"):
        env.provider.inspect(env.source, "fictional-act", "current", deadline=time.monotonic()-1)
    env.rag.revoke(env.owner["token"], env.scope, "law")
    with pytest.raises(FeedbackError, match="source_changed"):
        env.provider.search(env.source, RagQuery("law", "deadline"), deadline=time.monotonic()+5)
