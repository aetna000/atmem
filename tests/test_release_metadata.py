from pathlib import Path
import json
import re
import runpy
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest


release_metadata = runpy.run_path(str(Path(__file__).parents[1] / "tools/release_metadata.py"))["release_metadata"]


@pytest.mark.parametrize("version,bridge,channel,prerelease", [
    ("2.2.6", "2.2.6", "latest", "false"),
    ("2.3.0a1", "2.3.0-alpha.1", "alpha", "true"),
    ("2.3.0b2", "2.3.0-beta.2", "beta", "true"),
    ("2.3.0rc1", "2.3.0-rc.1", "rc", "true"),
])
def test_release_channel_matches_version(version, bridge, channel, prerelease):
    result = release_metadata(version, bridge, f"v{version}")
    assert result["npm_tag"] == channel
    assert result["prerelease"] == prerelease


@pytest.mark.parametrize("version,bridge,tag", [
    ("2.2.6", "2.2.6-beta.11", "v2.2.6"),
    ("2.3.0b2", "2.3.0-beta.1", "v2.3.0b2"),
    ("2.2.6", "2.2.6", "v2.2.7"),
    ("2.2.6+local", "2.2.6", "v2.2.6+local"),
])
def test_mismatched_or_unsupported_release_is_rejected(version, bridge, tag):
    with pytest.raises(ValueError):
        release_metadata(version, bridge, tag)


def test_repository_release_constants_and_notes_are_aligned():
    root = Path(__file__).parents[1]
    project = (root / 'pyproject.toml').read_text()
    version = re.search(r'^version = "([^"]+)"', project, re.M).group(1)
    bridge = json.loads((root / 'integrations/openclaw/package.json').read_text())['version']
    release_metadata(version, bridge, f'v{version}')
    lock = json.loads((root / 'integrations/openclaw/package-lock.json').read_text())
    assert lock['version'] == lock['packages']['']['version'] == bridge
    assert json.loads((root / 'integrations/openclaw/openclaw.plugin.json').read_text())['version'] == bridge
    for path, constant in (
        ('atmem/openclaw_install.py', 'OPENCLAW_PLUGIN_VERSION'),
        ('atmem/mcp/server.py', 'SERVER_VERSION'),
        ('tools/smoke_installed_package.py', 'EXPECTED_ATMEM_VERSION'),
    ):
        value = re.search(rf'^\s*{constant}(?::[^=\n]+)? = "([^"]+)"', (root / path).read_text(), re.M)
        assert value and value.group(1) == (bridge if constant == 'OPENCLAW_PLUGIN_VERSION' else version)
    companion = re.search(r'^version = "([^"]+)"', (root / 'packages/atbot/pyproject.toml').read_text(), re.M).group(1)
    assert f'atmem-atbot=={companion}' in project
    assert f'PINNED_ATBOT_VERSION = "{companion}"' in (root / 'atmem/control/atbot_service.py').read_text()
    metadata = tomllib.loads(project)['project']
    assert 'atflows==0.1.3' in metadata['dependencies']
    atflows_version = next(
        dependency.removeprefix('atflows==')
        for dependency in metadata['dependencies']
        if dependency.startswith('atflows==')
    )
    for workflow in ('ci.yml', 'publish.yml'):
        workflow_text = (root / '.github/workflows' / workflow).read_text()
        assert f"assert version('atflows') == '{atflows_version}'" in workflow_text
    handoff = (root / 'tools/smoke_atflows_handoff.py').read_text()
    assert f'version("atflows") != "{atflows_version}"' in handoff
    assert f'atflows_version != "atflows {atflows_version}"' in handoff
    assert metadata['optional-dependencies']['atflows'] == []  # legacy extra
    note = root / f'docs/releases/v{version}.md'
    assert note.is_file()
    assert f'atmem=={version}' in note.read_text()
    assert f'openclaw-memory-atmem@{bridge}' in note.read_text()
