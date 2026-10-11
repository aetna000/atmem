from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


ALLOWED_TRAINING_SPLITS = frozenset({"train", "validation", "calibration"})


def iter_training_rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    """Read only explicitly non-sealed decision rows for training/calibration."""

    for path in paths:
        if "sealed" in {part.casefold() for part in path.parts}:
            raise ValueError("sealed paths are unavailable to the training loader")
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("split") not in ALLOWED_TRAINING_SPLITS:
                    raise ValueError(f"sealed or unknown split at {path}:{line_number}")
                if "expected_choice_ids" not in row:
                    raise ValueError(f"training row lacks target at {path}:{line_number}")
                yield row
