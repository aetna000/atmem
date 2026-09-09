"""The supported-OpenClaw list must mean the same thing everywhere.

AtMem describes "which OpenClaw versions do we support" in two places: the
compatibility matrix that gates native takeover, and the recorded hook-context
fixtures that pin each version's declared plugin surface. Nothing checked they
agreed.

That is the same shape of bug that shipped in 2.2.6b6, where three version
declarations drifted apart and the failure surfaced on a user's machine instead
of in CI. One list is a claim; two unchecked lists are a coin flip.
"""

from __future__ import annotations

import json
from pathlib import Path

from atmem.control.compat import (
    TESTED_OPENCLAW_VERSIONS,
    evaluate_host_version,
    normalize_openclaw_version,
)


FIXTURES = (
    Path(__file__).parents[1]
    / "integrations" / "openclaw" / "test" / "fixtures" / "hook-context"
)


def _recorded_versions() -> set[str]:
    return {
        json.loads(path.read_text(encoding="utf-8"))["version"]
        for path in FIXTURES.glob("*.json")
    }


def test_every_tested_version_has_a_recorded_hook_context_fixture() -> None:
    """Claiming a version is tested requires having recorded what it declares.

    Without the fixture there is nothing pinning that version's hook-context
    surface, so "tested" would rest on a one-time manual check that no later
    change re-runs.
    """
    missing = sorted(set(TESTED_OPENCLAW_VERSIONS) - _recorded_versions())
    assert not missing, (
        f"{missing} are in the compatibility matrix with no recorded fixture in "
        f"{FIXTURES.relative_to(Path(__file__).parents[1])}. Record one with "
        "`node test/lib/record-hook-context.mjs --label <label>` against that "
        "exact version, or drop the version from the matrix."
    )


def test_every_recorded_fixture_is_a_version_we_claim_to_support() -> None:
    """The reverse direction: a fixture nobody supports is a stale file.

    Left alone it looks like coverage while gating nothing.
    """
    extra = sorted(_recorded_versions() - set(TESTED_OPENCLAW_VERSIONS))
    assert not extra, (
        f"{extra} have recorded fixtures but are not in TESTED_OPENCLAW_VERSIONS. "
        "Either support them or remove the fixture; a fixture that gates nothing "
        "reads as coverage it does not provide."
    )


def test_the_matrix_covers_the_declared_peer_range_floor() -> None:
    """The lowest tested version is the bridge's declared minimum.

    `peerDependencies` promises `>=2026.7.1-2` works. If the matrix floor rose
    above it, that promise would be untested at its own boundary.
    """
    package = json.loads(
        (
            Path(__file__).parents[1]
            / "integrations" / "openclaw" / "package.json"
        ).read_text(encoding="utf-8")
    )
    declared_floor = package["peerDependencies"]["openclaw"].lstrip(">=").strip()
    assert normalize_openclaw_version(declared_floor) in TESTED_OPENCLAW_VERSIONS


def test_an_unlisted_host_is_refused_rather_than_assumed() -> None:
    """Fail closed. A newer host is not silently treated as compatible."""
    assert evaluate_host_version("2026.9.2") == "tested"
    assert evaluate_host_version("2027.1.1") == "untested"
    # A patch inside a tested minor is distinguishable from a wholly new line,
    # so the two can be handled differently without conflating them.
    assert evaluate_host_version("2026.9.7") == "untested_patch"
