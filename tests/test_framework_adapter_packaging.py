from pathlib import Path
import tomllib

def test_framework_extras_are_optional_and_base_has_no_framework_sdk():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    base = " ".join(data["project"]["dependencies"])
    assert not any(name in base for name in ("crewai", "smolagents", "google-adk", "openai-agents", "agent-framework"))
    extras = data["project"]["optional-dependencies"]
    for name in ("openai-agents", "microsoft-agent", "google-adk", "smolagents", "crewai"):
        assert extras[name]
