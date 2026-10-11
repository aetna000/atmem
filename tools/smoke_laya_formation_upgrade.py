"""Two-phase installed-wheel compatibility smoke for the 2.3.8 upgrade gate."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def _distribution() -> dict:
    dist = metadata.distribution("atmem")
    dependencies = list(dist.requires or ())
    return {
        "version": dist.version,
        "dependency_names": sorted({re.match(r"^[A-Za-z0-9_.-]+", row).group(0).lower() for row in dependencies}),
        "provides_extras": sorted(dist.metadata.get_all("Provides-Extra") or ()),
    }


def _surface(db_path: Path) -> dict:
    from atbot.companion import CompanionRuntime
    from atbot.config import AtBotConfig
    from atmem import Memory
    from atmem.mcp import MCPServer
    import atmem.openclaw_install as openclaw

    memory = Memory(db_path)
    try:
        tools = sorted(row["name"] for row in MCPServer(memory)._tool_definitions())
    finally:
        memory.close()
    help_text = subprocess.run(
        [sys.executable, "-m", "atmem.cli", "--help"], text=True,
        capture_output=True, check=True, timeout=20,
    ).stdout
    commands = sorted(
        name for name in (
            "status", "install", "home", "openclaw", "atbot", "delegated", "provider",
            "benchmark", "dashboard", "control", "remember", "recall", "mcp",
            "formation",
        ) if name in help_text
    )
    capabilities = CompanionRuntime(AtBotConfig(providers=[])).capabilities()
    return {
        "mcp_tools": tools,
        "cli_commands": commands,
        "atbot_protocol": capabilities["protocol_version"],
        "atbot_features": sorted(capabilities["features"]),
        "openclaw_symbols": sorted(name for name in dir(openclaw) if not name.startswith("_")),
        "openclaw_version": openclaw.OPENCLAW_PLUGIN_VERSION,
        "atbot_version": metadata.version("atmem-atbot"),
        "atflows_version": metadata.version("atflows"),
    }


def baseline(state_dir: Path) -> dict:
    from atmem import Memory

    db_path = state_dir / "persisted.db"
    memory = Memory(db_path)
    try:
        stored = memory.remember("upgrade-user", "My preferred color is blue.")
        record_id = stored["records"][0]["id"]
    finally:
        memory.close()
    value = {
        "format": "atmem-laya-upgrade-baseline-v1",
        "distribution": _distribution(), "surface": _surface(db_path),
        "record_id": record_id, "db_path": str(db_path),
    }
    (state_dir / "baseline.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return value


def candidate(state_dir: Path) -> dict:
    from atmem import Memory
    from atmem.laya_formation.artifacts import ArtifactBundle
    from atmem.laya_formation.contracts import CalibrationBinding
    from atmem.laya_formation.setup import LayaProfileManager

    old = json.loads((state_dir / "baseline.json").read_text())
    new_dist = _distribution()
    new_surface = _surface(Path(old["db_path"]))
    assert old["distribution"]["version"] == "2.3.8"
    assert new_dist["version"] == "2.3.9b1"
    assert set(old["distribution"]["dependency_names"]) <= set(new_dist["dependency_names"])
    assert "laya-formation" in new_dist["provides_extras"]
    assert set(old["surface"]["mcp_tools"]) <= set(new_surface["mcp_tools"])
    assert set(old["surface"]["cli_commands"]) <= set(new_surface["cli_commands"])
    assert set(old["surface"]["atbot_features"]) <= set(new_surface["atbot_features"])
    assert set(old["surface"]["openclaw_symbols"]) <= set(new_surface["openclaw_symbols"])
    assert old["surface"]["atbot_protocol"] == new_surface["atbot_protocol"] == "1"
    assert old["surface"]["atflows_version"] == new_surface["atflows_version"]

    memory = Memory(old["db_path"])
    try:
        rows = memory.recall("upgrade-user", "preferred color", limit=5)
        assert any(row["id"] == old["record_id"] for row in rows)
    finally:
        memory.close()

    hf_home = Path(os.environ["HF_HOME"])
    profile_root = state_dir / "profile"
    inactive = LayaProfileManager(profile_root).status()
    assert inactive["configured"] is False and inactive["active"] is False
    assert not hf_home.exists() or not any(hf_home.rglob("*"))

    calibration = CalibrationBinding(
        "f" * 64, "7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e",
        "b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        "per-question-temperature-and-abstention-v1", (1.0, 1.0, 1.0),
        {"choice:3-5": 1.0}, {"choice:3-5": 1.0},
    )
    model_dir = state_dir / "verified-model"
    model_dir.mkdir(exist_ok=True)
    artifact = ArtifactBundle(
        model_dir, "atmem/atmem-laya-formation-model-v1", "1" * 40,
        calibration.model_sha256, calibration.questions_digest,
        calibration.calibration_digest, "e" * 64, calibration, {"operation": {}},
    )
    class Resolver:
        def resolve(self, **kwargs): return artifact
        def verify(self, root): return artifact
    class Engine:
        device = "cpu"
        def __init__(self, value, *, device): self.device = device
        def close(self): pass
    manager = LayaProfileManager(
        profile_root, resolver=Resolver(), engine_factory=Engine,
        dependency_probe=lambda: {"available": True, "versions": {"laya": "0.4.2"}},
    )
    manager.setup(local_dir=model_dir, device="cpu")
    before = manager.config_path.read_bytes()
    manager.activate(confirmed=True)
    manager.rollback(confirmed=True)
    exact_rollback = manager.config_path.read_bytes() == before
    assert exact_rollback

    result = {
        "format": "atmem-laya-wheel-compatibility-v1", "result": "pass",
        "baseline": old["distribution"], "candidate": new_dist,
        "persisted_record_recalled": True, "default_profile_unchanged": True,
        "forced_model_download": False, "exact_profile_rollback": exact_rollback,
        "contract_checks": {
            "cli_additive": True, "mcp_additive": True, "atbot_protocol_unchanged": True,
            "atbot_features_additive": True, "openclaw_api_additive": True,
            "atflows_version_unchanged": True,
        },
        "versions": {
            "atbot_before": old["surface"]["atbot_version"],
            "atbot_after": new_surface["atbot_version"],
            "openclaw_before": old["surface"]["openclaw_version"],
            "openclaw_after": new_surface["openclaw_version"],
            "atflows": new_surface["atflows_version"],
        },
    }
    (state_dir / "candidate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("baseline", "candidate"))
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    value = baseline(args.state_dir) if args.phase == "baseline" else candidate(args.state_dir)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
