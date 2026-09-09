"""Checked-in retrieval calibration loading and validation."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_calibration() -> dict[str, Any]:
    resource = files("atmem.retrieve").joinpath("calibration-v1.json")
    value = json.loads(resource.read_text(encoding="utf-8"))
    if value.get("format") != "atmem-retrieval-calibration-v1":
        raise ValueError("unsupported retrieval calibration")
    for key in (
        "direct_threshold",
        "background_threshold",
        "production_semantic_threshold",
        "relevance_weight",
        "prior_weight",
    ):
        score = float(value[key])
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"invalid retrieval calibration value: {key}")
    if float(value["background_threshold"]) >= float(value["direct_threshold"]):
        raise ValueError("background threshold must be below direct threshold")
    return value
