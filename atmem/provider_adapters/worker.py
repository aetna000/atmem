"""Foreground worker entry point used by the provider lifecycle manager."""

from __future__ import annotations

import sys

from .lifecycle import build_runtime, load_config
from .server import serve


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m atmem.provider_adapters.worker INSTANCE")
    instance = sys.argv[1]
    _, config = load_config(instance)
    serve(build_runtime(instance), config["host"], config["port"])


if __name__ == "__main__":
    main()
