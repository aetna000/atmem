import pytest

from atmem.benchmark.memorybench import BenchmarkStore


def session(name="s1", content="User's preferred airport is Sydney Airport."):
    return {"sessionId": name, "messages": [{"role": "user", "content": content}], "metadata": {"date": "2026-01-01"}}


def test_real_admission_index_delivery_and_restart(tmp_path):
    store = BenchmarkStore(tmp_path, "first", embedding="hashing")
    first = store.ingest([session()])
    assert first["documentIds"]
    assert store.ingest([session()])["documentIds"] == first["documentIds"]
    store.index()
    restored = BenchmarkStore(tmp_path, "first", embedding="hashing")
    rows = restored.search("preferred airport")
    assert "Sydney Airport" in rows[0]["content"]
    assert rows[0]["sessionIds"] == ["s1"]
    assert rows[0]["recordIds"] == first["documentIds"]
    assert len(rows[0]["content"]) <= 16000


def test_containers_are_isolated_and_clear_is_scoped(tmp_path):
    a = BenchmarkStore(tmp_path, "../first", embedding="hashing")
    b = BenchmarkStore(tmp_path, "second", embedding="hashing")
    a.ingest([session()]); a.index()
    b.ingest([session("s2", "User's preferred airport is Melbourne Airport.")]); b.index()
    assert "Sydney" not in b.search("airport")[0]["content"]
    a.clear()
    assert b.database.is_file()
    assert a.directory.parent == tmp_path


def test_reference_answers_and_metadata_labels_are_not_ingested(tmp_path):
    store = BenchmarkStore(tmp_path, "labels", embedding="hashing")
    row = session()
    row["groundTruth"] = "SECRET_ANSWER"
    row["metadata"]["answer"] = "SECRET_ANSWER"
    store.ingest([row]); store.index()
    assert "SECRET_ANSWER" not in store.search("airport")[0]["content"]


def test_openai_profile_requires_key_without_silent_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = BenchmarkStore(tmp_path, "test")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        store._embedder()


def test_every_chunk_has_session_date(tmp_path):
    store = BenchmarkStore(tmp_path, "long", embedding="hashing")
    ids = store.ingest([session(content="Airport preference information. " * 160)])["documentIds"]
    assert len(ids) > 1
    memory = store._memory()
    try:
        for rid in ids:
            record = memory.store.get_record(store.scope.subject_id, rid)
            assert "Date: 2026-01-01" in str(record)
    finally:
        memory.close()


def test_symlink_container_cannot_be_opened_or_deleted(tmp_path):
    target = tmp_path / "protected"
    target.mkdir()
    store = BenchmarkStore(tmp_path, "linked", embedding="hashing")
    store.directory.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="invalid benchmark container"):
        store.ingest([session()])
    with pytest.raises(ValueError, match="invalid benchmark container"):
        store.clear()
    assert target.is_dir()
