from research.laya_memory_evidence.publish_artifact import _contains_secret


def test_secret_scanner_reads_beyond_twenty_megabytes(tmp_path):
    path = tmp_path / "large.jsonl"
    with path.open("wb") as stream:
        stream.seek(21 * 1024 * 1024)
        stream.write(b"token = 'hf_" + b"A" * 30 + b"'")
    assert _contains_secret(path)


def test_secret_scanner_accepts_environment_variable_reference(tmp_path):
    path = tmp_path / "safe.py"
    path.write_text('OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")')
    assert not _contains_secret(path)
