#!/usr/bin/env python3
"""Validate exact Python/bridge release alignment and select publication channels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


def release_metadata(version: str, bridge_version: str, tag: str | None = None) -> dict[str, str]:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?", version)
    if match is None:
        raise ValueError(f"unsupported release version: {version}")
    core, phase, number = match.groups()
    channel = {"a": "alpha", "b": "beta", "rc": "rc"}.get(phase, "latest")
    expected_bridge = f"{core}-{channel}.{number}" if phase else core
    if bridge_version != expected_bridge:
        raise ValueError(f"bridge {bridge_version} must equal {expected_bridge} for AtMem {version}")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"tag {tag} must equal v{version}")
    return {
        "version": version,
        "bridge_version": bridge_version,
        "npm_tag": channel,
        "prerelease": "true" if phase else "false",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag")
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib
        project = tomllib.loads((args.root / "pyproject.toml").read_text())["project"]
        bridge = json.loads((args.root / "integrations/openclaw/package.json").read_text())
        result = release_metadata(project["version"], bridge["version"], args.tag)
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.github_output:
        for key, value in result.items():
            print(f"{key}={value}")
    else:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
