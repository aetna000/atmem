from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from research.laya_formation.training.contracts import canonical_digest, secret_findings
from research.laya_formation.training.smoke import sha256_file


def export_model(
    *, run_root: Path, calibration_rows: Path | None, output: Path,
    research_only: bool = False,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite export: {output}")
    manifest = json.loads((run_root / "training-manifest.json").read_text(encoding="utf-8"))
    calibration_path = run_root / "calibration-bundle.json"
    calibration = (
        json.loads(calibration_path.read_text(encoding="utf-8"))
        if calibration_path.is_file() else None
    )
    if calibration_rows is not None and sha256_file(calibration_rows) != manifest["split_digests"]["calibration"]:
        raise ValueError("calibration rows do not match the selected training run")
    if calibration is None and not (
        research_only and manifest.get("hyperparameters", {}).get("research_only") is True
    ):
        raise ValueError("a production model export requires a calibration bundle")
    if calibration is None and calibration_rows is not None:
        raise ValueError("calibration rows cannot substitute for a missing calibration bundle")
    # The definitions are frozen over train+validation+calibration by the
    # training run.  Calibration alone can legitimately omit a rare dynamic
    # target shape, so reconstructing the union here would be incomplete.
    definitions = json.loads(
        (run_root / "question-definitions.json").read_text(encoding="utf-8")
    )
    if canonical_digest(definitions) != manifest["questions_digest"]:
        raise ValueError("exported question definitions do not match training")
    output.mkdir(parents=True)
    for path in sorted((run_root / "model").rglob("*")):
        relative = path.relative_to(run_root / "model")
        target = output / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    questions = {
        "format": "portable-laya-memory-understanding-questions-v2",
        "digest": manifest["questions_digest"],
        "questions": definitions,
    }
    (output / "questions.json").write_text(json.dumps(questions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if calibration is not None:
        shutil.copy2(calibration_path, output / "calibration.json")
    shutil.copy2(run_root / "training-manifest.json", output / "training-manifest.json")
    for name in (
        "base-validation-metrics.json", "validation-metrics.json",
        "calibration-metrics.json", "calibration-power.json",
    ):
        source = run_root / name
        if source.is_file():
            shutil.copy2(source, output / name)
    inventory = [
        {"path": path.relative_to(output).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output.rglob("*")) if path.is_file()
    ]
    receipt = {
        "format": "atmem-laya-formation-export-v1",
        "run_id": manifest["run_id"],
        "objective": manifest["objective"],
        "model_sha256": (
            calibration["model_digest"] if calibration is not None
            else sha256_file(output / "model.safetensors")
        ),
        "questions_digest": manifest["questions_digest"],
        "calibration_digest": calibration["digest"] if calibration is not None else None,
        "publication_status": "research-only" if calibration is None else "calibrated-candidate",
        "base_model": manifest["base_model"],
        "laya": manifest["laya"],
        "dataset": manifest["dataset"],
        "inventory": inventory,
    }
    receipt["digest"] = canonical_digest(receipt)
    if secret_findings(receipt):
        raise RuntimeError("secret-like material detected in model export")
    (output / "artifact-manifest.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the selected Spec 041 Laya model")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--calibration-rows", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research-only", action="store_true")
    args = parser.parse_args(argv)
    result = export_model(
        run_root=args.run_root.resolve(),
        calibration_rows=(args.calibration_rows.resolve() if args.calibration_rows else None),
        output=args.output.resolve(), research_only=args.research_only,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
