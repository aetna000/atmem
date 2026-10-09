"""Run DolphinBench history ingestion concurrently across independent personas."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from research.production_benchmarks.installed_product import (  # noqa: E402
    installed_atmem_identity,
)


def main() -> int:
    installed_atmem_identity()
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--confirm-local-ingestion", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local_ingestion:
        raise SystemExit("refusing DolphinBench ingestion without confirmation")

    checkout = Path(args.checkout).expanduser().resolve()
    config = Path(args.config).expanduser().resolve()
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))
    from harness import runner as official_runner
    from harness.durable_json import save_json

    original = official_runner.Runner.ingest

    def concurrent_ingest(instance) -> None:
        def ingest_persona(persona: str) -> None:
            release = instance.release[persona]
            checkpoint = instance.directory / "checkpoints" / f"{persona}.json"
            if checkpoint.exists():
                instance.adapter.verify_checkpoint(
                    persona, json.loads(checkpoint.read_text(encoding="utf-8"))
                )
                return
            for spec in release["sessions"]:
                instance._execute("ingestion", persona, spec)
            save_json(checkpoint, instance.adapter.freeze(persona))

        personas = tuple(instance.release)
        with ThreadPoolExecutor(max_workers=len(personas)) as pool:
            futures = [pool.submit(ingest_persona, persona) for persona in personas]
            for future in futures:
                future.result()
        instance._collect_cost("ingestion")

    official_runner.Runner.ingest = concurrent_ingest
    try:
        return int(official_runner.main([
            "ingest", "--config", str(config), "--confirm-paid-calls",
        ]))
    finally:
        official_runner.Runner.ingest = original


if __name__ == "__main__":
    raise SystemExit(main())
