from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from research.laya_formation.dataset.training_view import iter_training_rows
from research.laya_formation.training.contracts import canonical_digest, secret_findings
from research.laya_formation.training.smoke import QUESTION_INSTRUCTIONS, sha256_file


def export_model(*, run_root: Path, calibration_rows: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite export: {output}")
    manifest = json.loads((run_root / "training-manifest.json").read_text(encoding="utf-8"))
    calibration = json.loads((run_root / "calibration-bundle.json").read_text(encoding="utf-8"))
    choices: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in iter_training_rows([calibration_rows]):
        choices[row["question_id"]].add(tuple(row["choice_ids"]))
    if set(choices) != set(QUESTION_INSTRUCTIONS) or any(len(values) != 1 for values in choices.values()):
        raise ValueError("question definitions are incomplete or inconsistent")
    definitions = {
        question_id: {
            "instructions": QUESTION_INSTRUCTIONS[question_id],
            "choice_ids": list(next(iter(choices[question_id]))),
        }
        for question_id in sorted(choices)
    }
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
        "format": "atmem-laya-formation-questions-v1",
        "digest": manifest["questions_digest"],
        "questions": definitions,
    }
    (output / "questions.json").write_text(json.dumps(questions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(run_root / "calibration-bundle.json", output / "calibration.json")
    shutil.copy2(run_root / "training-manifest.json", output / "training-manifest.json")
    inventory = [
        {"path": path.relative_to(output).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output.rglob("*")) if path.is_file()
    ]
    receipt = {
        "format": "atmem-laya-formation-export-v1",
        "run_id": manifest["run_id"],
        "objective": manifest["objective"],
        "model_sha256": calibration["model_digest"],
        "questions_digest": manifest["questions_digest"],
        "calibration_digest": calibration["digest"],
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
    parser.add_argument("--calibration-rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = export_model(
        run_root=args.run_root.resolve(), calibration_rows=args.calibration_rows.resolve(),
        output=args.output.resolve(),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
