from __future__ import annotations

from pathlib import Path
import json
import re

from atmem import Memory
from atmem.mcp import MCPServer


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = (
    ROOT / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    ROOT / "integrations" / "openclaw" / "README.md",
)


def test_documentation_structure_and_local_links() -> None:
    markdown_link = re.compile(r"\[[^]]*\]\(([^)]+)\)")
    for path in MARKDOWN_FILES:
        text = path.read_text()
        assert text.count("```") % 2 == 0, f"unbalanced code fence in {path}"
        for target in markdown_link.findall(text):
            target = target.split("#", 1)[0]
            if not target or target.startswith(("https://", "http://")):
                continue
            assert not target.startswith("/"), f"absolute link in {path}: {target}"
            assert (path.parent / target).exists(), f"broken link in {path}: {target}"


def test_documented_mcp_catalog_matches_runtime() -> None:
    runtime_names = {
        tool["name"] for tool in MCPServer(Memory(":memory:"))._tool_definitions()
    }
    guide = (ROOT / "docs" / "integration-guide.md").read_text()
    documented_names = set(
        re.findall(r"^\| `(memory_[a-z_]+)` \|", guide, flags=re.MULTILINE)
    )
    assert documented_names == runtime_names
    readme = (ROOT / "README.md").read_text()
    for name in runtime_names:
        assert f"`{name}`" in readme


def test_integration_json_files_parse() -> None:
    integration = ROOT / "integrations" / "openclaw"
    for name in ("package.json", "package-lock.json", "openclaw.plugin.json", "tsconfig.json"):
        json.loads((integration / name).read_text())
    capabilities = json.loads((ROOT / "docs" / "capabilities.json").read_text())
    assert capabilities["product"] == "memory_control_plane"
    assert capabilities["engine"] == "model_agnostic"
    assert capabilities["reversible_switch_hosts"] == ["openclaw"]


def test_readme_puts_supported_quick_starts_front_and_center() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quick_start = readme.index("## Start here")
    details = readme.index("## Installation details")
    opening = readme[quick_start:details]

    assert "AtBot is installed automatically" in readme[:quick_start]
    assert "atmem atbot setup" in opening
    assert "atmem openclaw install" in opening
    assert "atmem openclaw upgrade" in opening
    assert "atmem[pydantic-ai]==2.2.3" in opening
    assert "PydanticAIAtMemAdapter" in opening
    assert "atmem[langgraph]==2.2.3" in opening
    assert "create_langgraph_middleware" in opening
    assert "atmem control activate" in opening


def test_readme_version_matches_package_metadata() -> None:
    metadata = (ROOT / "pyproject.toml").read_text()
    version = re.search(r'^version = "([^"]+)"$', metadata, flags=re.MULTILINE).group(1)
    readme = (ROOT / "README.md").read_text()
    assert f"Version {version}" in readme
    assert f"version-{version}" in readme


def test_development_docs_match_companion_packaging() -> None:
    root_metadata = (ROOT / "pyproject.toml").read_text()
    companion_metadata = (ROOT / "packages" / "atbot" / "pyproject.toml").read_text()
    companion_version = re.search(
        r'^version = "([^"]+)"$', companion_metadata, flags=re.MULTILINE
    ).group(1)
    capabilities = json.loads((ROOT / "docs" / "capabilities.json").read_text())
    companion = capabilities["intelligence_companion"]

    assert 'name = "atmem-atbot"' in companion_metadata
    assert f'"atmem-atbot=={companion_version}"' in root_metadata
    assert '"pydantic-ai-slim[openai]>=1,<2"' in companion_metadata
    assert '"openai>=2.29,<3"' in companion_metadata
    assert '"jiter>=0.10,<0.14"' in companion_metadata
    assert companion["distribution"] == "atmem-atbot"
    assert companion["pinned_version"] == companion_version
    assert companion["required_distribution_dependency"] is True
    assert companion["separate_process"] is True
    assert companion["canonical_storage"] is False
    assert capabilities["release_status"] == "released"

    active_guides = (
        ROOT / "README.md",
        ROOT / "docs" / "integration-guide.md",
        ROOT / "research" / "research.md",
    )
    for path in active_guides:
        assert "atmem[atbot]" not in path.read_text(), path


def test_atbot_trusted_publishing_identity_is_exact() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-atbot.yml").read_text()
    release_guide = (ROOT / "docs" / "atbot-release.md").read_text()

    assert 'tags:\n      - "atbot-v*"' in workflow
    assert "name: pypi-atbot" in workflow
    assert "url: https://pypi.org/p/atmem-atbot" in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    for exact_value in ("aetna000", "atmem", "publish-atbot.yml", "pypi-atbot"):
        assert exact_value in release_guide


def test_semantic_docs_match_automatic_governed_vectors() -> None:
    semantic = (ROOT / "docs" / "semantic-search.md").read_text().casefold()
    capabilities = json.loads((ROOT / "docs" / "capabilities.json").read_text())

    assert "automatically" in semantic
    assert "hashing" in semantic
    assert "canonical" in semantic
    assert "does not automatically change agent recall" not in semantic
    assert capabilities["semantic_search"] == "automatic_derived_local_vector_sidecar"
    assert (
        capabilities["semantic_governance"]
        == "candidate_nomination_with_canonical_revalidation"
    )


def test_public_product_namespace_is_atmem_only() -> None:
    legacy = "aetna" + "mem"
    roots = (
        ROOT / "atmem",
        ROOT / "docs",
        ROOT / "integrations" / "openclaw",
        ROOT / "tools",
        ROOT / "README.md",
        ROOT / "pyproject.toml",
    )
    for root in roots:
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            if "node_modules" in path.parts:
                continue
            if not path.is_file() or path.suffix.lower() not in {
                ".py",
                ".md",
                ".json",
                ".ts",
                ".mjs",
                ".toml",
                ".yml",
                ".yaml",
                ".html",
                ".css",
                ".js",
            }:
                continue
            assert legacy not in path.name.casefold(), path
            assert legacy not in path.read_text(errors="ignore").casefold(), path
