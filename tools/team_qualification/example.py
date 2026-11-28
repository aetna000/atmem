"""Build the public, synthetic dashboard example from the recorded qualification."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "specs/058-portable-agent-runs"


def build():
    hosts = json.loads((SPEC / "host-qualification.json").read_text())
    rows = json.loads((SPEC / "measured.json").read_text())["rows"]
    policies = []
    for policy in ("single", "adaptive", "fixed"):
        selected = [r for r in rows if r["run"]["policy"] == policy]
        assert len(selected) == 10
        policies.append(
            {
                "policy": policy,
                "correct": sum(r["grade"]["correct"] for r in selected),
                "stale": sum(r["grade"]["stale"] for r in selected),
                "model_calls": sum(r["run"]["model_calls"] for r in selected),
                "input_tokens": sum(r["run"]["input_tokens"] for r in selected),
            }
        )
    return {
        "original": hosts["original"]["run"],
        "corrected": hosts["corrected"]["run"],
        "policies": policies,
        "excerpts": {
            hosts[key]["source_excerpt"]["excerpt_sha256"]: hosts[key]["source_excerpt"]
            for key in ("original", "corrected")
            if "source_excerpt" in hosts[key]
        },
    }


if __name__ == "__main__":
    data = build()
    (ROOT / "atmem/control/assets/team-project-example.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
