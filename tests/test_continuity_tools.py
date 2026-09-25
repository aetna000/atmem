import pytest

from atmem.continuity.tools import DirectoryPublisher


def test_published_file_is_real_receipt_and_conflicts_not_overwritten(tmp_path):
    publisher = DirectoryPublisher(tmp_path)
    arguments = {"text": "A real document\n", "destination": str(tmp_path.resolve())}
    assert publisher.query(arguments, "op_1", "key", 30)["outcome"] == "unknown"
    receipt = publisher.execute(arguments, "op_1", "key", 30)
    assert receipt["outcome"] == "confirmed_succeeded"
    assert (tmp_path / "op_1.md").read_text() == "A real document\n"
    assert publisher.query(arguments, "op_1", "key", 30) == receipt
    with pytest.raises(FileExistsError):
        publisher.execute(arguments, "op_1", "key", 30)
    assert publisher.query({**arguments, "text": "different"}, "op_1", "key", 30)["outcome"] == "unknown"
    assert len(list(tmp_path.iterdir())) == 1
    with pytest.raises(ValueError, match="destination"):
        publisher.execute({**arguments, "destination": "/somewhere-else"}, "op_2", "key", 30)
def test_json_response_adapter_preserves_actual_result_and_never_infers_errors():
    import io
    import json
    import pytest
    from atmem.continuity.tools import JsonResponseTool
    class Endpoint:
        def __init__(self, reply):
            self.reply = reply
        def open(self, request, timeout):
            assert timeout == 30
            return io.BytesIO(json.dumps(self.reply).encode())
    adapter = JsonResponseTool("http://127.0.0.1:9999/tool", "test")
    original = {"id": "call1", "error": False, "content": "original native response"}
    adapter.opener = Endpoint(original)
    receipt = adapter.execute({"id": "call1"}, "op1", None, 30)
    assert receipt["result"] == original
    assert receipt["effect_id"] == "call1"
    assert adapter.tool().query is None
    adapter.opener = Endpoint({**original, "error": True})
    assert adapter.execute({"id": "call1"}, "op1", None, 30)["outcome"] == "unknown"
    adapter.opener = Endpoint({**original, "id": "other"})
    with pytest.raises(ValueError, match="identity"):
        adapter.execute({"id": "call1"}, "op1", None, 30)
