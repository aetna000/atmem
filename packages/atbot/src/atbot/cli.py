"""Development CLI for the AtMem intelligence companion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from atbot.companion import CompanionRuntime
from atbot.config import DEFAULT_CONFIG, AtBotConfig, ProviderConfig, load_config, save_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atbot", description="Headless local-first intelligence companion for AtMem"
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Configure the local AtMem companion")
    init.add_argument("--model", default="qwen3:4b")
    init.add_argument("--endpoint", default="http://127.0.0.1:11434")
    init.add_argument("--force", action="store_true")
    commands.add_parser("status", help="Show companion capabilities and providers")
    commands.add_parser("doctor", help="Check companion readiness")
    serve = commands.add_parser("serve", help="Run the private headless companion")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            target = Path(args.config).expanduser()
            if target.exists() and not args.force:
                raise ValueError(f"configuration already exists: {target} (use --force)")
            config = AtBotConfig(
                profile="memory-companion",
                providers=[ProviderConfig(model=args.model, endpoint=args.endpoint)],
            )
            save_config(config, target)
            print(f"AtBot companion configured: {target}")
            print(f"Local model: {args.model} via Ollama")
            print("AtMem owns storage and the customer dashboard.")
            return 0
        config = load_config(args.config)
        companion = CompanionRuntime(config)
        if args.command in {"status", "doctor"}:
            value = companion.capabilities()
            value["config_path"] = str(Path(args.config).expanduser())
            print(json.dumps(value, indent=2, sort_keys=True))
            ready = any(bool(row.get("available")) for row in value["providers"])
            return 0 if ready else 1
        if args.command == "serve":
            from atbot.service import serve

            serve(config, host=args.host or config.host, port=args.port or config.port)
            return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
