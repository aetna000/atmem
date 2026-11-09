import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("feedback_doc_check", ROOT/"scripts/check_feedback_docs.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_documented_tools_match_executable_inventory_and_state_limits():
    text = (ROOT/"docs/governed-rag-and-mcp.md").read_text()
    assert checker.check(text) == []
    assert checker.check(text.replace("| `rag_search` |", "| `imaginary_activate` |"))
    assert checker.check(text.replace("2025-11-25", "2099-01-01"))
    assert checker.check(text.replace("outside this server", "everywhere"))
