from __future__ import annotations

from pathlib import Path


def test_provider_extras_are_independent_and_base_imports_are_sdk_neutral() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'mem0 = [' in pyproject
    assert 'langgraph-provider = [' in pyproject
    assert 'pydantic-provider = [' in pyproject
    for path in (Path("atmem/provider_adapters/__init__.py"), Path("atmem/provider_adapters/runtime.py")):
        source = path.read_text(encoding="utf-8")
        assert "from mem0 import" not in source
        assert "from langgraph" not in source
        assert "from pydantic_ai" not in source
