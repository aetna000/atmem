"""Validate the public website inventory; no website credentials required."""
from pathlib import Path, PurePosixPath
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def validate():
    manifest = json.loads((ROOT / 'docs/website/manifest.json').read_text())
    version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(), re.M)[1]
    assert manifest['version'] == version, 'website docs must match release version'
    assert manifest['schema'] == 1
    seen = set()
    sources = set()
    for page in manifest['pages']:
        slug = page['slug']
        assert re.fullmatch(r'[a-z0-9.-]+(?:/[a-z0-9.-]+)*|', slug)
        assert '..' not in slug and slug not in seen, slug
        seen.add(slug)
        source = PurePosixPath(page['source'])
        assert source.parts[0] == 'docs' and '..' not in source.parts
        assert source.suffix == '.md' and (ROOT / source).is_file()
        assert not (ROOT / source).is_symlink()
        assert (ROOT / source).stat().st_size < 512 * 1024
        sources.add(str(source))
    assert {'', 'getting-started', 'integrations', 'reference', 'examples', 'releases'} <= seen
    assert f'docs/releases/v{version}.md' in sources
    for source in (ROOT / 'docs/website').glob('*.md'):
        assert str(source.relative_to(ROOT)) in sources, f'orphan guide: {source}'
    print(f'Website docs: {len(seen)} pages; version {version}; inventory valid')


if __name__ == '__main__':
    validate()
