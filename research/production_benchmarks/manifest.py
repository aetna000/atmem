from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkManifest:
    name: str
    version: str
    source_url: str
    license: str
    source_ref: str
    expected_sha256: str
    task: str
    status: str

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkManifest":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        required = ("name", "version", "source_url", "license", "source_ref", "expected_sha256", "task", "status")
        # An empty digest is allowed only for exploratory development runs;
        # production-candidate status still requires an exact digest.
        missing = [key for key in required if key != "expected_sha256" and not raw.get(key)]
        if missing:
            raise ValueError(f"benchmark manifest missing: {', '.join(missing)}")
        if raw["status"] not in {"staged", "exploratory", "production-candidate"}:
            raise ValueError("unsupported benchmark status")
        return cls(*(str(raw[key]) for key in required))

    def validate_file(self, data_path: str | Path) -> str:
        digest = hashlib.sha256(Path(data_path).read_bytes()).hexdigest()
        if self.expected_sha256 and digest != self.expected_sha256:
            raise ValueError(f"dataset digest mismatch: expected {self.expected_sha256}, got {digest}")
        return digest

    def claim_status(self, *, full_corpus: bool, baseline: str, metrics: dict[str, Any], digest: str) -> str:
        required_metrics = {"mrr_at_5", "recall_at_1", "recall_at_5", "p50_latency_ms", "p95_latency_ms", "throughput_records_per_second", "errors"}
        gates = bool(self.expected_sha256 and digest == self.expected_sha256 and full_corpus and baseline and metrics.get("validation_issues", 1) == 0 and required_metrics <= set(metrics))
        return "production-candidate" if gates else "exploratory"
