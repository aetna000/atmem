from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from atmem.memory import Memory

DEFAULT_MCP_DB = os.environ.get(
    "ATMEM_DB", str(Path.home() / ".atmem" / "memories.db")
)


def _installed_version() -> str:
    try:
        return version("atmem")
    except PackageNotFoundError:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atmem",
        description="Governed memory and agent oversight, with optional AtBot intelligence.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Start here:
  atmem atbot setup
      Choose local AI, a hosted API, or the safe deterministic fallback.

  atmem openclaw install
      Connect OpenClaw in shadow mode, verify the bridge, and preserve restore.

  atmem control shadow --host generic --memory-db ~/.atmem/memories.db
      Connect another agent framework through the generic control contract.

  atmem dashboard
      Open the local memory, configuration, provenance, and agent-evidence UI.

Run `atmem COMMAND --help` for command-specific examples.""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_version()}",
    )
    subparsers = parser.add_subparsers(dest="command")

    openclaw_parser = subparsers.add_parser(
        "openclaw",
        help="Install and verify the matching OpenClaw bridge",
    )
    openclaw_commands = openclaw_parser.add_subparsers(
        dest="openclaw_command",
    )
    openclaw_install = openclaw_commands.add_parser(
        "install",
        help="Install the bridge and start a native-memory shadow migration",
    )
    openclaw_install.add_argument(
        "--state",
        default=None,
        help="Advanced: override the local migration control-file path",
    )
    openclaw_install.add_argument(
        "--control-root",
        default=None,
        help="Advanced: override the private migration evidence directory",
    )
    openclaw_install.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    openclaw_upgrade = openclaw_commands.add_parser(
        "upgrade",
        help=(
            "Restart a running dashboard, upgrade the bridge, and verify the current "
            "memory mode"
        ),
    )
    openclaw_upgrade.add_argument(
        "--state",
        default=None,
        help="Advanced: override the local migration control-file path",
    )
    openclaw_upgrade.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    openclaw_memory = openclaw_commands.add_parser(
        "memory",
        help="Inspect the OpenClaw memory mirror owned by AtMem",
    )
    openclaw_memory_commands = openclaw_memory.add_subparsers(
        dest="openclaw_memory_command",
    )
    for name, help_text in (
        ("status", "Show native mirror, takeover, audit, and context-budget status"),
        ("sync", "Synchronize changed native OpenClaw memory into the shadow mirror"),
        ("search", "Search the mirrored memory by ordinary words"),
        ("trace", "Trace mirrored memories and their audit evidence"),
    ):
        command_parser = openclaw_memory_commands.add_parser(name, help=help_text)
        command_parser.add_argument("--state", default=None)
        command_parser.add_argument(
            "--json", action="store_true", help="Print machine-readable JSON"
        )
        if name in {"search", "trace"}:
            command_parser.add_argument("query")
            command_parser.add_argument("--limit", type=int, default=50)

    atbot_parser = subparsers.add_parser(
        "atbot",
        help="Choose and manage AtMem's pinned intelligence companion",
        description="Configure AtBot without giving it memory authority or storing API keys.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Recommended:
  atmem atbot setup

Discover and verify:
  atmem atbot providers
  atmem atbot status
  atmem atbot doctor

Direct examples:
  atmem atbot configure --provider local-ollama --model qwen3:4b
  atmem atbot configure --provider openai --model gpt-5-mini
  atmem atbot configure --provider openrouter --model anthropic/claude-sonnet-4.5

For hosted APIs, export the key variable shown by `atmem atbot providers`.
AtMem stores the variable name, never the key.""",
    )
    atbot_commands = atbot_parser.add_subparsers(dest="atbot_command")
    for name, help_text in (
        ("install", "Install the AtMem-pinned AtBot runtime"),
        ("setup", "Choose local AI, a hosted API, or safe fallback interactively"),
        ("providers", "List supported provider profiles and secure key variables"),
        ("configure", "Configure a local or hosted intelligence provider"),
        ("start", "Start the private loopback companion"),
        ("stop", "Stop the AtMem-managed companion"),
        ("restart", "Restart the AtMem-managed companion"),
        ("status", "Show install, configuration, and runtime state"),
        ("doctor", "Verify version, protocol, authority, and fallback safety"),
    ):
        command_parser = atbot_commands.add_parser(name, help=help_text)
        command_parser.add_argument(
            "--json", action="store_true", help="Print machine-readable JSON"
        )
        if name == "install":
            command_parser.add_argument("--force", action="store_true")
        if name == "configure":
            from atmem.control.atbot_service import PROVIDER_PROFILES

            command_parser.formatter_class = argparse.RawDescriptionHelpFormatter
            command_parser.description = (
                "Choose the model AtBot uses for extraction, query expansion, and ranking. "
                "AtMem still authorizes every candidate and stores canonical memory."
            )
            command_parser.epilog = (
                "Examples:\n"
                "  atmem atbot configure --provider local-ollama --model qwen3:4b\n"
                "  atmem atbot configure --provider openai --model gpt-5-mini\n"
                "  atmem atbot configure --provider local-openai --endpoint http://127.0.0.1:8000/v1 --model my-model\n\n"
                "For a hosted provider, export the profile's API-key variable before starting AtBot. "
                "Run `atmem atbot providers` to see the expected variable names."
            )

            command_parser.add_argument(
                "--provider",
                choices=tuple(PROVIDER_PROFILES),
                default="local-ollama",
                help="Provider profile; run `atmem atbot providers` to compare them",
            )
            command_parser.add_argument(
                "--model", default=None, help="Override the profile's model identifier"
            )
            command_parser.add_argument(
                "--endpoint",
                default=None,
                help="Override the profile endpoint; remote endpoints must use HTTPS",
            )
            command_parser.add_argument(
                "--api-key-env",
                default=None,
                help="Environment-variable name containing the API key; never the key itself",
            )
            command_parser.add_argument("--provider-kind", default=None, help=argparse.SUPPRESS)
            command_parser.add_argument(
                "--remote-egress-allowed",
                action="store_true",
                help="Explicitly allow a custom non-loopback endpoint",
            )
            command_parser.add_argument(
                "--force", action="store_true", help="Replace the existing AtBot configuration"
            )

    delegated_parser = subparsers.add_parser(
        "delegated",
        help="Optionally trust an external context authority",
        description=(
            "Native AtMem authority remains the default. Registration never enables "
            "delegation; opt in separately for explicit user, agent, and workspace scopes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
  atmem delegated register --provider-id context-provider --provider-version 1.0 \
    --instance-id local --key-id primary --public-key-file provider.pub \
    --endpoint http://127.0.0.1:8788/v1/delegated-context \
    --workspace ws_123 --agent main --user local-owner
  atmem delegated enable context-provider:local
  atmem delegated doctor

Failure is closed by default. Add --native-fallback only if the operator explicitly
wants AtMem to resume native context preparation when the provider fails.""",
    )
    delegated_commands = delegated_parser.add_subparsers(dest="delegated_command")
    delegated_register = delegated_commands.add_parser(
        "register", help="Register trust and exact scopes; remains disabled"
    )
    delegated_register.add_argument("--provider-id", required=True)
    delegated_register.add_argument("--provider-version", required=True)
    delegated_register.add_argument("--instance-id", required=True)
    delegated_register.add_argument("--key-id", required=True)
    delegated_register.add_argument("--public-key-file", required=True)
    delegated_register.add_argument("--endpoint", required=True)
    delegated_register.add_argument("--workspace", action="append", required=True)
    delegated_register.add_argument("--agent", action="append", required=True)
    delegated_register.add_argument("--user", action="append", required=True)
    delegated_register.add_argument("--timeout-ms", type=int, default=3000)
    delegated_register.add_argument("--max-context-bytes", type=int, default=262144)
    delegated_register.add_argument("--native-fallback", action="store_true")
    delegated_register.add_argument("--replace", action="store_true")
    delegated_register.add_argument("--json", action="store_true")
    for name, help_text in (
        ("enable", "Explicitly enable one registered provider scope"),
        ("disable", "Return one provider scope to native AtMem authority"),
        ("remove", "Remove one disabled provider registration"),
    ):
        command_parser = delegated_commands.add_parser(name, help=help_text)
        command_parser.add_argument("registration_id")
        command_parser.add_argument("--json", action="store_true")
        if name == "remove":
            command_parser.add_argument("--yes", action="store_true")
    for name, help_text in (
        ("status", "Show authority mode, safe scopes, and next action"),
        ("doctor", "Check trust, configuration, and activation safety"),
        ("self-test", "Verify local signature and configuration primitives"),
    ):
        command_parser = delegated_commands.add_parser(name, help=help_text)
        command_parser.add_argument("--json", action="store_true")

    provider_parser = subparsers.add_parser(
        "provider",
        help="Run an optional Mem0, LangGraph, or Pydantic AI context authority",
        description=(
            "Create a signed local context-provider service. Initialization and startup "
            "do not change AtMem authority; registration and enablement remain explicit."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python -m pip install 'atmem[mem0]'
  atmem provider init memory-provider --kind mem0 --mode oss --port 8788
  atmem provider start memory-provider
  atmem provider doctor memory-provider

  python -m pip install 'atmem[langgraph-provider]'
  atmem provider init graph-provider --kind langgraph \
    --factory myapp.context:build_graph --port 8789

  python -m pip install 'atmem[pydantic-provider]'
  atmem provider init ai-provider --kind pydantic-ai \
    --factory myapp.context:build_agent --egress hosted --port 8790

The init result prints the separate `atmem delegated register` command. Run its
matching `atmem delegated enable` command only after reviewing the exact scopes.""",
    )
    provider_commands = provider_parser.add_subparsers(dest="provider_command")
    provider_init = provider_commands.add_parser("init", help="Create private keys and secret-free configuration")
    provider_init.add_argument("instance")
    provider_init.add_argument("--kind", required=True, choices=("mem0", "langgraph", "pydantic-ai"))
    provider_init.add_argument("--port", type=int, default=8788)
    provider_init.add_argument("--factory", default=None, help="Operator factory in module:attribute form")
    provider_init.add_argument("--mode", choices=("oss", "platform"), default=None, help="Mem0 client mode")
    provider_init.add_argument("--provider-id", default=None)
    provider_init.add_argument("--provider-version", default="1.0")
    provider_init.add_argument("--egress", choices=("local", "hosted"), default="local")
    provider_init.add_argument("--json", action="store_true")
    for name, help_text in (
        ("serve", "Run one provider in the foreground"),
        ("start", "Start one private background provider process"),
        ("stop", "Stop only the PID owned by this provider instance"),
        ("doctor", "Check dependencies, files, service health, and next trust step"),
    ):
        command_parser = provider_commands.add_parser(name, help=help_text)
        command_parser.add_argument("instance")
        command_parser.add_argument("--json", action="store_true")
    provider_status = provider_commands.add_parser("status", help="Show redacted provider state")
    provider_status.add_argument("instance", nargs="?")
    provider_status.add_argument("--json", action="store_true")
    provider_remove = provider_commands.add_parser("remove", help="Remove a stopped provider; AtMem evidence is retained")
    provider_remove.add_argument("instance")
    provider_remove.add_argument("--yes", action="store_true")
    provider_remove.add_argument("--json", action="store_true")

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run reproducible memory-quality gates and compare external results",
        description="Offline by default. Optional model profiles require explicit configuration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Release gate:
  atmem benchmark run --output benchmark.json

Optional evidence:
  atmem benchmark profiles
  atmem benchmark run --profile local-embeddings --output local.json

External evaluation:
  atmem benchmark import-longmemeval INPUT.jsonl --output cases.json
  atmem benchmark compare atmem.json mem0.json --output comparison.json""",
    )
    benchmark_commands = benchmark_parser.add_subparsers(dest="benchmark_command")
    benchmark_run = benchmark_commands.add_parser("run", help="Run one isolated benchmark profile")
    benchmark_run.add_argument(
        "--profile",
        choices=("deterministic", "local-embeddings", "local-atbot", "hosted-atbot"),
        default="deterministic",
    )
    benchmark_run.add_argument("--dataset", default=None)
    benchmark_run.add_argument("--thresholds", default=None)
    benchmark_run.add_argument("--output", default=None)
    benchmark_run.add_argument("--json", action="store_true")
    benchmark_profiles = benchmark_commands.add_parser("profiles", help="Show profile availability and egress")
    benchmark_profiles.add_argument("--json", action="store_true")
    benchmark_import = benchmark_commands.add_parser(
        "import-longmemeval", help="Normalize a locally supplied LongMemEval JSON or JSONL file"
    )
    benchmark_import.add_argument("input")
    benchmark_import.add_argument("--output", required=True)
    benchmark_import.add_argument("--json", action="store_true")
    benchmark_compare = benchmark_commands.add_parser(
        "compare", help="Compare compatible AtMem and external result envelopes"
    )
    benchmark_compare.add_argument("left")
    benchmark_compare.add_argument("right")
    benchmark_compare.add_argument("--output", default=None)
    benchmark_compare.add_argument("--json", action="store_true")

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Run the local host-neutral memory, flight, audit, and switch UI",
    )
    dashboard_parser.add_argument("--state", default=None)
    dashboard_parser.add_argument("--port", type=int, default=8766)
    dashboard_parser.add_argument("--no-open", action="store_true")
    dashboard_commands = dashboard_parser.add_subparsers(dest="dashboard_command")
    dashboard_daemon = dashboard_commands.add_parser(
        "daemon", help="Manage the dashboard as a background user service"
    )
    dashboard_daemon_commands = dashboard_daemon.add_subparsers(
        dest="dashboard_daemon_command"
    )
    for name in ("start", "open", "stop", "restart", "status", "remove"):
        command_parser = dashboard_daemon_commands.add_parser(name)
        command_parser.add_argument("--state", default=None)
        command_parser.add_argument("--port", type=int, default=8766)
        command_parser.add_argument(
            "--json", action="store_true", help="Print machine-readable JSON"
        )

    remember_parser = subparsers.add_parser(
        "remember", help="Ingest a message through the write pipeline"
    )
    remember_parser.add_argument("path")
    remember_parser.add_argument("subject_id")
    remember_parser.add_argument("message")
    remember_parser.add_argument("--session", default=None)
    remember_parser.add_argument("--turn", default=None)
    remember_parser.add_argument(
        "--source-type",
        default=None,
        help="Override source classification (user_message, webpage, tool_output)",
    )

    observe_parser = subparsers.add_parser(
        "observe",
        help="Admit one typed, quarantined text observation of host-controlled media",
    )
    observe_parser.add_argument("path")
    observe_parser.add_argument("subject_id")
    observe_parser.add_argument(
        "--envelope",
        required=True,
        help="JSON envelope file, or - to read JSON from stdin",
    )
    observe_parser.add_argument("--session", default=None)
    observe_parser.add_argument("--turn", default=None)

    recall_parser = subparsers.add_parser(
        "recall", help="Top-k recall over active records"
    )
    recall_parser.add_argument("path")
    recall_parser.add_argument("subject_id")
    recall_parser.add_argument("query")
    recall_parser.add_argument("--limit", type=int, default=10)
    recall_parser.add_argument("--min-score", type=float, default=None)
    recall_parser.add_argument("--session", default=None)
    recall_parser.add_argument(
        "--graph", action="store_true", help="Blend bounded graph seed-and-spread recall"
    )

    graph_backfill_parser = subparsers.add_parser(
        "graph-backfill", help="Build the derived graph index from canonical records"
    )
    graph_backfill_parser.add_argument("path")
    graph_backfill_parser.add_argument("subject_id")
    graph_backfill_parser.add_argument(
        "--rebuild", action="store_true", help="Drop and deterministically rebuild graph rows"
    )

    graph_inspect_parser = subparsers.add_parser(
        "graph-inspect", help="Inspect derived entities, aliases, edges, and counts"
    )
    graph_inspect_parser.add_argument("path")
    graph_inspect_parser.add_argument("subject_id")

    graph_consolidate_parser = subparsers.add_parser(
        "graph-consolidate",
        help="Backfill graph state, propose entity merges, and optionally archive history",
    )
    graph_consolidate_parser.add_argument("path")
    graph_consolidate_parser.add_argument("subject_id")
    graph_consolidate_parser.add_argument("--archive-root", default=None)
    graph_consolidate_parser.add_argument("--archive-before", default=None)
    graph_consolidate_parser.add_argument("--no-prune", action="store_true")

    graph_merges_parser = subparsers.add_parser(
        "graph-merges", help="List reviewer-gated entity merge proposals"
    )
    graph_merges_parser.add_argument("path")
    graph_merges_parser.add_argument("subject_id")
    graph_merges_parser.add_argument("--status", default=None)

    graph_merge_parser = subparsers.add_parser(
        "graph-merge", help="Approve, reject, or revert an entity merge proposal"
    )
    graph_merge_parser.add_argument("path")
    graph_merge_parser.add_argument("subject_id")
    graph_merge_parser.add_argument("proposal_id")
    graph_merge_parser.add_argument("decision", choices=("approve", "reject", "revert"))
    graph_merge_parser.add_argument("--winner", default=None)
    graph_merge_parser.add_argument("--actor", default="reviewer")

    graph_history_parser = subparsers.add_parser(
        "graph-history", help="Read verified inactive-edge archive partitions"
    )
    graph_history_parser.add_argument("path")
    graph_history_parser.add_argument("subject_id")
    graph_history_parser.add_argument("--year", type=int, default=None)

    optimize_parser = subparsers.add_parser(
        "optimize", help="Run SQLite PRAGMA optimize maintenance"
    )
    optimize_parser.add_argument("path")

    index_parser = subparsers.add_parser(
        "index",
        help="Inspect, upgrade, and verify the derived local vector index",
    )
    index_commands = index_parser.add_subparsers(
        dest="index_command"
    )
    index_build = index_commands.add_parser(
        "build", help="Build and activate a verified versioned index epoch"
    )
    index_build.add_argument("path")
    index_build.add_argument("--subject", required=True)
    index_build.add_argument(
        "--embedder",
        choices=("ollama", "openai-compatible", "sentence-transformers", "hashing"),
        default="ollama",
    )
    index_build.add_argument("--model", default=None)
    index_build.add_argument("--model-version", default="unverified")
    index_build.add_argument("--endpoint", default=None)
    index_build.add_argument("--api-key-env", default=None)
    index_build.add_argument("--index-path", default=None)
    index_build.add_argument("--batch-size", type=int, default=64)

    index_status = index_commands.add_parser(
        "status", help="Show active and retired semantic index epochs"
    )
    index_status.add_argument("path")
    index_status.add_argument("--subject", default=None)
    index_status.add_argument("--index-path", default=None)

    index_verify = index_commands.add_parser(
        "verify", help="Fail if vectors are stale, orphaned, unsafe, or incomplete"
    )
    index_verify.add_argument("path")
    index_verify.add_argument("--subject", required=True)
    index_verify.add_argument("--index-path", default=None)

    semantic_parser = subparsers.add_parser(
        "semantic",
        help="Set up, diagnose, and safely rebuild semantic retrieval",
        description="Set up, diagnose, and safely rebuild semantic retrieval.",
    )
    semantic_commands = semantic_parser.add_subparsers(dest="semantic_command")
    for name, help_text in (
        ("setup", "Choose a local model, build its index, and test a paraphrase"),
        ("status", "Show authoritative semantic health and corrective actions"),
        ("rebuild", "Resume or rebuild an inactive epoch, then activate it safely"),
        ("verify", "Verify coverage, identity, dimensions, and canonical digests"),
    ):
        command_parser = semantic_commands.add_parser(name, help=help_text)
        command_parser.add_argument("path")
        command_parser.add_argument("--subject", required=True)
        command_parser.add_argument("--index-path", default=None)
        command_parser.add_argument(
            "--json", action="store_true", help="Print machine-readable JSON"
        )
        if name in {"setup", "rebuild"}:
            command_parser.add_argument(
                "--provider",
                choices=("ollama", "openai-compatible", "sentence-transformers", "hashing"),
                default=None,
            )
            command_parser.add_argument("--model", default=None)
            command_parser.add_argument("--model-version", default="unverified")
            command_parser.add_argument("--endpoint", default=None)
            command_parser.add_argument("--api-key-env", default=None)
            command_parser.add_argument("--batch-size", type=int, default=64)
        if name == "setup":
            command_parser.add_argument(
                "--allow-download",
                action="store_true",
                help="Explicitly permit the selected local runtime to download model files",
            )
            command_parser.add_argument(
                "--allow-egress",
                action="store_true",
                help="Explicitly permit requests to a configured remote embedding endpoint",
            )
            command_parser.add_argument(
                "--smoke-query",
                default=None,
                help="Manual paraphrase used to verify the first eligible record",
            )

    task_parser = subparsers.add_parser(
        "task",
        help="Start, inspect, and govern task state for an agent",
        description="Start, inspect, and govern task state for an agent.",
        epilog="""Examples:
  atmem task enable memories.db --subject user-1 --agent agent-1 --workspace ws-1
      Turn on governed task state for one exact scope.

  atmem task start memories.db --task-id task-1 --goal "Ship the migration" \
      --subject user-1 --agent agent-1 --workspace ws-1 --actor you@example.com
      Begin a governed task.

  atmem task list memories.db --subject user-1 --agent agent-1 --workspace ws-1
      See open work, newest state first.

  atmem task show memories.db task-1 --subject user-1 --agent agent-1 --workspace ws-1
      Read the goal, phase, progress, blockers, and next eligible work.

Exit codes: 0 for a successful read, an accepted action, or no_change;
1 for rejected, conflict, unavailable, or integrity outcomes; 2 for usage
or input errors.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    task_commands = task_parser.add_subparsers(dest="task_command")

    def _scoped(name: str, help_text: str, *, needs_task: bool = False):
        command = task_commands.add_parser(name, help=help_text)
        command.add_argument("path")
        if needs_task:
            command.add_argument("task_id")
        command.add_argument("--subject", required=True)
        command.add_argument("--agent", required=True)
        command.add_argument("--workspace", required=True)
        command.add_argument(
            "--json", action="store_true", help="Print one machine-readable document"
        )
        return command

    _scoped("enable", "Turn on governed task state for one exact scope")
    _scoped("disable", "Turn governed task state off for one exact scope")

    task_start = _scoped("start", "Start a governed task")
    task_start.add_argument("--task-id", required=True)
    task_start.add_argument("--goal", required=True)
    task_start.add_argument("--actor", required=True)
    task_start.add_argument("--profile", default="general-v1")
    task_start.add_argument(
        "--item", action="append", default=[],
        help="Add an item as ID=Title, repeatable",
    )
    task_start.add_argument(
        "--required-item", action="append", default=[],
        help="Add a completion-required item as ID=Title, repeatable",
    )
    task_start.add_argument("--constraint", action="append", default=[])
    task_start.add_argument("--source", action="append", default=[])
    task_start.add_argument("--continues", default=None)

    task_list = _scoped("list", "List governed tasks in this scope")
    task_list.add_argument("--lifecycle", action="append", default=[])
    task_list.add_argument("--cursor", default=None)
    task_list.add_argument("--limit", type=int, default=50)

    _scoped("show", "Show one task's goal, progress, blockers, and next work",
            needs_task=True)
    _scoped("timeline", "Show every revision, decision, and delivery for a task",
            needs_task=True)
    _scoped("health", "Show scope-filtered task health and counters")
    _scoped("verify", "Check revision-chain integrity for this scope")

    task_provenance = _scoped(
        "provenance", "Explain where one task value came from", needs_task=True
    )
    task_provenance.add_argument(
        "--target-kind", required=True,
        choices=("task", "field", "item", "status", "constraint", "transition",
                 "delivery", "lifecycle"),
    )
    task_provenance.add_argument("--target-id", required=True)

    for name, help_text in (
        ("pause", "Pause a task without losing its place"),
        ("resume", "Resume a paused task"),
        ("complete", "Complete a task once its gates are satisfied"),
        ("cancel", "Cancel a task and record why"),
    ):
        command = _scoped(name, help_text, needs_task=True)
        command.add_argument("--actor", required=True)
        command.add_argument("--reason", default="")
        command.add_argument("--expected-revision", type=int, default=None)
        command.add_argument(
            "--yes", action="store_true",
            help="Confirm without prompting; required in non-interactive use",
        )

    task_correct = _scoped(
        "correct", "Correct one item's status as an operator", needs_task=True
    )
    task_correct.add_argument("--actor", required=True)
    task_correct.add_argument("--item", required=True)
    task_correct.add_argument(
        "--status", required=True,
        choices=("pending", "ready", "running", "blocked", "completed",
                 "skipped", "failed"),
    )
    task_correct.add_argument("--reason", required=True)
    task_correct.add_argument("--expected-revision", type=int, required=True)
    task_correct.add_argument("--yes", action="store_true")

    task_bind = _scoped(
        "bind", "Bind one host conversation to a task", needs_task=True
    )
    task_bind.add_argument("--actor", required=True)
    task_bind.add_argument("--reason", required=True)
    task_bind.add_argument(
        "--host-type", required=True,
        help="Which host this conversation lives in, e.g. openclaw",
    )
    task_bind.add_argument(
        "--session-key", required=True, help="The host's stable conversation address"
    )
    task_bind.add_argument(
        "--session-epoch", required=True,
        help=(
            "The host's session generation, which changes when a conversation is "
            "reset. Required: without it a recycled key would inherit this binding"
        ),
    )
    task_bind.add_argument("--source", default="")
    task_bind.add_argument("--yes", action="store_true")

    task_unbind = _scoped("unbind", "Revoke one conversation's binding")
    task_unbind.add_argument("--binding-id", required=True)
    task_unbind.add_argument("--actor", required=True)
    task_unbind.add_argument("--reason", required=True)
    task_unbind.add_argument("--yes", action="store_true")

    task_bindings = _scoped("bindings", "List conversation bindings in this scope")
    task_bindings.add_argument("--task-id", default=None)
    task_bindings.add_argument(
        "--include-revoked", action="store_true",
        help="Include revoked bindings; history is retained as evidence",
    )

    task_forget = _scoped(
        "forget", "Permanently delete a task and everything derived from it",
        needs_task=True,
    )
    task_forget.add_argument("--actor", required=True)
    task_forget.add_argument("--yes", action="store_true")

    task_profile = task_commands.add_parser(
        "profile", help="Inspect and register versioned task profiles"
    )
    profile_commands = task_profile.add_subparsers(dest="profile_command")
    profile_list = profile_commands.add_parser("list", help="List known profiles")
    profile_list.add_argument("path")
    profile_list.add_argument("--json", action="store_true")
    profile_show = profile_commands.add_parser("show", help="Show one profile")
    profile_show.add_argument("path")
    profile_show.add_argument("version")
    profile_show.add_argument("--json", action="store_true")
    profile_register = profile_commands.add_parser(
        "register", help="Register an immutable versioned profile"
    )
    profile_register.add_argument("path")
    profile_register.add_argument("file", help="JSON profile document")
    profile_register.add_argument("--actor", required=True)
    profile_register.add_argument(
        "--dry-run", action="store_true", help="Validate without registering"
    )
    profile_register.add_argument("--yes", action="store_true")
    profile_register.add_argument("--json", action="store_true")

    proposals_parser = subparsers.add_parser(
        "proposals",
        help="Inspect and decide governed memory proposals awaiting review",
        description="Inspect and decide governed memory proposals awaiting review.",
    )
    proposals_commands = proposals_parser.add_subparsers(dest="proposals_command")

    proposals_queue = proposals_commands.add_parser(
        "queue", help="List proposals waiting for a review decision"
    )
    proposals_queue.add_argument("path")
    proposals_queue.add_argument("--subject", default=None)
    proposals_queue.add_argument("--limit", type=int, default=100)
    proposals_queue.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    proposals_show = proposals_commands.add_parser(
        "show", help="Show one proposal with its exact source evidence"
    )
    proposals_show.add_argument("path")
    proposals_show.add_argument("proposal_id")
    proposals_show.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    proposals_decide = proposals_commands.add_parser(
        "decide", help="Approve, edit and approve, or reject one proposal"
    )
    proposals_decide.add_argument("path")
    proposals_decide.add_argument("proposal_id")
    proposals_decide.add_argument(
        "decision", choices=("approve", "edit_and_approve", "reject")
    )
    proposals_decide.add_argument(
        "--actor", required=True, help="Who is making this decision, for the audit log"
    )
    proposals_decide.add_argument("--reason", default="")
    proposals_decide.add_argument(
        "--fact", default=None, help="Replacement fact text for edit_and_approve"
    )
    proposals_decide.add_argument("--session", default=None)
    proposals_decide.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    proposals_lineage = proposals_commands.add_parser(
        "lineage", help="Show how corrected and superseding records relate"
    )
    proposals_lineage.add_argument("path")
    proposals_lineage.add_argument("subject_id")
    proposals_lineage.add_argument("--record-id", default=None)
    proposals_lineage.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    list_parser = subparsers.add_parser("list", help="List a subject's records")
    list_parser.add_argument("path")
    list_parser.add_argument("subject_id")
    list_parser.add_argument(
        "--all", action="store_true", help="Include superseded/quarantined/tombstoned"
    )

    memories_parser = subparsers.add_parser(
        "memories", help="Browse and search a user's memories without recording a recall"
    )
    memories_parser.add_argument("path")
    memories_parser.add_argument("--subject", required=True)
    memories_parser.add_argument("--query", default="")
    memories_parser.add_argument(
        "--status",
        action="append",
        choices=("active", "quarantined", "superseded", "tombstoned"),
        default=[],
        help="Filter by status; repeat to select more than one",
    )
    memories_parser.add_argument(
        "--all", action="store_true", help="Include every memory status"
    )
    memories_parser.add_argument("--since", default=None, help="ISO date or timestamp")
    memories_parser.add_argument("--until", default=None, help="ISO date or timestamp")
    memories_parser.add_argument("--limit", type=int, default=100)
    _add_semantic_search_arguments(memories_parser)
    _add_access_audit_arguments(memories_parser)
    _add_report_arguments(memories_parser)

    search_parser = subparsers.add_parser(
        "search", help="Search across memories and audit evidence without agent recall"
    )
    search_parser.add_argument("path")
    search_parser.add_argument("query", nargs="?", default="")
    search_parser.add_argument("--subject", required=True)
    search_parser.add_argument(
        "--scope",
        choices=(
            "all",
            "memories",
            "media",
            "episodes",
            "retrievals",
            "events",
        ),
        default="all",
    )
    search_parser.add_argument(
        "--status",
        action="append",
        choices=("active", "quarantined", "superseded", "tombstoned"),
        default=[],
    )
    search_parser.add_argument("--session", default=None)
    search_parser.add_argument(
        "--event-type", default=None, help="Exact type or wildcard such as memory.*"
    )
    search_parser.add_argument("--actor", default=None)
    search_parser.add_argument("--since", default=None, help="ISO date or timestamp")
    search_parser.add_argument("--until", default=None, help="ISO date or timestamp")
    search_parser.add_argument("--limit", type=int, default=100)
    _add_semantic_search_arguments(search_parser)
    _add_access_audit_arguments(search_parser)
    _add_report_arguments(search_parser)

    trace_parser = subparsers.add_parser(
        "trace", help="Find a clue and reconstruct its chronological evidence trail"
    )
    trace_parser.add_argument("path")
    trace_parser.add_argument("query", nargs="?", default="")
    trace_parser.add_argument("--subject", required=True)
    trace_parser.add_argument("--session", default=None)
    trace_parser.add_argument("--run", default=None)
    trace_parser.add_argument("--record", default=None)
    trace_parser.add_argument(
        "--event-type", default=None, help="Exact type or wildcard such as memory.*"
    )
    trace_parser.add_argument("--since", default=None, help="ISO date or timestamp")
    trace_parser.add_argument("--until", default=None, help="ISO date or timestamp")
    trace_parser.add_argument("--limit", type=int, default=500)
    _add_semantic_search_arguments(trace_parser)
    _add_access_audit_arguments(trace_parser)
    _add_report_arguments(trace_parser)

    access_log_parser = subparsers.add_parser(
        "access-log", help="List and verify the separate investigator access chain"
    )
    access_log_parser.add_argument("path")
    access_log_parser.add_argument("--subject", required=True)

    forget_parser = subparsers.add_parser(
        "forget", help="Tombstone + purge matching records; prints a deletion receipt"
    )
    forget_parser.add_argument("path")
    forget_parser.add_argument("subject_id")
    forget_group = forget_parser.add_mutually_exclusive_group(required=True)
    forget_group.add_argument("--contains", default=None)
    forget_group.add_argument(
        "--utterance", default=None, help='e.g. "Forget my backup email."'
    )
    forget_parser.add_argument("--session", default=None)

    forget_artifact_parser = subparsers.add_parser(
        "forget-artifact",
        help="Purge all AtMem derivatives of one exact media-byte SHA-256",
    )
    forget_artifact_parser.add_argument("path")
    forget_artifact_parser.add_argument("subject_id")
    forget_artifact_parser.add_argument("media_sha256")
    forget_artifact_parser.add_argument("--artifact-id", default=None)
    forget_artifact_parser.add_argument("--session", default=None)
    forget_artifact_parser.add_argument("--turn", default=None)

    promote_parser = subparsers.add_parser(
        "promote", help="Activate a quarantined record and audit the trust transition"
    )
    promote_parser.add_argument("path")
    promote_parser.add_argument("subject_id")
    promote_parser.add_argument("record_id")
    promote_parser.add_argument("--session", default=None)

    log_action_parser = subparsers.add_parser(
        "log-action", help="Append an agent action event to the audit chain"
    )
    log_action_parser.add_argument("path")
    log_action_parser.add_argument("subject_id")
    log_action_parser.add_argument("action_type")
    log_action_parser.add_argument(
        "--payload", default="{}", help="JSON object (store digests, not raw content)"
    )
    log_action_parser.add_argument("--session", default=None)
    log_action_parser.add_argument("--turn", default=None)

    consolidate_parser = subparsers.add_parser(
        "consolidate",
        help="Deterministic cleanup: collapse duplicate actives, repair fact-key conflicts",
    )
    consolidate_parser.add_argument("path")
    consolidate_parser.add_argument("subject_id")

    persona_parser = subparsers.add_parser(
        "persona", help="Deterministic L3 persona snapshot derived from active records"
    )
    persona_parser.add_argument("path")
    persona_parser.add_argument("subject_id")
    persona_parser.add_argument("--max-chars", type=int, default=1500)

    context_parser = subparsers.add_parser(
        "context-pack", help="Build host-neutral stable and dynamic prompt context"
    )
    context_parser.add_argument("path")
    context_parser.add_argument("subject_id")
    context_parser.add_argument("query")
    context_parser.add_argument("--session", default=None)
    context_parser.add_argument("--persona-max-chars", type=int, default=600)
    context_parser.add_argument("--recall-max-records", type=int, default=3)
    context_parser.add_argument("--recall-max-chars", type=int, default=1200)
    context_parser.add_argument("--min-score", type=float, default=0.3)
    context_parser.add_argument("--graph", action="store_true")
    context_parser.add_argument(
        "--reference-mode", choices=("full", "compact", "none"), default="compact"
    )

    scenes_parser = subparsers.add_parser(
        "scenes", help="Deterministic L2 scene view: sessions with their episodes/records"
    )
    scenes_parser.add_argument("path")
    scenes_parser.add_argument("subject_id")

    propose_parser = subparsers.add_parser(
        "propose",
        help="Submit derived fact proposals (JSON array on stdin); they land quarantined with evidence",
    )
    propose_parser.add_argument("path")
    propose_parser.add_argument("subject_id")
    propose_parser.add_argument("--proposer", default="llm")

    inspect_parser = subparsers.add_parser(
        "inspect", help="Dump a subject's records, episodes, and audit trail"
    )
    inspect_parser.add_argument("path")
    inspect_parser.add_argument("subject_id")

    audit_parser = subparsers.add_parser(
        "audit", help="Dump a subject's audit log and verify the hash chain"
    )
    audit_parser.add_argument("path")
    audit_parser.add_argument("subject_id")

    checkpoint_parser = subparsers.add_parser(
        "checkpoint",
        help="Snapshot all audit-chain heads; anchor the output externally",
    )
    checkpoint_parser.add_argument("path")
    checkpoint_parser.add_argument(
        "sink", nargs="?", help="JSONL file to append the checkpoint to"
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify audit-chain integrity, optionally against checkpoints",
    )
    verify_parser.add_argument("path")
    verify_parser.add_argument("--subject", default=None)
    verify_parser.add_argument(
        "--checkpoints", default=None, help="JSONL checkpoint file to check against"
    )
    verify_parser.add_argument(
        "--incremental",
        action="store_true",
        help="verify only the suffix after a locally cached, hash-checked head",
    )

    mcp_parser = subparsers.add_parser(
        "mcp", help="Serve the verbs as MCP tools over stdio"
    )
    mcp_parser.add_argument(
        "--db",
        default=DEFAULT_MCP_DB,
        help=f"SQLite path (default: $ATMEM_DB or {DEFAULT_MCP_DB})",
    )
    mcp_parser.add_argument(
        "--subject",
        default="default",
        help="Subject used when a tool call omits subject_id",
    )
    mcp_parser.add_argument(
        "--checkpoints",
        default=None,
        help="Default checkpoint JSONL for the memory_verify tool",
    )
    mcp_parser.add_argument("--retain-query-text", action="store_true")

    control_parser = subparsers.add_parser(
        "control", help="Manage host-neutral shadowing, activation, evidence, and adapters"
    )
    control_commands = control_parser.add_subparsers(
        dest="control_command"
    )
    control_shadow = control_commands.add_parser(
        "shadow", help="Start safe observation without changing model context"
    )
    control_shadow.add_argument(
        "--host",
        choices=("generic", "openclaw"),
        default="generic",
        help="Runtime adapter; generic starts safe event-driven shadow mode",
    )
    control_shadow.add_argument(
        "--state",
        default=None,
        help="Advanced: override the local migration control-file path",
    )
    control_shadow.add_argument(
        "--control-root",
        default=None,
        help="Advanced: override the private migration evidence directory",
    )
    control_shadow.add_argument(
        "--memory-db",
        default=None,
        help="Generic adapter canonical memory database (defaults to $ATMEM_DB or an isolated control database)",
    )
    control_shadow.add_argument(
        "--no-configure",
        action="store_true",
        help="Testing only: create migration state without installing the host hook",
    )
    control_shadow.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    for name, help_text in (
        ("status", "Show which memory provider is active and whether switching is safe"),
        ("activate", "Allow the runtime adapter to inject approved AtMem context"),
        ("restore", "Return to shadow or restore native host memory; preserve evidence"),
        ("verify", "Measure the migration without repairing or restarting it"),
        ("mcp", "Serve the private host-integration protocol over stdio"),
        ("operator-mcp", "Serve the complete host-neutral operator protocol"),
        ("dashboard", "Open the local memory, flight, audit, and switch dashboard"),
        ("agents", "List registered agents and their memory workspace scopes"),
        ("configure-agents", "Replace the generic agent/workspace topology from JSON"),
        ("memory-sync", "Refresh adapter memory or verify event-driven shadow state"),
        ("memory-status", "Show host-neutral shadow/active memory status"),
        ("memory-search", "Search memory for one agent workspace"),
        ("memory-reviews", "List memories waiting for an operator decision"),
        ("memory-record", "Inspect one memory and its lifecycle evidence"),
        ("memory-audit", "Search the host-neutral memory evidence chain"),
        ("memory-review", "Approve or reject one exact shadow memory"),
    ):
        command_parser = control_commands.add_parser(name, help=help_text)
        command_parser.add_argument("--state", default=None)
        if name not in {"mcp", "operator-mcp", "dashboard"}:
            command_parser.add_argument(
                "--json", action="store_true", help="Print machine-readable JSON"
            )
        if name == "dashboard":
            command_parser.add_argument("--port", type=int, default=8766)
            command_parser.add_argument("--no-open", action="store_true")
        if name in {"activate", "restore"}:
            command_parser.add_argument(
                "--yes", action="store_true", help="Confirm non-interactively"
            )
        if name == "restore":
            command_parser.add_argument(
                "--drill",
                action="store_true",
                help="Test file restoration and config readability without changing live state",
            )
        if name == "verify":
            command_parser.add_argument(
                "--probe",
                action="store_true",
                help="Attempt an isolated context comparison; skip when isolation is unavailable",
            )
        if name == "configure-agents":
            command_parser.add_argument(
                "file", help="JSON array of agents, or - to read from stdin"
            )
        if name == "memory-search":
            command_parser.add_argument("query")
            command_parser.add_argument("--agent", default=None)
            command_parser.add_argument("--subject", default=None)
            command_parser.add_argument("--limit", type=int, default=50)
        if name == "memory-review":
            command_parser.add_argument("record_id")
            command_parser.add_argument("decision", choices=("approve", "reject"))
        if name == "memory-record":
            command_parser.add_argument("record_id")
        if name == "memory-audit":
            command_parser.add_argument("--query", default="")
            command_parser.add_argument("--event-type", default="")
            command_parser.add_argument("--actor", default="")
            command_parser.add_argument("--session", default="")
            command_parser.add_argument("--record", default="")
            command_parser.add_argument("--since", default="")
            command_parser.add_argument("--until", default="")
            command_parser.add_argument("--limit", type=int, default=100)
            command_parser.add_argument(
                "--format",
                choices=("json", "ndjson", "csv", "text"),
                default="json",
                help="Portable export format (used with --output)",
            )
            command_parser.add_argument(
                "--output",
                default=None,
                help="Write the complete filtered audit export to this file",
            )

    blackbox_parser = subparsers.add_parser(
        "blackbox",
        help="Inspect tamper-evident agent flight records",
    )
    blackbox_commands = blackbox_parser.add_subparsers(
        dest="blackbox_command"
    )
    for name, help_text in (
        ("status", "Show recorder coverage and evidence-chain integrity"),
        ("runs", "List recently observed agent runs"),
        ("show", "Show one chronological agent flight"),
        ("story", "Show one concise human-readable flight story"),
        ("verify", "Verify one flight's chain and tool-event closure"),
        ("export", "Export one portable flight investigation report"),
        ("ack", "Acknowledge one exact active flight finding"),
        ("record", "Append one host-observed model, tool, or lifecycle event"),
    ):
        command_parser = blackbox_commands.add_parser(name, help=help_text)
        command_parser.add_argument("--state", default=None)
        command_parser.add_argument(
            "--json", action="store_true", help="Print machine-readable JSON"
        )
        if name in {"show", "story", "verify", "export", "ack", "record"}:
            command_parser.add_argument("run_id")
        if name in {"status", "runs"}:
            command_parser.add_argument("--limit", type=int, default=50)
        if name == "export":
            command_parser.add_argument(
                "--format", choices=("json", "text"), default="json"
            )
            command_parser.add_argument("--output", required=True)
        if name == "ack":
            command_parser.add_argument("attention_code")
            command_parser.add_argument("--actor", default="cli-operator")
        if name == "record":
            command_parser.add_argument("event_type")
            command_parser.add_argument(
                "--envelope", required=True, help="JSON object file, or - for stdin"
            )

    verify_run_parser = subparsers.add_parser(
        "verify-run",
        help="Verify one agent run and print its unified coverage report",
    )
    verify_run_parser.add_argument("run_id")
    verify_run_parser.add_argument("--state", default=None)
    verify_run_parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )

    args = parser.parse_args()

    if args.command is None:
        _print_cli_welcome(parser)
        return

    if args.command == "openclaw":
        if args.openclaw_command is None:
            openclaw_parser.print_help()
            return
        if args.openclaw_command == "memory" and args.openclaw_memory_command is None:
            openclaw_memory.print_help()
            return
        _run_openclaw(args)
        return

    if args.command == "atbot":
        if args.atbot_command is None:
            atbot_parser.print_help()
            return
        _run_atbot(args)
        return

    if args.command == "delegated":
        if args.delegated_command is None:
            delegated_parser.print_help()
            return
        _run_delegated(args)
        return

    if args.command == "provider":
        if args.provider_command is None:
            provider_parser.print_help()
            return
        _run_provider(args)
        return

    if args.command == "benchmark":
        if args.benchmark_command is None:
            benchmark_parser.print_help()
            return
        _run_benchmark_cli(args)
        return

    if args.command == "dashboard":
        if args.dashboard_command == "daemon" and args.dashboard_daemon_command is None:
            dashboard_daemon.print_help()
            return
        _run_dashboard(args)
        return

    if args.command == "control":
        if args.control_command is None:
            control_parser.print_help()
            return
        _run_control(args)
        return

    if args.command == "blackbox":
        if args.blackbox_command is None:
            blackbox_parser.print_help()
            return
        _run_blackbox(args)
        return

    if args.command == "verify-run":
        args.blackbox_command = "verify"
        _run_blackbox(args)
        return

    if args.command == "index":
        if args.index_command is None:
            index_parser.print_help()
            return
        _run_index(args)
        return

    if args.command == "semantic":
        if args.semantic_command is None:
            semantic_parser.print_help()
            return
        _run_semantic(args)
        return

    if args.command == "task":
        if args.task_command is None:
            task_parser.print_help()
            return
        _run_task(args)
        return

    if args.command == "proposals":
        if args.proposals_command is None:
            proposals_parser.print_help()
            return
        _run_proposals(args)
        return

    if args.command == "mcp":
        from atmem.mcp import MCPServer

        memory = Memory(args.db, retain_query_text=args.retain_query_text)
        MCPServer(
            memory,
            default_subject=args.subject,
            checkpoints_path=args.checkpoints,
        ).serve()
        return

    memory = Memory(args.path)

    if args.command == "remember":
        result = memory.remember(
            args.subject_id,
            args.message,
            session_id=args.session,
            turn_id=args.turn,
            source_type=args.source_type,
        )
        _print(result)
    elif args.command == "observe":
        envelope_text = (
            sys.stdin.read()
            if args.envelope == "-"
            else Path(args.envelope).read_text(encoding="utf-8")
        )
        envelope = json.loads(envelope_text)
        if not isinstance(envelope, dict):
            raise ValueError("media observation envelope must be a JSON object")
        _print(
            memory.remember_observation(
                args.subject_id,
                envelope,
                session_id=args.session,
                turn_id=args.turn,
                actor="cli-caller",
                forced_assurance="caller_asserted",
            )
        )
    elif args.command == "recall":
        _print(
            memory.recall(
                args.subject_id,
                args.query,
                session_id=args.session,
                limit=args.limit,
                min_score=args.min_score,
                use_graph=args.graph,
            )
        )
    elif args.command == "graph-backfill":
        _print(memory.backfill_graph(args.subject_id, rebuild=args.rebuild))
    elif args.command == "graph-inspect":
        _print(memory.inspect_graph(args.subject_id))
    elif args.command == "graph-consolidate":
        _print(
            memory.consolidate_graph(
                args.subject_id,
                archive_root=args.archive_root,
                archive_before=args.archive_before,
                prune_archive=not args.no_prune,
            )
        )
    elif args.command == "graph-merges":
        _print(memory.list_graph_merge_proposals(args.subject_id, status=args.status))
    elif args.command == "graph-merge":
        if args.decision == "revert":
            _print(
                memory.revert_graph_merge(
                    args.subject_id, args.proposal_id, actor=args.actor
                )
            )
        else:
            _print(
                memory.decide_graph_merge(
                    args.subject_id,
                    args.proposal_id,
                    approve=args.decision == "approve",
                    actor=args.actor,
                    winner_entity=args.winner,
                )
            )
    elif args.command == "graph-history":
        _print(memory.read_graph_archive(args.subject_id, partition_year=args.year))
    elif args.command == "optimize":
        memory.optimize()
        _print({"optimized": True})
    elif args.command == "list":
        _print(memory.list(args.subject_id, include_inactive=args.all))
    elif args.command == "memories":
        from atmem.investigate import format_memories, search_evidence

        semantic_index, embedder = _semantic_search_resources(args, memory)
        try:
            statuses = args.status or (
                ("active", "quarantined", "superseded", "tombstoned")
                if args.all
                else ("active",)
            )
            report = search_evidence(
                memory,
                args.subject,
                args.query,
                scope="memories",
                statuses=statuses,
                since=args.since,
                until=args.until,
                limit=args.limit,
                mode=args.mode,
                semantic_index=semantic_index,
                embedder=embedder,
                min_similarity=args.min_similarity,
                audit_access=args.audit_access,
                access_actor=args.access_actor,
                access_operation="memories",
            )
            _emit_report(report, format_memories(report), args)
        finally:
            if semantic_index is not None:
                semantic_index.close()
    elif args.command == "search":
        from atmem.investigate import format_search, search_evidence

        semantic_index, embedder = _semantic_search_resources(args, memory)
        try:
            report = search_evidence(
                memory,
                args.subject,
                args.query,
                scope=args.scope,
                statuses=args.status,
                session_id=args.session,
                event_type=args.event_type,
                actor=args.actor,
                since=args.since,
                until=args.until,
                limit=args.limit,
                mode=args.mode,
                semantic_index=semantic_index,
                embedder=embedder,
                min_similarity=args.min_similarity,
                audit_access=args.audit_access,
                access_actor=args.access_actor,
            )
            _emit_report(report, format_search(report), args)
        finally:
            if semantic_index is not None:
                semantic_index.close()
    elif args.command == "trace":
        from atmem.investigate import format_trace, trace_evidence

        semantic_index, embedder = _semantic_search_resources(args, memory)
        try:
            report = trace_evidence(
                memory,
                args.subject,
                args.query,
                session_id=args.session,
                run_id=args.run,
                record_id=args.record,
                event_type=args.event_type,
                since=args.since,
                until=args.until,
                limit=args.limit,
                mode=args.mode,
                semantic_index=semantic_index,
                embedder=embedder,
                min_similarity=args.min_similarity,
                audit_access=args.audit_access,
                access_actor=args.access_actor,
            )
            _emit_report(report, format_trace(report), args)
        finally:
            if semantic_index is not None:
                semantic_index.close()
    elif args.command == "access-log":
        _print(
            {
                "format": "atmem-investigation-access-v1",
                "subject_id": args.subject,
                "verification": memory.store.verify_investigation_access(
                    args.subject
                ),
                "events": memory.store.list_investigation_access(args.subject),
            }
        )
    elif args.command == "forget":
        result = memory.forget(
            args.subject_id,
            selector=args.contains,
            utterance=args.utterance,
            session_id=args.session,
        )
        _print(result)
    elif args.command == "forget-artifact":
        _print(
            memory.forget_artifact(
                args.subject_id,
                args.media_sha256,
                artifact_id=args.artifact_id,
                session_id=args.session,
                turn_id=args.turn,
            )
        )
    elif args.command == "promote":
        _print(
            memory.promote(args.subject_id, args.record_id, session_id=args.session)
        )
    elif args.command == "log-action":
        event_id = memory.log_action(
            args.subject_id,
            args.action_type,
            json.loads(args.payload),
            session_id=args.session,
            turn_id=args.turn,
        )
        _print({"event_id": event_id})
    elif args.command == "consolidate":
        _print(memory.consolidate(args.subject_id))
    elif args.command == "persona":
        _print(memory.build_persona(args.subject_id, max_chars=args.max_chars))
    elif args.command == "context-pack":
        _print(
            memory.build_context_pack(
                args.subject_id,
                args.query,
                session_id=args.session,
                persona_max_chars=args.persona_max_chars,
                recall_max_records=args.recall_max_records,
                recall_max_chars=args.recall_max_chars,
                min_score=args.min_score,
                use_graph=args.graph,
                reference_mode=args.reference_mode,
            )
        )
    elif args.command == "scenes":
        _print(memory.scenes(args.subject_id))
    elif args.command == "propose":
        proposals = json.load(sys.stdin)
        _print(
            memory.propose_facts(
                args.subject_id, proposals, proposer=args.proposer
            )
        )
    elif args.command == "inspect":
        _print(memory.inspect(args.subject_id))
    elif args.command == "audit":
        _print(memory.audit(args.subject_id))
    elif args.command == "checkpoint":
        _print(memory.checkpoint(sink_path=args.sink))
    elif args.command == "verify":
        result = memory.verify(
            args.subject,
            checkpoints_path=args.checkpoints,
            incremental=args.incremental,
        )
        _print(result)
        if not result["valid"]:
            sys.exit(1)


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _restart_running_dashboard_after_upgrade() -> dict[str, object]:
    """Replace a live pre-upgrade dashboard with this CLI's runtime."""

    from atmem.dashboard_daemon import manage_dashboard_daemon

    current = manage_dashboard_daemon("status")
    if not current.get("running"):
        return {
            "format": "atmem-dashboard-upgrade-v1",
            "was_running": False,
            "restarted": False,
        }
    restarted = manage_dashboard_daemon("restart")
    if not restarted.get("running"):
        raise ValueError(
            "the dashboard was running before upgrade but did not restart; "
            "run `atmem dashboard daemon restart`"
        )
    return {
        "format": "atmem-dashboard-upgrade-v1",
        "was_running": True,
        "restarted": True,
        "atmem_version": restarted.get("atmem_version"),
        "url": restarted.get("url"),
    }


def _run_openclaw(args: argparse.Namespace) -> None:
    if args.openclaw_command == "memory":
        from atmem.control import ControlPlaneManager
        from atmem.control.manager import DEFAULT_STATE_PATH
        from atmem.control.openclaw_native import (
            mirror_status,
            search_mirror,
            sync_mirror,
            takeover_status,
            trace_mirror,
        )

        manager = ControlPlaneManager(args.state or DEFAULT_STATE_PATH)
        state = manager.state()
        command = args.openclaw_memory_command
        if command == "sync":
            result = sync_mirror(state)
        elif command == "status":
            result = {
                "format": "atmem-openclaw-memory-status-v1",
                "mode": state.mode.value,
                "mirror": mirror_status(state),
                "takeover": takeover_status(state),
            }
        elif command == "search":
            result = search_mirror(state, args.query, limit=args.limit)
        elif command == "trace":
            result = trace_mirror(state, args.query, limit=args.limit)
        else:
            raise ValueError(f"unknown OpenClaw memory command: {command}")
        if args.json:
            _print(result)
        else:
            _print_openclaw_memory(command, result)
        return
    if args.openclaw_command == "upgrade":
        from atmem.control.manager import DEFAULT_STATE_PATH
        from atmem.openclaw_install import refresh_openclaw_bridge_and_test

        try:
            dashboard = _restart_running_dashboard_after_upgrade()
            result = refresh_openclaw_bridge_and_test(
                state_path=args.state or DEFAULT_STATE_PATH
            )
        except ValueError as exc:
            if args.json:
                _print(
                    {
                        "format": "atmem-openclaw-upgrade-v1",
                        "upgraded": False,
                        "error": str(exc),
                    }
                )
            else:
                print("AtMem OpenClaw upgrade did not complete", file=sys.stderr)
                print(f"\n{exc}", file=sys.stderr)
            raise SystemExit(1) from None
        result["dashboard"] = dashboard
        if args.json:
            _print(result)
        else:
            print("AtMem upgraded the OpenClaw bridge")
            print(
                f"\n  Previous bridge       "
                f"{result.get('previous_bridge_version') or 'unknown'}"
            )
            print(f"  Current bridge        {result['bridge_version']}")
            print(f"  Memory mode           {result['mode']}")
            print(f"  Test flight           {result['test_flight']['verdict']}")
            print(
                "  Dashboard             "
                + ("restarted" if dashboard["restarted"] else "was not running")
            )
        return
    if args.openclaw_command != "install":
        raise ValueError(f"unknown OpenClaw command: {args.openclaw_command}")
    from atmem.openclaw_install import install_openclaw
    from atmem.control.manager import DEFAULT_STATE_PATH, DEFAULT_CONTROL_ROOT

    try:
        def show_progress(step: int, total: int, label: str) -> None:
            width = 20
            filled = min(width, max(0, round(width * step / max(1, total))))
            bar = "#" * filled + "-" * (width - filled)
            print(
                f"[{bar}] {step}/{total}  {label}",
                file=sys.stderr,
                flush=True,
            )

        result = install_openclaw(
            state_path=args.state or DEFAULT_STATE_PATH,
            control_root=args.control_root or DEFAULT_CONTROL_ROOT,
            progress=None if args.json else show_progress,
        )
    except ValueError as exc:
        if args.json:
            _print(
                {
                    "format": "atmem-openclaw-install-v1",
                    "installed": False,
                    "error": str(exc),
                }
            )
        else:
            print("AtMem OpenClaw installation did not complete", file=sys.stderr)
            print(f"\n{exc}", file=sys.stderr)
        raise SystemExit(1) from None
    if args.json:
        _print(result)
        return
    print("AtMem is installed beside OpenClaw")
    print(f"\n  Engine version        {result['engine_version']}")
    print(f"  Engine executable     {result['engine_executable']}")
    print(f"  OpenClaw bridge       {result['plugin_version']}")
    print(
        "  Installation           "
        + (
            "existing shadow verified"
            if result.get("existing_migration_reused")
            else "new shadow created"
        )
    )
    print(
        "  Gateway verification "
        + ("PASSED" if result.get("gateway_verified") else "FAILED")
    )
    print(
        "  Native memory baseline "
        + ("PASSED" if result.get("native_baseline_verified") else "FAILED")
    )
    print(
        "  Baseline files         "
        f"{int(result.get('native_baseline_files') or 0)}"
    )
    print(
        "  Baseline bytes         "
        f"{int(result.get('native_baseline_bytes') or 0):,}"
    )
    print(
        "  Search mirror          "
        + ("PASSED" if result.get("mirror_verified") else "FAILED")
    )
    print("  Control mode            shadow capture")
    print("  Model context changed no")
    print("  Extra provider calls  no")
    print(f"  Control ID              {result['migration_id']}")
    print(f"  Evidence directory    {result['control_dir']}")
    print(
        "\nKeep using OpenClaw normally. AtMem will collect candidate memories "
        "locally and mirror native memory without changing model context."
    )
    print("Next: atmem dashboard")


def _print_openclaw_memory(command: str, result: dict[str, object]) -> None:
    if command == "status":
        mirror = result.get("mirror")
        mirror = mirror if isinstance(mirror, dict) else {}
        takeover = result.get("takeover")
        takeover = takeover if isinstance(takeover, dict) else {}
        print("AtMem OpenClaw memory status")
        print(f"\n  Mode                    {result.get('mode', 'unknown')}")
        print(
            "  Native mirror           "
            + ("synchronized" if mirror.get("synced") else "NOT READY")
        )
        print(f"  Native sources          {int(mirror.get('source_count') or 0)}")
        print(f"  Mirrored records        {int(mirror.get('record_count') or 0)}")
        print(f"  Source bytes            {int(mirror.get('source_bytes') or 0):,}")
        baseline = mirror.get("native_baseline")
        baseline = baseline if isinstance(baseline, dict) else {}
        history = mirror.get("shadow_history")
        history = history if isinstance(history, dict) else {}
        print(
            "  Pre-shadow baseline     "
            + ("PASSED" if baseline.get("snapshot_sha256") else "MISSING")
        )
        if baseline.get("snapshot_sha256"):
            print(
                "  Baseline files          "
                f"{int(baseline.get('file_count') or 0)}"
            )
            print(
                "  Baseline digest         "
                f"{baseline.get('snapshot_sha256')}"
            )
            print(
                "  Observed change states  "
                f"{int(history.get('observed_change_versions') or 0)}"
            )
        print(
            "  Audit verification      "
            + ("PASSED" if mirror.get("audit_verified") else "FAILED")
        )
        print(f"  Mirror database         {mirror.get('mirror_db', 'not created')}")
        print(f"  Manifest                {mirror.get('manifest_sha256', 'none')}")
        print(
            "  Native memory takeover  "
            + ("active" if takeover.get("active") else "shadow only")
        )
        snapshot = takeover.get("native_snapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        if takeover.get("native_snapshot_verified"):
            print("  Complete native snapshot PASSED")
            print(
                "  Snapshot files          "
                f"{int(snapshot.get('file_count') or 0)}"
            )
            print(
                "  Snapshot bytes          "
                f"{int(snapshot.get('total_bytes') or 0):,}"
            )
            print(
                "  Snapshot digest         "
                f"{snapshot.get('snapshot_sha256', 'none')}"
            )
        print(
            "  Cost projection         "
            + str(mirror.get("token_projection") or "not measured").replace("_", " ")
        )
        if not takeover.get("active"):
            print(
                "\nOpenClaw native memory remains authoritative. "
                "AtMem is mirroring and auditing without changing prompts."
            )
        else:
            print(
                "\nAtMem owns supplemental memory recall. The frozen native "
                "snapshot remains available for verified restore."
            )
        return
    if command == "sync":
        print("AtMem OpenClaw mirror synchronized")
        print(f"\n  Sources          {int(result.get('source_count') or 0)}")
        print(f"  Records          {int(result.get('record_count') or 0)}")
        print(f"  Source bytes     {int(result.get('source_bytes') or 0):,}")
        print(f"  Database         {result.get('mirror_db')}")
        print(f"  Manifest         {result.get('manifest_sha256')}")
        return
    if command == "search":
        rows = result.get("records")
        rows = rows if isinstance(rows, list) else []
        print(f"AtMem OpenClaw memory search\n\n  {len(rows)} result(s)")
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            content = str(row.get("content") or "").replace("\n", " ").strip()
            print(f"  {index}. {content}")
            provenance = row.get("openclaw_provenance")
            provenance = provenance if isinstance(provenance, dict) else {}
            source = provenance.get("relative_path") or row.get("source_type")
            lines = (
                f" lines {provenance.get('line_start')}-{provenance.get('line_end')}"
                if provenance.get("line_start")
                else ""
            )
            print(f"     record {row.get('id')} · {source}{lines}")
        return
    if command == "trace":
        from atmem.investigate import format_trace

        print(format_trace(result), end="")
        return


def _print_control(command: str, value: object, *, json_output: bool) -> None:
    if json_output:
        _print(value)
        return
    result = value if isinstance(value, dict) else {}
    if command == "restore":
        restored = result.get("host_restore")
        restored = restored if isinstance(restored, dict) else {}
        verified = bool(restored.get("verified"))
        print("AtMem restore complete")
        print(f"\n  Host                 {_display_host(result.get('host'))}")
        print(
            "  Host configuration   "
            + ("restored" if restored.get("restored") else "not restored")
        )
        print(f"  Verification         {'PASSED' if verified else 'FAILED'}")
        print("  Memory provider      OpenClaw")
        plugin_enabled = restored.get("plugin_enabled")
        if plugin_enabled is True:
            print("  AtMem plugin      enabled (restored pre-migration state)")
        elif plugin_enabled is False:
            print("  AtMem plugin      disabled")
        else:
            print("  AtMem plugin      state unknown")
        takeover_restore = restored.get("takeover")
        takeover_restore = (
            takeover_restore if isinstance(takeover_restore, dict) else {}
        )
        preserved = takeover_restore.get("post_switch_native_preserved")
        if isinstance(preserved, list) and preserved:
            print(f"  Post-switch files    preserved ({len(preserved)})")
        active_export = takeover_restore.get("active_memory_export")
        active_export = active_export if isinstance(active_export, dict) else {}
        exported_count = int(active_export.get("record_count") or 0)
        if exported_count:
            print(f"  Active memories      returned to OpenClaw ({exported_count})")
            print(f"  Native export        {active_export.get('path')}")
        print("  Control evidence       preserved")
        if result.get("migration_id"):
            print(f"  Control ID             {result['migration_id']}")
        if result.get("control_dir"):
            print(f"  Evidence directory   {result['control_dir']}")
        print("\nYour original host configuration has been restored.")
        if plugin_enabled is True:
            print(
                "AtMem itself is still enabled because it was enabled before "
                "this control-plane migration."
            )
        else:
            print("AtMem is not enabled in the restored host configuration.")
        print("Past agent outputs and provider logs are unchanged.")
        return
    if command == "restore-drill":
        print("AtMem restore drill complete")
        print(
            "\n  File restoration      "
            + ("tested" if result.get("files_restoration_tested") else "FAILED")
        )
        print(
            "  Saved configuration   "
            + ("readable" if result.get("saved_config_readable") else "FAILED")
        )
        print("  Live rollback         not performed")
        print(
            "  Verification          "
            + ("PASSED" if result.get("valid") else "FAILED")
        )
        print(f"  Evidence digest       {result.get('evidence_sha256', 'none')}")
        print(f"  Report digest         {result.get('report_sha256', 'none')}")
        return
    titles = {
        "shadow": "AtMem shadowing started",
        "status": "AtMem memory status",
        "activate": "AtMem is active",
        "verify": "AtMem control verification",
    }
    print(titles.get(command, "AtMem memory control plane"))
    _print_control_status_rows(result)
    if command == "verify":
        for row in result.get("checks") or []:
            if isinstance(row, dict):
                print(
                    f"  {str(row.get('status') or 'unknown').upper():4}  "
                    f"{row.get('name')}"
                )
        print(f"\n  Evidence digest       {result.get('evidence_sha256', 'none')}")
        print(f"  Report digest         {result.get('report_sha256', 'none')}")
        return
    if command == "shadow":
        integration = result.get("integration")
        integration = integration if isinstance(integration, dict) else {}
        generic = result.get("host") == "generic"
        print(
            f"  Host integration      "
            f"{'ready' if integration.get('adapter_ready') else 'configured' if integration.get('configured') else 'not configured'}"
        )
        if generic:
            print("\nGeneric shadow mode is active.")
            print("AtMem records capture and flight events but never authorizes context injection.")
        else:
            print("\nOpenClaw memory remains active.")
            print("AtMem is copying, indexing, and auditing it without changing prompts.")
    elif command == "status":
        readiness = result.get("readiness")
        readiness = readiness if isinstance(readiness, dict) else {}
        reasons = readiness.get("reasons")
        if result.get("mode") == "off" and readiness.get("ready_for_active"):
            print(
                "\nReady: the preserved mirror verified. Inspect/search it, "
                "then activate when satisfied."
            )
        elif result.get("mode") == "off":
            print(
                "\nNext: start a new migration with "
                "`atmem control shadow --host openclaw`."
            )
        elif result.get("mode") == "active":
            print(
                "\nAtMem is active. Use `atmem control restore` to return to "
                + ("OpenClaw memory." if result.get("host") == "openclaw" else "shadow mode.")
            )
        elif isinstance(reasons, list) and reasons:
            print(f"\nNext: {reasons[0]}")
        elif readiness.get("ready_for_active"):
            print("\nReady: inspect/search the mirror, then activate when satisfied.")
    elif command == "activate":
        print(
            "\nAtMem now supplies bounded, governed memory context. "
            "Use `atmem control restore` to stop injection and preserve evidence."
        )


def _print_control_status_rows(result: dict[str, object]) -> None:
    mode = str(result.get("mode") or "unknown")
    evidence = result.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    chain = evidence.get("transition_chain")
    chain = chain if isinstance(chain, dict) else {}
    mirror = result.get("mirror")
    mirror = mirror if isinstance(mirror, dict) else {}
    provider = "AtMem" if mode == "active" else _display_host(result.get("host"))
    print(f"\n  Memory provider       {provider}")
    print(f"  Host                  {_display_host(result.get('host'))}")
    print(
        "  Changes agent context "
        + ("yes" if result.get("changes_model_context") else "no")
    )
    print(
        "  Extra provider calls  "
        + ("yes" if result.get("makes_extra_provider_calls") else "no")
    )
    if mirror:
        print(f"  Mirrored files        {int(mirror.get('source_count') or 0)}")
        print(f"  Searchable memories   {int(mirror.get('record_count') or 0)}")
        print(
            "  Mirror verification   "
            + ("PASSED" if mirror.get("audit_verified") else "CHECK REQUIRED")
        )
    if evidence:
        print(
            "  Audit chain           "
            + ("valid" if chain.get("valid") else "CHECK REQUIRED")
        )
    if result.get("migration_id"):
        print(f"  Control ID              {result['migration_id']}")
    drill = result.get("restore_drill")
    drill = drill if isinstance(drill, dict) else {}
    if drill.get("valid"):
        print(f"  File restoration       tested {drill.get('ended_at', 'unknown')}")
        print("  Saved configuration    readable")
        print("  Live rollback          not performed")
    verification = result.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    if verification.get("report_sha256"):
        print(
            "  Last verification      "
            + ("PASSED" if verification.get("valid") else "FAILED")
        )
        print(f"  Verification evidence  {verification.get('evidence_sha256')}")


def _print_operator_result(
    command: str, result: dict[str, object], *, json_output: bool
) -> None:
    if json_output:
        _print(result)
        return
    if command == "agents":
        agents = list(result.get("agents") or [])
        workspaces = list(result.get("workspaces") or [])
        print(f"AtMem agents: {len(agents)} agent(s), {len(workspaces)} workspace(s)")
        by_workspace = {
            row.get("workspace_id"): row for row in workspaces if isinstance(row, dict)
        }
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            scope = by_workspace.get(agent.get("workspace_id"), {})
            members = list(scope.get("agent_ids") or []) if isinstance(scope, dict) else []
            kind = "nested isolated" if scope.get("parent_workspace_id") else "shared" if len(members) > 1 else "isolated"
            print(
                f"  {agent.get('name') or agent.get('agent_id')}  {kind}  "
                f"workspace={agent.get('workspace')}  subject={agent.get('subject_id')}"
            )
        return
    if command == "memory-status":
        print("AtMem memory")
        print(f"  Mode       {result.get('mode')}")
        print(f"  Approved   {result.get('record_count', 0)}")
        print(f"  To review  {result.get('candidate_count', 0)}")
        print(f"  Integrity  {'verified' if result.get('audit_verified') else 'failed'}")
        return
    if command == "memory-reviews":
        rows = list(result.get("records") or [])
        print(f"AtMem memory review queue: {len(rows)} item(s)")
        for row in rows:
            if isinstance(row, dict):
                print(f"  [{row.get('status', 'candidate')}] {row.get('content')}")
                print(f"      {row.get('record_id')} · {row.get('subject_id')}")
        return
    if command == "memory-search":
        rows = list(result.get("records") or [])
        print(f"AtMem memory search: {len(rows)} result(s)")
        for row in rows:
            if isinstance(row, dict):
                print(f"  [{row.get('status', 'active')}] {row.get('content') or row.get('match_excerpt')}")
                print(f"      {row.get('record_id') or row.get('id')}")
        return
    if command == "memory-record":
        record = result.get("record") or {}
        record = record if isinstance(record, dict) else {}
        print(f"AtMem memory {record.get('id')}")
        print(f"  Status   {result.get('status')}")
        print(f"  Content  {record.get('content') or 'purged'}")
        print(f"  Digest   {record.get('content_sha256')}")
        return
    if command == "memory-audit":
        rows = list(result.get("events") or [])
        print(f"AtMem memory audit: {result.get('matched_total', len(rows))} matching event(s)")
        for row in rows:
            if isinstance(row, dict):
                print(f"  {row.get('created_at')}  {row.get('event_type')}  {row.get('record_id') or ''}")
        return
    if command == "memory-review":
        print(f"Memory {result.get('record_id')}: {result.get('decision')}")
        return
    _print(result)


def _display_host(value: object) -> str:
    text = str(value or "unknown")
    return {"openclaw": "OpenClaw", "generic": "Generic runtime"}.get(text, text)


def _add_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        dest="report_format",
        choices=("text", "json"),
        default=None,
        help="Output format (default: text, or inferred from --output extension)",
    )
    parser.add_argument(
        "--output", default=None, help="Write the complete report to this file"
    )


def _add_semantic_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=("lexical", "semantic", "hybrid"),
        default="lexical",
        help="Retrieval mode; AtMem creates a local index automatically",
    )
    parser.add_argument(
        "--embedder",
        choices=("ollama", "openai-compatible", "sentence-transformers", "hashing"),
        default=None,
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--index-path", default=None)
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.2,
        help="Minimum cosine similarity for semantic nominations",
    )


def _add_access_audit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--audit-access",
        action="store_true",
        help="Append a digest-only event to the separate investigation access chain",
    )
    parser.add_argument(
        "--access-actor",
        default="unauthenticated-cli",
        help="Actor asserted by the caller; authenticated hosts should supply identity",
    )


def _semantic_search_resources(
    args: argparse.Namespace, memory: Memory
) -> tuple[object | None, object | None]:
    if args.mode == "lexical":
        return None, None
    from atmem.semantic import SemanticIndex, create_embedder, default_index_path

    index_path = Path(
        args.index_path or default_index_path(memory.store.path)
    ).expanduser()
    if not index_path.exists():
        raise ValueError(
            f"semantic index does not exist: {index_path}; "
            "run `atmem index build` first"
        )
    index = SemanticIndex(index_path, policy=memory.policy)
    epoch = index.active_epoch(args.subject)
    if epoch is None:
        index.close()
        raise ValueError(
            f"no semantic index for {args.subject!r}; run `atmem index build` first"
        )
    from atmem.semantic import inspect_semantic_health

    health = inspect_semantic_health(index, memory, args.subject)
    if health.status.value not in {"healthy", "weak"}:
        index.close()
        raise ValueError(
            f"semantic index is {health.status.value}; "
            "run `atmem semantic status` and rebuild before semantic retrieval"
        )
    identity = epoch["identity"]
    provider = args.embedder or str(identity["provider"])
    if provider == "hashing-diagnostic":
        provider = "hashing"
    model = args.model or str(identity["model"])
    if provider == "hashing":
        model = str(epoch["dimensions"])
    embedder = create_embedder(
        provider,
        model,
        endpoint=args.endpoint or identity.get("endpoint"),
        api_key_env=args.api_key_env,
        model_version=args.model_version or str(identity.get("version", "unverified")),
    )
    return index, embedder


def _run_index(args: argparse.Namespace) -> None:
    from atmem.semantic import SemanticIndex, create_embedder, default_index_path

    memory = Memory(args.path)
    index = SemanticIndex(
        args.index_path or default_index_path(args.path), policy=memory.policy
    )
    try:
        if args.index_command == "status":
            _print(index.status(args.subject))
            return
        if args.index_command == "verify":
            report = index.verify(memory, args.subject)
            _print(report)
            if not report["valid"]:
                raise SystemExit(1)
            return
        if args.index_command == "build":
            model = args.model
            if args.embedder == "ollama" and not model:
                model = "nomic-embed-text"
            embedder = create_embedder(
                args.embedder,
                model,
                endpoint=args.endpoint,
                api_key_env=args.api_key_env,
                model_version=args.model_version,
            )
            report = index.build(
                memory,
                args.subject,
                embedder,
                batch_size=args.batch_size,
            )
            _print(report)
            return
        raise ValueError(f"unknown index command: {args.index_command}")
    finally:
        index.close()
        memory.close()


def _run_semantic(args: argparse.Namespace) -> None:
    from atmem.semantic import (
        HardwareProfile,
        SemanticIndex,
        create_embedder,
        default_index_path,
        evaluate_semantic_health,
        inspect_semantic_health,
        recommend_local_models,
    )

    memory = Memory(args.path, auto_vectors=False)
    index_path = Path(args.index_path or default_index_path(args.path)).expanduser()
    index = None
    try:
        if args.semantic_command == "status" and not index_path.exists():
            health = evaluate_semantic_health(args.subject, active_epoch=None)
            _emit_semantic_health(health.to_dict(), json_output=args.json)
            return
        index = SemanticIndex(index_path, policy=memory.policy)
        if args.semantic_command == "status":
            _emit_semantic_health(
                inspect_semantic_health(index, memory, args.subject).to_dict(),
                json_output=args.json,
            )
            return
        if args.semantic_command == "verify":
            health = inspect_semantic_health(index, memory, args.subject).to_dict()
            _emit_semantic_health(health, json_output=args.json)
            if health["status"] not in {"healthy", "weak"}:
                raise SystemExit(1)
            return

        provider, model = _semantic_provider_selection(args, index)
        if args.semantic_command == "setup":
            consent = _semantic_setup_consent(args, provider, model)
            if not consent:
                memory.log_action(
                    args.subject,
                    "semantic.setup_declined",
                    {"provider": provider, "model": model},
                    actor="cli-operator",
                )
                result = {
                    "format": "atmem-semantic-setup-v1",
                    "status": "cancelled",
                    "provider": provider,
                    "model": model,
                    "fallback": "hashing-diagnostic",
                    "decisions": list(_semantic_decisions(args)),
                    "decision_count": len(_semantic_decisions(args)),
                    "message": "No download or egress occurred; deterministic hashing remains available.",
                }
                _emit_semantic_setup(result, json_output=args.json)
                return
            hardware = HardwareProfile.detect()
            recommendations = recommend_local_models(hardware)
            approval = {
                "provider": provider,
                "model": model,
                "download_approved": bool(args.allow_download),
                "egress_approved": bool(args.allow_egress),
                "configuration_sha256": _semantic_configuration_digest(args, provider, model),
            }
            memory.log_action(
                args.subject,
                "semantic.setup_approved",
                approval,
                actor="cli-operator",
            )
        else:
            hardware = None
            recommendations = []

        embedder = create_embedder(
            provider,
            model,
            endpoint=args.endpoint,
            api_key_env=args.api_key_env,
            model_version=args.model_version,
        )
        built = index.build(
            memory,
            args.subject,
            embedder,
            batch_size=args.batch_size,
        )
        health = inspect_semantic_health(index, memory, args.subject).to_dict()
        if args.semantic_command == "rebuild":
            result = {
                "format": "atmem-semantic-rebuild-v1",
                "build": built,
                "health": health,
            }
            _emit_semantic_setup(result, json_output=args.json)
            return

        records = memory.store.list_records(args.subject, statuses=("active",))
        expected = str(records[0]["id"]) if records else None
        query = args.smoke_query or (
            f"In other words: {records[0]['content']}" if records else ""
        )
        matches = (
            index.search(
                memory,
                args.subject,
                query,
                embedder,
                statuses=("active",),
                limit=3,
                min_similarity=-1.0,
            )
            if query and expected
            else []
        )
        smoke = {
            "query": query,
            "expected_record_id": expected,
            "returned_record_ids": [row["record_id"] for row in matches],
            "passed": expected is not None
            and expected in {str(row["record_id"]) for row in matches},
        }
        result = {
            "format": "atmem-semantic-setup-v1",
            "status": "complete" if smoke["passed"] else "verification_failed",
            "decisions": list(_semantic_decisions(args)),
            "decision_count": len(_semantic_decisions(args)),
            "hardware": hardware.to_dict() if hardware else None,
            "recommendations": recommendations,
            "build": built,
            "health": health,
            "smoke_test": smoke,
        }
        _emit_semantic_setup(result, json_output=args.json)
        if not smoke["passed"]:
            raise SystemExit(1)
    finally:
        if index is not None:
            index.close()
        memory.close()


def _semantic_decisions(args: argparse.Namespace) -> list[str]:
    """Every operator decision the setup flow actually consumed.

    SC-005 bounds the number of decisions, so this must be counted from the
    flow rather than asserted as a constant.
    """

    decisions = getattr(args, "_semantic_decision_log", None)
    if decisions is None:
        decisions = []
        setattr(args, "_semantic_decision_log", decisions)
    return decisions


def _record_semantic_decision(args: argparse.Namespace, name: str) -> None:
    _semantic_decisions(args).append(name)


def _semantic_provider_selection(
    args: argparse.Namespace, index: object
) -> tuple[str, str | None]:
    from atmem.semantic import HardwareProfile, recommend_local_models

    provider = args.provider
    model = args.model
    active = index.active_epoch(args.subject)
    if args.semantic_command == "rebuild" and active is not None:
        identity = active["identity"]
        provider = provider or str(identity["provider"])
        model = model or str(identity["model"])
        if provider == "hashing-diagnostic":
            provider = "hashing"
            model = str(active["dimensions"])
        if args.model_version == "unverified":
            args.model_version = str(identity.get("version", "unverified"))
        args.endpoint = args.endpoint or identity.get("endpoint")
    if provider is None:
        recommendations = recommend_local_models(HardwareProfile.detect())
        if not recommendations:
            raise ValueError(
                "no catalog model fits detected hardware; select --provider and --model manually"
            )
        selected = 0
        if args.semantic_command == "setup" and sys.stdin.isatty():
            print("Recommended local embedding models:")
            for position, recommendation in enumerate(recommendations, start=1):
                print(
                    f"  {position}. {recommendation['model']} · "
                    f"~{recommendation['approximate_download_mib']} MiB · "
                    f"{recommendation['caveat']}"
                )
            answer = input("Choose a model [1], or use --provider/--model manually: ").strip()
            _record_semantic_decision(args, "model_selection")
            if answer:
                try:
                    selected = int(answer) - 1
                except ValueError as exc:
                    raise ValueError("model choice must be a listed number") from exc
                if not 0 <= selected < len(recommendations):
                    raise ValueError("model choice is outside the recommendation list")
        provider = str(recommendations[selected]["provider"])
        model = model or str(recommendations[selected]["model"])
    if provider == "ollama" and not model:
        model = "nomic-embed-text"
    return provider, model


def _semantic_setup_consent(
    args: argparse.Namespace, provider: str, model: str | None
) -> bool:
    if provider == "sentence-transformers" and not args.allow_download:
        if not sys.stdin.isatty():
            return False
        answer = input(
            f"Allow the local model runtime to download {model!r} if absent? [y/N] "
        )
        _record_semantic_decision(args, "download_consent")
        if answer.strip().casefold() not in {"y", "yes"}:
            return False
        args.allow_download = True
    elif provider == "sentence-transformers":
        _record_semantic_decision(args, "download_consent_flag")
    if provider in {"openai-compatible", "ollama"} and not args.allow_egress:
        if not sys.stdin.isatty():
            return False
        target = (
            "the configured HTTPS endpoint"
            if provider == "openai-compatible"
            else "the configured Ollama endpoint (which may pull the model)"
        )
        answer = input(f"Allow embedding requests to {target}? [y/N] ")
        _record_semantic_decision(args, "egress_consent")
        if answer.strip().casefold() not in {"y", "yes"}:
            return False
        args.allow_egress = True
    elif provider in {"openai-compatible", "ollama"}:
        _record_semantic_decision(args, "egress_consent_flag")
    return True


def _semantic_configuration_digest(
    args: argparse.Namespace, provider: str, model: str | None
) -> str:
    from atmem.core.canonical import canonical_json, sha256_hex

    safe = {
        "provider": provider,
        "model": model,
        "model_version": args.model_version,
        "endpoint": args.endpoint,
        "api_key_environment_variable": args.api_key_env,
    }
    return f"sha256:{sha256_hex(canonical_json(safe))}"


def _run_task(args: argparse.Namespace) -> None:
    """Drive governed task state from a terminal.

    Process behaviour is part of the contract: exit 0 for a successful read,
    an accepted action, or `no_change`; exit 1 for a rejected, conflicting,
    unavailable, or integrity outcome; exit 2 for usage errors. In `--json`
    mode exactly one document reaches stdout and every diagnostic goes to
    stderr, so a script can parse stdout unconditionally.
    """
    from atmem.contracts import AuthorityScope
    from atmem.task_state.enablement import ScopeEnablement
    from atmem.task_state.governance import CapabilityDenied
    from atmem.task_state.service import TaskStateError, TaskStateService

    if args.task_command == "profile":
        _run_task_profile(args)
        return

    memory = Memory(args.path, auto_vectors=False)
    try:
        scope = AuthorityScope(args.subject, args.agent, args.workspace)
        enablement = ScopeEnablement(memory.store)
        service = TaskStateService(memory.store)

        if args.task_command in {"enable", "disable"}:
            mode = (
                enablement.enable(scope, actor="cli-operator")
                if args.task_command == "enable"
                else enablement.disable(scope, actor="cli-operator")
            )
            _emit_task(
                {**mode.to_dict(), "scope": scope.to_dict()},
                json_output=args.json,
                human=lambda value: [
                    f"Governed task state is {value['mode']} for this scope.",
                    "Next: atmem task start "
                    f"{args.path} --task-id TASK --goal GOAL --subject "
                    f"{args.subject} --agent {args.agent} --workspace "
                    f"{args.workspace} --actor YOU"
                    if value["enabled"]
                    else "Next: atmem task enable "
                    f"{args.path} --subject {args.subject} --agent {args.agent} "
                    f"--workspace {args.workspace}",
                ],
            )
            return

        mode = enablement.mode(scope)
        if not mode.enabled:
            # Fail closed and say exactly how to proceed, rather than acting.
            _emit_task(
                {
                    "format": "atmem-task-unavailable-v1",
                    "reason_code": "task_state_disabled",
                    "mode": mode.label,
                    "scope": scope.to_dict(),
                    "message": "Governed task state is disabled for this scope.",
                },
                json_output=args.json,
                human=lambda value: [
                    "Governed task state is disabled for this scope.",
                    f"Next: atmem task enable {args.path} --subject {args.subject} "
                    f"--agent {args.agent} --workspace {args.workspace}",
                ],
                stream=sys.stderr,
            )
            raise SystemExit(1)

        _require_task_confirmation(args)

        try:
            _dispatch_task_command(args, scope=scope, service=service, mode=mode)
        except CapabilityDenied as exc:
            _emit_task_failure(
                args, reason_code=exc.reason_code, message=str(exc)
            )
        except TaskStateError as exc:
            _emit_task_failure(
                args, reason_code=exc.reason_code, message=str(exc),
                guard=getattr(exc, "guard", None),
            )
    finally:
        memory.close()


def _dispatch_task_command(
    args: argparse.Namespace, *, scope: Any, service: Any, mode: Any
) -> None:
    from atmem.core.canonical import sha256_hex
    from atmem.contracts.task_state import (
        ActorRole,
        Assurance,
        ItemStatus,
        OperationKind,
        TaskItem,
        TaskOperation,
        TaskStartRequest,
        TaskStateProposal,
    )
    from atmem.task_state.observability import TaskObservability
    from atmem.task_state.provenance import ProvenanceResolver

    command = args.task_command

    if command == "start":
        items = tuple(
            TaskItem(
                item_id=identifier, kind="step", title=title,
                required=required,
            )
            # Required work is listed first: it is what completion waits on.
            for required, pairs in (
                (True, args.required_item), (False, args.item)
            )
            for identifier, title in (_task_pair(row) for row in pairs)
        )
        view = service.start(
            TaskStartRequest(
                task_id=args.task_id,
                scope=scope,
                profile_id=args.profile.split("-")[0],
                profile_version=args.profile,
                goal=args.goal,
                actor=args.actor,
                actor_role=ActorRole.OPERATOR,
                idempotency_key=f"cli-start:{args.task_id}",
                constraints=tuple(args.constraint),
                sources_to_inspect=tuple(args.source),
                continues_task_id=args.continues,
            ),
            items=items,
        )
        _emit_task(view.to_dict(), json_output=args.json, human=_task_human_view)
        return

    if command == "list":
        listing = service.list(
            scope,
            lifecycles=tuple(args.lifecycle) or None,
            cursor=args.cursor,
            limit=args.limit,
        )
        _emit_task(listing, json_output=args.json, human=_task_human_list)
        return

    if command == "show":
        view = service.get(scope, args.task_id)
        _emit_task(view.to_dict(), json_output=args.json, human=_task_human_view)
        return

    if command == "timeline":
        timeline = service.timeline(scope, args.task_id)
        _emit_task(timeline, json_output=args.json, human=_task_human_timeline)
        return

    if command == "health":
        snapshot = TaskObservability(service.store, clock=service.clock).snapshot(scope)
        _emit_task(snapshot, json_output=args.json, human=_task_human_health)
        return

    if command == "verify":
        snapshot = TaskObservability(service.store, clock=service.clock).snapshot(scope)
        integrity = snapshot["integrity"]
        _emit_task(
            {
                "format": "atmem-task-integrity-v1",
                "scope": scope.to_dict(),
                **integrity,
            },
            json_output=args.json,
            human=lambda value: [
                f"Revision-chain integrity: {'valid' if value['valid'] else 'FAILED'}",
                f"Tasks checked: {value['checked_tasks']}",
                *[f"  problem: {row}" for row in value["problems"]],
            ],
        )
        if not integrity["valid"]:
            raise SystemExit(1)
        return

    if command == "provenance":
        result = ProvenanceResolver(service.store).resolve(
            scope, args.task_id,
            target_kind=args.target_kind, target_id=args.target_id,
        )
        _emit_task(result, json_output=args.json, human=_task_human_provenance)
        if not result["found"]:
            raise SystemExit(1)
        return

    if command in {"pause", "resume", "complete", "cancel"}:
        _check_expected_revision(args, service, scope)
        view = getattr(service, command)(
            scope, args.task_id, actor=args.actor,
            actor_role=ActorRole.OPERATOR,
            reason=args.reason or command,
        )
        _emit_task(view.to_dict(), json_output=args.json, human=_task_human_view)
        return

    if command in {"bind", "unbind", "bindings"}:
        from atmem.contracts.task_state import HostSessionIdentity
        from atmem.task_state.binding import BindingError, SessionBindingService

        bindings = SessionBindingService(service.store, service.clock)

        if command == "bindings":
            rows = bindings.list(
                scope,
                task_id=getattr(args, "task_id", None),
                include_revoked=args.include_revoked,
            )
            _emit_task(
                {"format": "atmem-task-binding-list-v1", "count": len(rows),
                 "bindings": rows},
                json_output=args.json,
                human=lambda value: _task_human_bindings(value, args),
            )
            return

        if command == "unbind":
            try:
                bindings.revoke(
                    scope, binding_id=args.binding_id, actor=args.actor,
                    reason=args.reason,
                )
            except BindingError as exc:
                _fail_task(args, exc.reason_code, str(exc))
                return
            _emit_task(
                {"format": "atmem-task-binding-revoked-v1",
                 "binding_id": args.binding_id},
                json_output=args.json,
                human=lambda value: [
                    "Binding revoked. This conversation no longer resolves to a task.",
                    f"Next: atmem task bindings {args.path} --subject {args.subject} "
                    f"--agent {args.agent} --workspace {args.workspace}",
                ],
            )
            return

        # bind: the task must exist and be eligible before a conversation is
        # pointed at it, so a binding never names something unreachable.
        try:
            view = service.get(scope, args.task_id)
        except TaskStateError as exc:
            _fail_task(args, exc.reason_code, str(exc))
            return
        try:
            identity = HostSessionIdentity(
                args.host_type, args.session_key, args.session_epoch
            )
        except ValueError as exc:
            _fail_task(args, "session_identity_required", str(exc))
            return
        try:
            binding = bindings.register(
                scope, identity, task_id=args.task_id, actor=args.actor,
                reason=args.reason, source=args.source, profile=view.profile,
            )
        except BindingError as exc:
            _fail_task(args, exc.reason_code, str(exc))
            return
        _emit_task(
            binding.to_dict(),
            json_output=args.json,
            human=lambda value: [
                f"Bound this conversation to {value['task_id']}.",
                f"Binding ID: {value['binding_id']}",
                "That conversation now receives this task's state, and may "
                "report progress against it and no other task.",
                f"Next: atmem task show {args.path} {value['task_id']} "
                f"--subject {args.subject} --agent {args.agent} "
                f"--workspace {args.workspace}",
            ],
        )
        return

    if command == "correct":
        _check_expected_revision(args, service, scope)
        # One identity for one correction: the same request replays, a
        # different one gets its own proposal rather than colliding.
        key = (
            f"cli-correct:{args.task_id}:{args.item}:{args.status}"
            f":{args.expected_revision}:{args.reason}"
        )
        decision = service.correct(
            scope, args.task_id,
            TaskStateProposal(
                proposal_id=f"cli-correction-{sha256_hex(key)[:32]}",
                task_id=args.task_id,
                scope=scope,
                base_revision=args.expected_revision,
                idempotency_key=key,
                actor=args.actor,
                actor_role=ActorRole.OPERATOR,
                assurance=Assurance.OPERATOR_CONFIRMED,
                operations=(
                    TaskOperation(
                        kind=OperationKind.SET_ITEM_STATUS,
                        item_id=args.item,
                        status=ItemStatus(args.status),
                        reason=args.reason,
                    ),
                ),
                reason=args.reason,
            ),
            reason=args.reason,
        )
        _emit_task(
            decision.to_dict(), json_output=args.json, human=_task_human_decision
        )
        if decision.outcome.value in {"rejected", "conflict"}:
            raise SystemExit(1)
        return

    if command == "forget":
        receipt = service.forget(
            scope, args.task_id, actor=args.actor,
            actor_role=ActorRole.ADMINISTRATOR,
        )
        _emit_task(
            receipt,
            json_output=args.json,
            human=lambda value: [
                f"Deleted task {value['task_id']} and everything derived from it.",
                f"Revisions removed: {value['revisions_removed']}",
                f"Goal digest retained for the receipt: {value['goal_sha256']}",
            ],
        )
        return


def _run_task_profile(args: argparse.Namespace) -> None:
    """Inspect and register versioned profiles. Registration enables nothing."""
    import json as _json

    from atmem.task_state.profiles import ProfileRegistry

    if args.profile_command is None:
        raise SystemExit(2)
    memory = Memory(args.path, auto_vectors=False)
    try:
        registry = ProfileRegistry(memory.store)
        if args.profile_command == "list":
            profiles = registry.list_profiles()
            _emit_task(
                {
                    "format": "atmem-task-profile-list-v1",
                    "count": len(profiles),
                    "profiles": [
                        {
                            "version": row.version,
                            "profile_id": row.profile_id,
                            "phases": list(row.phases),
                            "digest": row.profile_digest(),
                        }
                        for row in profiles
                    ],
                },
                json_output=args.json,
                human=lambda value: [
                    f"Known task profiles: {value['count']}",
                    *[
                        f"  {row['version']}  phases: {', '.join(row['phases'])}"
                        for row in value["profiles"]
                    ],
                ],
            )
            return

        if args.profile_command == "show":
            profile = registry.get(args.version)
            if profile is None:
                _emit_task_failure(
                    args, reason_code="task_not_eligible",
                    message=f"unknown profile version: {args.version}",
                )
                return
            _emit_task(
                {**profile.to_dict(), "digest": profile.profile_digest()},
                json_output=args.json,
                human=lambda value: [
                    f"Profile {value['version']} ({value['profile_id']})",
                    f"Phases: {', '.join(value['phases'])}",
                    f"Digest: {value['digest']}",
                    value.get("description") or "",
                ],
            )
            return

        if args.profile_command == "register":
            _require_task_confirmation(args)
            payload = _json.loads(Path(args.file).expanduser().read_text())
            result = registry.register(
                payload, actor=args.actor, dry_run=args.dry_run
            )
            _emit_task(
                result.to_dict(),
                json_output=args.json,
                human=lambda value: [
                    (
                        f"Registered profile {value['version']}."
                        if value["registered"]
                        else f"Profile {value['version']} was not registered."
                    ),
                    "Reasons: " + ", ".join(value["reason_codes"]),
                    "Registration does not enable a profile or change any task.",
                ],
            )
            if not result.registered and not args.dry_run:
                raise SystemExit(1)
            return
    finally:
        memory.close()


def _task_pair(value: str) -> tuple[str, str]:
    identifier, separator, title = str(value).partition("=")
    if not separator or not identifier.strip() or not title.strip():
        raise SystemExit(2)
    return identifier.strip(), title.strip()


def _check_expected_revision(args: argparse.Namespace, service: Any, scope: Any) -> None:
    """Refuse a mutation aimed at a revision that has already moved on."""
    expected = getattr(args, "expected_revision", None)
    if expected is None:
        return
    current = service.get(scope, args.task_id).state.revision
    if int(expected) != current:
        _emit_task_failure(
            args,
            reason_code="stale_base_revision",
            message=(
                f"This task is at revision {current}, not {expected}. "
                "Re-read it and submit a fresh request."
            ),
        )


def _task_human_bindings(value: dict[str, Any], args: argparse.Namespace) -> list[str]:
    rows = value.get("bindings") or []
    if not rows:
        return [
            "No conversation bindings in this scope.",
            f"Next: atmem task bind {args.path} TASK --subject {args.subject} "
            f"--agent {args.agent} --workspace {args.workspace} --actor YOU "
            "--reason WHY --host-type HOST --session-key KEY --session-epoch EPOCH",
        ]
    lines = [f"Conversation bindings: {len(rows)}"]
    for row in rows:
        state = "revoked" if row.get("revoked_at_utc") else "active"
        lines.append(
            f"  {row['host_type']}:{row['session_key']} -> {row['task_id']}  [{state}]"
        )
        lines.append(f"    Binding ID: {row['binding_id']}")
    return lines


def _fail_task(args: argparse.Namespace, reason_code: str, message: str) -> None:
    """One refusal shape for both output modes, with exit 1 per FR-040."""
    _emit_task(
        {
            "format": "atmem-task-unavailable-v1",
            "reason_code": reason_code,
            "message": message,
        },
        json_output=args.json,
        human=lambda value: [f"{value['message']} ({value['reason_code']})"],
        stream=sys.stderr,
    )
    raise SystemExit(1)


def _require_task_confirmation(args: argparse.Namespace) -> None:
    """Privileged mutations need `--yes` when nobody is at the terminal."""
    # Binding decides which conversation may write to a task, so registering or
    # revoking one carries the same weight as correcting state.
    privileged = {"cancel", "correct", "forget", "bind", "unbind"}
    command = getattr(args, "task_command", "")
    if command == "profile" and getattr(args, "profile_command", "") == "register":
        privileged = {"profile"}
        command = "profile"
    if command not in privileged:
        return
    if getattr(args, "yes", False):
        return
    if not sys.stdin.isatty():
        # Fail closed rather than prompting into a pipe.
        print(
            f"Refusing to {command} without confirmation. Re-run with --yes.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    answer = input(f"Confirm {command}? This cannot be undone. [y/N] ")
    if answer.strip().lower() not in {"y", "yes"}:
        raise SystemExit(2)


def _emit_task(
    value: dict[str, Any],
    *,
    json_output: bool,
    human: Any,
    stream: Any = None,
) -> None:
    # In JSON mode the single document always goes to stdout, including for a
    # failure, so a script can parse stdout unconditionally. Only human-mode
    # diagnostics are routed to stderr.
    if json_output:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    target = stream or sys.stdout
    for line in human(value):
        if line:
            print(line, file=target)


def _emit_task_failure(
    args: argparse.Namespace,
    *,
    reason_code: str,
    message: str,
    guard: Any = None,
) -> None:
    """One failure shape for both modes, then exit 1."""
    payload = {
        "format": "atmem-task-failure-v1",
        "outcome": "rejected",
        "reason_code": reason_code,
        "message": message,
    }
    if guard is not None:
        payload["guard"] = guard.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{message} ({reason_code})", file=sys.stderr)
        if guard is not None and guard.blocking_item_ids:
            print(
                "Blocked by: " + ", ".join(guard.blocking_item_ids), file=sys.stderr
            )
    raise SystemExit(1)


def _task_human_view(value: dict[str, Any]) -> list[str]:
    summary = value["summary"]
    lines = [
        f"{summary['goal']}",
        f"State: {value['lifecycle']} · phase {summary['phase']} · "
        f"revision {value['revision']}",
        f"Progress: {summary['completed_items']} completed, "
        f"{len(summary['remaining_items'])} remaining, "
        f"{len(summary['blocked_items'])} blocked",
    ]
    if summary["blocked_items"]:
        lines.append("Blocked: " + ", ".join(summary["blocked_items"]))
    if summary["unsatisfied_constraints"]:
        lines.append(
            "Unsatisfied constraints: "
            + ", ".join(summary["unsatisfied_constraints"])
        )
    lines.append(
        "Completion allowed: "
        + ("yes" if summary["completion_allowed"] else "no")
    )
    if summary["completion_blockers"]:
        lines.append("Blocked by: " + ", ".join(summary["completion_blockers"]))
    terminal = value["lifecycle"] in {"completed", "cancelled", "expired"}
    if terminal:
        # Terminal work has no next step. Continuing it means a new task.
        lines.append(
            f"This task is {value['lifecycle']}"
            + (
                f" ({value['terminal_reason']})"
                if value.get("terminal_reason")
                else ""
            )
            + " and cannot be changed."
        )
        lines.append("Next: atmem task start ... --continues " + value["task_id"])
    elif summary["ready_items"]:
        lines.append("Next eligible work: " + ", ".join(summary["ready_items"]))
        lines.append(f"Next: work item {summary['ready_items'][0]}")
    elif summary["completion_allowed"] and value["lifecycle"] == "open":
        lines.append("Next: atmem task complete ... --actor YOU")
    lines.append(f"Task ID: {value['task_id']}")
    return lines


def _task_human_list(value: dict[str, Any]) -> list[str]:
    lines = [f"Governed tasks: {value['count']}"]
    for row in value["tasks"]:
        lines.append(
            f"  {row['goal']}  [{row['lifecycle']}, revision {row['revision']}]"
        )
        lines.append(f"    {row['task_id']}")
    if value.get("next_cursor"):
        lines.append(f"Next: re-run with --cursor {value['next_cursor']}")
    elif not value["tasks"]:
        lines.append("Next: atmem task start ... to begin one")
    return lines


def _task_human_timeline(value: dict[str, Any]) -> list[str]:
    lines = [f"Timeline for {value['task_id']}"]
    for row in value["steps"]:
        lines.append(
            f"  {row['recorded_at_utc']}  {row['step_kind']}  {row['outcome']}"
            + (
                f"  ({', '.join(row['reason_codes'])})"
                if row["reason_codes"]
                else ""
            )
        )
    for row in value["deliveries"]:
        lines.append(
            f"  {row['prepared_at_utc']}  context {row['disposition']}"
            + (
                f"  ({', '.join(row['reason_codes'])})"
                if row["reason_codes"]
                else ""
            )
        )
    return lines


def _task_human_health(value: dict[str, Any]) -> list[str]:
    tasks = value["tasks"]
    transitions = value["transitions"]
    lines = [
        f"Tasks: {tasks['total']} total, {tasks['open_or_paused']} open or paused",
        "By lifecycle: "
        + ", ".join(f"{name} {count}" for name, count in tasks["by_lifecycle"].items()),
        "Decisions: "
        + ", ".join(
            f"{name} {count}" for name, count in transitions["by_outcome"].items()
        ),
        f"Stale-revision conflicts: {transitions['stale_revision_conflicts']}",
        f"Context prepared/exposed/withheld: {value['context']['prepared']}/"
        f"{value['context']['exposed']}/{value['context']['withheld']}",
        f"Integrity: {'valid' if value['integrity']['valid'] else 'FAILED'}",
    ]
    if value["overdue_tasks"]:
        lines.append(
            "Overdue: "
            + ", ".join(row["task_id"] for row in value["overdue_tasks"])
        )
        lines.append("Next: atmem task show PATH TASK_ID ... to inspect one")
    return lines


def _task_human_provenance(value: dict[str, Any]) -> list[str]:
    if not value["found"]:
        return ["No provenance is available for this selection."]
    lines = [f"{value['target_kind']} {value['target_id']} on {value['task_id']}:"]
    for row in value["history"]:
        lines.append(f"  revision {row['revision']}: {row['summary']}")
        for evidence in row["evidence"]:
            lines.append(
                f"    evidence: {evidence['kind']} {evidence['reference_id']}"
            )
    for row in value["deliveries"]:
        lines.append(
            f"  delivered at revision {row['revision']}: {row['disposition']}"
            f" (exposed: {'yes' if row['exposed'] else 'no'})"
        )
    return lines


def _task_human_decision(value: dict[str, Any]) -> list[str]:
    lines = [
        f"Outcome: {value['outcome']}",
        "Reasons: " + ", ".join(value["reason_codes"]),
    ]
    if value.get("resulting_revision"):
        lines.append(f"Revision: {value['resulting_revision']}")
    for guard in value.get("guards") or ():
        lines.append(f"Guard: {guard['message']}")
    if value["outcome"] == "conflict":
        lines.append("Next: re-read the task and submit a fresh request")
    return lines


def _run_proposals(args: argparse.Namespace) -> None:
    """Drive the same review service the dashboard uses, from a terminal."""
    from atmem.extract.review import ReviewService

    memory = Memory(args.path, auto_vectors=False)
    try:
        service = ReviewService(memory)
        if args.proposals_command == "queue":
            queue = service.queue(args.subject, limit=args.limit)
            _emit_proposal_queue(queue, json_output=args.json)
            return
        if args.proposals_command == "show":
            _emit_proposal(service.inspect(args.proposal_id), json_output=args.json)
            return
        if args.proposals_command == "lineage":
            lineage = memory.memory_lineage(args.subject_id, args.record_id)
            if args.json:
                _print({"format": "atmem-memory-lineage-v1", "lineage": lineage})
                return
            if not lineage:
                print("No lineage is recorded for this selection.")
                return
            for row in lineage:
                print(
                    f"{row['predecessor_record_id']} --{row['relation']}--> "
                    f"{row['successor_record_id']}  ({row['created_at']})"
                )
            return
        if args.proposals_command == "decide":
            result = service.decide(
                args.proposal_id,
                args.decision,
                actor=args.actor,
                reason=args.reason,
                edited_fact=args.fact,
                session_id=args.session,
            )
            _emit_proposal(result, json_output=args.json)
            if result["review_state"] == "stale":
                # Nothing was committed: the memory this proposal targeted
                # changed while it waited, so the operator must look again.
                raise SystemExit(1)
            return
    finally:
        memory.close()


def _emit_proposal_queue(value: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _print(value)
        return
    rows = value.get("proposals") or []
    print(f"Proposals awaiting review: {len(rows)}")
    for row in rows:
        print(
            f"  {row['proposal_id']}  {row['action']}  {row['memory_class']}  "
            f"confidence {row['confidence']:.2f}"
        )
        print(f"    proposed fact: {row.get('fact') or '(no fact)'}")
        print("    reasons: " + ", ".join(row.get("reason_codes") or ["none"]))
    if rows:
        print("Decide with: atmem proposals decide PATH PROPOSAL_ID DECISION --actor YOU")


def _emit_proposal(value: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _print(value)
        return
    print(f"Proposal: {value['proposal_id']}")
    print(f"State: {value['review_state']}")
    print(f"Action: {value['action']} ({value['memory_class']})")
    print(f"Confidence: {value['confidence']:.2f}")
    # The proposed text, not necessarily what was committed: an
    # edit-and-approve stores the reviewer's wording instead.
    print(f"Proposed fact: {value.get('fact') or '(no fact)'}")
    print("Reasons: " + ", ".join(value.get("reason_codes") or ["none"]))
    for item in value.get("evidence") or []:
        print(
            f"Evidence: {item['source_id']} "
            f"[{item['start_offset']}:{item['end_offset']}] {item['excerpt_sha256']}"
        )
    if value.get("affected_record_ids"):
        print("Affects: " + ", ".join(value["affected_record_ids"]))
    if value.get("record_ids"):
        print("Committed records: " + ", ".join(value["record_ids"]))
    if value.get("superseded_record_ids"):
        print("Superseded records: " + ", ".join(value["superseded_record_ids"]))
    if value.get("allowed_decisions"):
        print("Allowed decisions: " + ", ".join(value["allowed_decisions"]))
    for review in value.get("reviews") or []:
        print(
            f"Decision: {review['decision']} by {review['actor']} "
            f"at {review['decided_at']} — {review['reason'] or 'no reason given'}"
        )


def _emit_semantic_health(value: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _print(value)
        return
    manifest = value.get("manifest") or {}
    print(f"Semantic index: {value['status']}")
    print(f"Subject: {value['subject_id']}")
    print("Reasons: " + ", ".join(value.get("reasons") or ["none recorded"]))
    if manifest:
        print(
            "Model: "
            f"{manifest.get('provider')}/{manifest.get('model')} "
            f"({manifest.get('dimensions')} dimensions)"
        )
        print(f"Epoch: {manifest.get('epoch_id')}")
        print(f"Source digest: {manifest.get('source_sha256')}")
        print(f"Record coverage: {manifest.get('record_count')} records")
    print("Next actions: " + ", ".join(value.get("actions") or ["none"]))


def _emit_semantic_setup(value: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _print(value)
        return
    print(f"Semantic operation: {value.get('status', 'complete')}")
    if value.get("message"):
        print(value["message"])
    health = value.get("health") or {}
    if health:
        print(f"Health: {health.get('status')}")
    recommendations = value.get("recommendations") or []
    if recommendations:
        print("Compatible local models:")
        for row in recommendations:
            print(
                f"  {row['model']} · ~{row['approximate_download_mib']} MiB · "
                f"{row['caveat']}"
            )
    smoke = value.get("smoke_test") or {}
    if smoke:
        print("Paraphrase smoke test: " + ("passed" if smoke.get("passed") else "failed"))


def _emit_report(value: object, text: str, args: argparse.Namespace) -> None:
    output_path = Path(args.output).expanduser() if args.output else None
    report_format = args.report_format
    if report_format is None:
        report_format = "json" if output_path and output_path.suffix.lower() == ".json" else "text"
    rendered = (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
        if report_format == "json"
        else text
    )
    if output_path is None:
        sys.stdout.write(rendered)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


def _print_cli_welcome(parser: argparse.ArgumentParser) -> None:
    del parser
    print("AtMem — governed memory and agent oversight\n")
    print("What do you want to do?\n")
    print("  1. Set up memory intelligence")
    print("     atmem atbot setup\n")
    print("  2. Connect OpenClaw")
    print("     atmem openclaw install\n")
    print("  3. Connect another agent framework")
    print("     atmem control shadow --host generic --memory-db ~/.atmem/memories.db\n")
    print("  4. Open the dashboard")
    print("     atmem dashboard\n")
    print("  5. Check AtBot and its configured model")
    print("     atmem atbot doctor\n")
    print("AtMem starts safely: no memory injection is enabled until you explicitly activate it.")
    print("Run `atmem --help` for every command or `atmem atbot` for provider examples.")


def _run_atbot(args: argparse.Namespace) -> None:
    from atmem.control.atbot_service import AtBotServiceManager, provider_profiles

    manager = AtBotServiceManager()
    command = args.atbot_command
    try:
        if command == "install":
            result = manager.install(force=bool(args.force))
        elif command == "setup":
            result = _interactive_atbot_setup(manager)
        elif command == "providers":
            result = {"format": "atmem-atbot-provider-profiles-v1", "providers": provider_profiles()}
        elif command == "configure":
            result = manager.configure(
                profile=args.provider,
                model=args.model,
                endpoint=args.endpoint,
                provider_kind=args.provider_kind,
                api_key_env=args.api_key_env,
                remote_egress_allowed=(True if args.remote_egress_allowed else None),
                force=bool(args.force),
            )
        elif command == "start":
            result = manager.start()
        elif command == "stop":
            result = manager.stop()
        elif command == "restart":
            manager.stop()
            result = manager.start()
        elif command == "status":
            result = manager.status()
        elif command == "doctor":
            result = manager.doctor()
        else:  # pragma: no cover - argparse owns the command set
            raise ValueError(f"unknown AtBot command: {command}")
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    if command in {"configure", "setup"} and result.get("configured"):
        print(f"AtBot configured: {result['config_path']}")
        provider = result["config"]["providers"][0]
        print(f"Provider: {result['profile']} · model {provider['model']}")
        for action in result.get("setup_actions") or []:
            print(action)
    elif command == "providers":
        for name, value in result["providers"].items():
            key = value.get("api_key_env") or "no API key"
            print(f"{name}: {value['label']} · {value.get('model') or 'model required'} · {key}")
    elif command == "install":
        print(f"AtBot {result['version']} installed: {result['executable']}")
    else:
        state = "ready" if result.get("available") else "safe AtMem fallback"
        print(f"AtBot intelligence: {state}")
        if result.get("installed_version"):
            print(f"Runtime: {result['installed_version']} (pinned {result['pinned_version']})")
        for action in result.get("setup_actions") or []:
            print(action)


def _run_delegated(args: argparse.Namespace) -> None:
    from atmem.delegated import (
        DelegatedConfigStore,
        DelegatedContextService,
        DelegatedRegistration,
    )

    config = DelegatedConfigStore()
    service = DelegatedContextService(config)
    command = args.delegated_command
    try:
        if command == "register":
            key_path = Path(args.public_key_file).expanduser()
            if key_path.is_symlink() or not key_path.is_file():
                raise ValueError("public key file must be a regular, non-symlink file")
            public_key = key_path.read_text(encoding="utf-8").strip()
            result = config.register(
                DelegatedRegistration(
                    provider_id=args.provider_id,
                    provider_version=args.provider_version,
                    provider_instance_id=args.instance_id,
                    key_id=args.key_id,
                    public_key_base64=public_key,
                    endpoint=args.endpoint,
                    workspace_ids=tuple(args.workspace),
                    agent_ids=tuple(args.agent),
                    user_ids=tuple(args.user),
                    timeout_ms=args.timeout_ms,
                    max_context_bytes=args.max_context_bytes,
                    enabled=False,
                    native_fallback_on_failure=bool(args.native_fallback),
                ),
                replace=bool(args.replace),
            )
        elif command in {"enable", "disable"}:
            result = config.set_enabled(args.registration_id, command == "enable")
        elif command == "remove":
            current = next(
                (row for row in config.registrations() if row.registration_id == args.registration_id),
                None,
            )
            if current is None:
                raise ValueError("delegated provider registration was not found")
            if current.enabled:
                raise ValueError("disable the delegated provider before removing it")
            if not args.yes:
                raise ValueError("removal requires --yes")
            result = {"removed": config.remove(args.registration_id), "registration_id": args.registration_id}
        elif command == "status":
            result = service.status()
        elif command == "doctor":
            result = service.doctor()
        elif command == "self-test":
            result = service.self_test()
        else:  # pragma: no cover
            raise ValueError(f"unknown delegated command: {command}")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    if command == "register":
        print(f"Registered {result['registration_id']} (disabled).")
        print(f"Enable explicitly: atmem delegated enable {result['registration_id']}")
    elif command in {"enable", "disable"}:
        authority = "delegated" if result["enabled"] else "native AtMem"
        print(f"Context authority for this scope: {authority}")
    elif command == "remove":
        print(f"Removed {result['registration_id']}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))


def _run_provider(args: argparse.Namespace) -> None:
    from atmem.provider_adapters import lifecycle

    command = args.provider_command
    try:
        if command == "init":
            result = lifecycle.initialize(
                instance=args.instance, kind=args.kind, port=args.port,
                factory=args.factory, mode=args.mode, provider_id=args.provider_id,
                provider_version=args.provider_version, egress=args.egress,
            )
        elif command == "serve":
            from atmem.provider_adapters.server import serve

            _, config = lifecycle.load_config(args.instance)
            serve(lifecycle.build_runtime(args.instance), config["host"], config["port"])
            return
        elif command == "start":
            result = lifecycle.start(args.instance)
        elif command == "stop":
            result = lifecycle.stop(args.instance)
        elif command == "doctor":
            result = lifecycle.doctor(args.instance)
        elif command == "status":
            if args.instance:
                result = lifecycle.status(args.instance)
            else:
                root = lifecycle.provider_root()
                result = {
                    "format": "atmem-provider-status-list-v1",
                    "providers": [
                        lifecycle.status(path.name)
                        for path in sorted(root.iterdir())
                        if path.is_dir() and not path.is_symlink()
                    ] if root.is_dir() else [],
                }
        elif command == "remove":
            if not args.yes:
                raise ValueError("provider removal requires --yes")
            result = lifecycle.remove(args.instance)
        else:  # pragma: no cover
            raise ValueError(f"unknown provider command: {command}")
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    if command == "init":
        print(f"Created provider {result['instance']} (authority remains native AtMem).")
        print("Start it:")
        print(f"  atmem provider start {result['instance']}")
        print("Register exact trust scopes (still disabled):")
        print(f"  {result['registration_command']}")
        print(f"Then review and enable: atmem delegated enable {result['provider_id']}:{result['instance']}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))


def _interactive_atbot_setup(manager: Any) -> dict[str, Any]:
    from atmem.control.atbot_service import PROVIDER_PROFILES

    print("\nAtBot intelligence setup")
    print("Memory stays under AtMem authority. API keys are never stored by AtMem.")
    print("1. Local Ollama (recommended, private)")
    print("2. Custom local AI server (LM Studio, vLLM, llama.cpp, LocalAI)")
    print("3. Hosted API")
    print("4. Skip for now (safe deterministic fallback)")
    try:
        choice = input("Choose [1]: ").strip() or "1"
    except EOFError:
        choice = "4"
    if choice == "4":
        return manager.skip_setup()
    if choice == "1":
        default = PROVIDER_PROFILES["local-ollama"]["model"]
        model = input(f"Local model [{default}]: ").strip() or str(default)
        return manager.configure(profile="local-ollama", model=model, force=True)
    if choice == "2":
        default = PROVIDER_PROFILES["local-openai"]
        endpoint = input(f"OpenAI-compatible base URL [{default['endpoint']}]: ").strip() or str(default["endpoint"])
        model = input(f"Model name [{default['model']}]: ").strip() or str(default["model"])
        return manager.configure(
            profile="local-openai", endpoint=endpoint, model=model, force=True
        )
    if choice != "3":
        raise ValueError("choose 1, 2, 3, or 4")
    remote_names = [
        "openrouter",
        "openai",
        "deepseek",
        "xai",
        "anthropic",
        "huggingface",
        "custom-api",
    ]
    for index, name in enumerate(remote_names, 1):
        print(f"{index}. {PROVIDER_PROFILES[name]['label']}")
    selected = input("Hosted provider [1]: ").strip() or "1"
    try:
        profile = remote_names[int(selected) - 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("choose a listed hosted provider") from exc
    defaults = PROVIDER_PROFILES[profile]
    endpoint = str(defaults["endpoint"])
    if not endpoint:
        endpoint = input("HTTPS OpenAI-compatible base URL: ").strip()
    default_model = str(defaults["model"])
    model_prompt = f"Model name [{default_model}]: " if default_model else "Model name: "
    model = input(model_prompt).strip() or default_model
    default_env = str(defaults["api_key_env"])
    key_env = input(f"API-key environment variable [{default_env}]: ").strip() or default_env
    return manager.configure(
        profile=profile,
        endpoint=endpoint,
        model=model,
        api_key_env=key_env,
        force=True,
    )


def _run_dashboard(args: argparse.Namespace) -> None:
    if args.dashboard_command == "daemon":
        from atmem.dashboard_daemon import manage_dashboard_daemon

        result = manage_dashboard_daemon(
            args.dashboard_daemon_command,
            port=args.port,
            control_state_path=args.state,
        )
        if args.json:
            _print(result)
            return
        print("AtMem dashboard daemon")
        print(
            f"\n  Status       "
            f"{'running' if result.get('running') else 'stopped'}"
        )
        if result.get("pid"):
            print(f"  Process      {result['pid']}")
        if result.get("port"):
            print(f"  Port         {result['port']}")
        if result.get("url"):
            print(f"  Dashboard    {result['url']}")
        if result.get("log_path"):
            print(f"  Log          {result['log_path']}")
        if result.get("restart_required"):
            print(
                "  Action       This dashboard uses an older AtMem runtime or "
                "Python environment. Run `atmem dashboard daemon restart`."
            )
        if result.get("opened"):
            print("\nOpened the dashboard in the default browser.")
        if result.get("removed"):
            print("\nThe background service record was removed. Memory and migration data were preserved.")
        return
    _serve_dashboard(
        state_path=args.state,
        port=args.port,
        open_browser=not args.no_open,
    )


def _serve_dashboard(
    *,
    state_path: str | None,
    port: int,
    open_browser: bool,
) -> None:
    import webbrowser

    from atmem.control import ControlPlaneManager
    from atmem.control.manager import DEFAULT_STATE_PATH
    from atmem.control.web import ControlDashboardServer, dashboard_html

    manager = ControlPlaneManager(state_path or DEFAULT_STATE_PATH)
    # Fail before opening a port if no valid migration exists.
    manager.state()
    from atmem.control.atbot_service import AtBotServiceManager

    atbot_manager = AtBotServiceManager()
    companion_status = atbot_manager.status()
    if companion_status.get("setup_pending") and sys.stdin.isatty():
        _interactive_atbot_setup(atbot_manager)
    companion = atbot_manager.ensure_running()
    server = ControlDashboardServer(
        ("127.0.0.1", port),
        manager,
        html=dashboard_html(),
    )
    base = f"http://127.0.0.1:{server.server_port}/"
    print(f"AtMem dashboard: {base}", flush=True)
    print(
        "AtBot intelligence: "
        + ("ready" if companion.get("available") else "safe AtMem fallback"),
        flush=True,
    )
    print("No login is required. The dashboard is loopback-only. Press Ctrl-C to stop.", flush=True)
    if open_browser:
        webbrowser.open(base)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _run_control(args: argparse.Namespace) -> None:
    from atmem.control import ControlPlaneManager, ControlMode
    from atmem.control.manager import DEFAULT_STATE_PATH, DEFAULT_CONTROL_ROOT
    from atmem.control.server import ControlMCPServer

    state_path = args.state or str(DEFAULT_STATE_PATH)
    if args.control_command == "shadow":
        host = args.host
        manager = ControlPlaneManager.start(
            host=host,
            state_path=state_path,
            control_root=args.control_root or str(DEFAULT_CONTROL_ROOT),
            memory_db=(args.memory_db or DEFAULT_MCP_DB) if host == "generic" else None,
        )
        integration: dict[str, object]
        if host == "generic":
            integration = {
                "configured": False,
                "adapter_ready": True,
                "message": (
                    "Generic shadow mode is ready. Connect the runtime to `atmem control mcp` "
                    "and emit capture and flight events. No model context changes in shadow mode."
                ),
            }
        elif args.no_configure:
            integration = {
                "configured": False,
                "warning": "host hook was not configured; no live turns will be observed",
            }
        else:
            from atmem.control.hosts import configure_host
            from atmem.control.openclaw_native import sync_mirror

            try:
                sync_mirror(manager.state())
                integration = configure_host(manager.state(), state_path)
            except Exception:
                manager.transition(ControlMode.OFF, actor="setup-failure")
                raise
        status = manager.status()
        status["integration"] = integration
        status["next"] = (
            "Connect the runtime to `atmem control mcp`; capture and flight "
            "events will remain non-influential until activation."
            if host == "generic"
            else "Keep using your agent normally. Native memory is mirrored and "
            "searchable, but model context is unchanged."
            if integration.get("configured")
            else "Configure the host hook before expecting live migration evidence."
        )
        _print_control("shadow", status, json_output=args.json)
        return

    manager = ControlPlaneManager(state_path)
    if args.control_command == "status":
        _print_control("status", manager.status(), json_output=args.json)
    elif args.control_command == "agents":
        _print_operator_result("agents", manager.agent_topology(), json_output=args.json)
    elif args.control_command == "configure-agents":
        raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        agents = json.loads(raw)
        if not isinstance(agents, list):
            raise ValueError("agent topology JSON must be an array")
        _print_operator_result(
            "agents", manager.configure_agent_topology(agents), json_output=args.json
        )
    elif args.control_command == "memory-status":
        _print_operator_result(
            "memory-status", manager.memory_status(), json_output=args.json
        )
    elif args.control_command == "memory-sync":
        _print_operator_result(
            "memory-status", manager.sync_memory(), json_output=args.json
        )
    elif args.control_command == "memory-reviews":
        _print_operator_result(
            "memory-reviews", manager.memory_reviews(), json_output=args.json
        )
    elif args.control_command == "memory-search":
        _print_operator_result(
            "memory-search",
            manager.memory_search(
                args.query,
                limit=args.limit,
                agent_id=args.agent,
                subject_id=args.subject,
            ),
            json_output=args.json,
        )
    elif args.control_command == "memory-record":
        _print_operator_result(
            "memory-record", manager.memory_record(args.record_id), json_output=args.json
        )
    elif args.control_command == "memory-audit":
        filters = {
            "query": args.query,
            "event_type": args.event_type,
            "actor": args.actor,
            "session_id": args.session,
            "record_id": args.record,
            "since": args.since,
            "until": args.until,
            "direction": "desc",
        }
        if args.output:
            content, content_type = manager.export_memory_audit(
                output_format=args.format, filters=filters
            )
            output = Path(args.output).expanduser().resolve(strict=False)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
            result = {
                "exported": True,
                "format": args.format,
                "content_type": content_type,
                "output": str(output),
            }
            if args.json:
                _print(result)
            else:
                print(f"AtMem memory audit exported to {output}")
        else:
            _print_operator_result(
                "memory-audit",
                manager.memory_audit(**filters, limit=args.limit),
                json_output=args.json,
            )
    elif args.control_command == "memory-review":
        _print_operator_result(
            "memory-review",
            manager.review_memory(args.record_id, args.decision),
            json_output=args.json,
        )
    elif args.control_command == "verify":
        from atmem.control.verify import verification_exit_code

        report = manager.verify(probe=args.probe)
        _print_control("verify", report, json_output=args.json)
        code = verification_exit_code(report)
        if code:
            raise SystemExit(code)
    elif args.control_command == "activate":
        _confirm_control_host(manager, non_interactive=args.yes)
        def activation_progress(step: int, total: int, label: str) -> None:
            if not args.json:
                print(f"[{step}/{total}] {label}", file=sys.stderr, flush=True)

        result = manager.activate(progress=activation_progress)
        _print_control(
            "activate",
            result,
            json_output=args.json,
        )
    elif args.control_command == "restore":
        state = manager.state()
        if state.host != "openclaw":
            if args.drill:
                raise ValueError("restore drill applies only to adapters with native host state")
            _confirm_control_host(manager, non_interactive=args.yes)
            _print_control(
                "restore", manager.deactivate(actor="cli-operator"), json_output=args.json
            )
            return
        from atmem.control.openclaw_native import restore_takeover
        if args.drill:
            from atmem.control.openclaw_native import restore_drill

            result = restore_drill(state)
            _print_control("restore-drill", result, json_output=args.json)
            if not result.get("valid"):
                raise SystemExit(1)
            return
        _confirm_control_host(manager, non_interactive=args.yes)
        def restore_progress(step: int, total: int, label: str) -> None:
            if args.json:
                return
            width = 20
            filled = min(width, max(0, round(width * step / max(1, total))))
            bar = "#" * filled + "-" * (width - filled)
            print(
                f"[{bar}] {step}/{total}  {label}",
                file=sys.stderr,
                flush=True,
            )

        takeover_restore = restore_takeover(
            state,
            progress=restore_progress,
        )
        if state.mode is not ControlMode.OFF:
            state = manager.transition(ControlMode.OFF, actor="restore")
        plugin_row = next(
            (
                row
                for row in takeover_restore.get("config", [])
                if isinstance(row, dict)
                and row.get("key") == "plugins.entries.memory-atmem"
            ),
            {},
        )
        plugin_value = plugin_row.get("observed_value")
        plugin_value = plugin_value if isinstance(plugin_value, dict) else {}
        restored = {
            "host": state.host,
            "restored": bool(takeover_restore.get("valid")),
            "verified": bool(takeover_restore.get("valid")),
            "plugin_present": bool(plugin_row.get("observed_present")),
            "plugin_enabled": bool(plugin_value.get("enabled")),
            "control_plane_enabled": bool(
                ((plugin_value.get("config") or {}).get("controlPlane") or {}).get(
                    "enabled"
                )
            ),
        }
        restored["takeover"] = takeover_restore
        restored["gateway"] = takeover_restore.get("gateway")
        result = state.public_status()
        result["host_restore"] = restored
        result["restore_boundary"] = (
            "The saved host plugin configuration was restored and future "
            "AtMem injection is off. Control evidence is preserved. Past "
            "agent outputs and provider logs are not undone."
        )
        _print_control("restore", result, json_output=args.json)
    elif args.control_command == "mcp":
        ControlMCPServer(manager).serve()
    elif args.control_command == "operator-mcp":
        ControlMCPServer(manager, operator=True).serve()
    elif args.control_command == "dashboard":
        _serve_dashboard(
            state_path=state_path,
            port=args.port,
            open_browser=not args.no_open,
        )
    else:  # pragma: no cover - argparse prevents this
        raise ValueError(f"unknown control command: {args.control_command}")


def _run_blackbox(args: argparse.Namespace) -> None:
    from atmem.control.blackbox import format_flight_report
    from atmem.control.manager import ControlPlaneManager, DEFAULT_STATE_PATH

    manager = ControlPlaneManager(args.state or str(DEFAULT_STATE_PATH))
    command = args.blackbox_command
    if command in {"status", "runs"}:
        result = manager.blackbox_runs(limit=args.limit)
        if args.json:
            _print(result)
            return
        chain = result.get("chain") or {}
        print("AtMem Agent Black Box")
        print(f"\n  Host             {result.get('host')}")
        print(f"  Recorded runs    {result.get('total_runs', 0)}")
        print(f"  Recorded events  {result.get('total_events', 0)}")
        print(f"  Evidence chain   {'VALID' if chain.get('valid') else 'INVALID'}")
        print("  Stored content   digests and bounded metadata only")
        rows = result.get("runs") or []
        if rows:
            print("\nRecent flights")
            for row in rows:
                state = (
                    "cancelled"
                    if row.get("cancelled")
                    else "failed"
                    if row.get("success") is False
                    else "complete"
                    if row.get("terminal")
                    else "incomplete"
                )
                print(
                    f"  {row.get('run_id')}  {row.get('events')} events  "
                    f"{row.get('tool_completions')}/{row.get('tool_requests')} tools  "
                    f"{state}  context={row.get('context_disposition') or 'missing'}"
                )
        else:
            print("\nNo flights recorded yet. Connect a runtime adapter and emit host observations.")
        return

    if command == "record":
        raw = (
            sys.stdin.read()
            if args.envelope == "-"
            else Path(args.envelope).read_text(encoding="utf-8")
        )
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValueError("event envelope must be a JSON object")
        value = manager.record_blackbox_event(
            event_type=args.event_type,
            run_id=args.run_id,
            session_id=envelope.get("session_id"),
            tool_call_id=envelope.get("tool_call_id"),
            turn_id=envelope.get("turn_id"),
            retrieval_id=envelope.get("retrieval_id"),
            context_event_id=envelope.get("context_event_id"),
            context_receipt_id=envelope.get("context_receipt_id"),
            outcome_id=envelope.get("outcome_id"),
            agent_id=envelope.get("agent_id"),
            workspace_id=envelope.get("workspace_id"),
            subject_id=envelope.get("subject_id"),
            payload=envelope.get("payload") or {},
        )
        _print(value)
        return
    if command == "ack":
        _print(
            manager.acknowledge_blackbox_attention(
                args.run_id, args.attention_code, actor=args.actor
            )
        )
        return
    if command == "story":
        _print(manager.blackbox_flight_story(args.run_id))
        return

    report = manager.verify_blackbox_flight(args.run_id)
    if command == "export":
        output = Path(args.output).expanduser().resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        content = (
            json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else format_flight_report(report)
        )
        output.write_text(content, encoding="utf-8")
        if args.json:
            _print(
                {
                    "exported": True,
                    "run_id": args.run_id,
                    "format": args.format,
                    "output": str(output),
                    "report_sha256": report.get("report_sha256"),
                }
            )
        else:
            print(f"Agent flight exported to {output}")
            print(f"Report SHA-256: {report.get('report_sha256')}")
        return
    if args.json:
        _print(report)
    else:
        print(format_flight_report(report), end="")


def _run_benchmark_cli(args: argparse.Namespace) -> None:
    from atmem.benchmark.contracts import read_json, write_json
    from atmem.benchmark.external import compare_results, import_longmemeval
    from atmem.benchmark.profiles import list_profiles
    from atmem.benchmark.runner import run_benchmark

    command = args.benchmark_command
    if command == "profiles":
        profiles = list_profiles()
        if args.json:
            _print({"profiles": profiles})
        else:
            for profile in profiles:
                state = "ready" if profile["available"] else "not ready"
                print(
                    f"{profile['mode']}: {state}; egress={profile['egress_class']}; "
                    f"provider={profile['provider']}"
                )
                if profile.get("skip_reason"):
                    print(f"  {profile['skip_reason']}")
        return
    if command == "import-longmemeval":
        result = import_longmemeval(args.input)
        write_json(args.output, result)
        if args.json:
            _print(result)
        else:
            counts = result["counts"]
            print(
                f"Imported {counts['supported']} supported cases; "
                f"{counts['skipped']} skipped; {counts['unsupported']} unsupported."
            )
            print(f"Wrote {Path(args.output).resolve(strict=False)}")
        return
    if command == "compare":
        result = compare_results(read_json(args.left), read_json(args.right))
        if args.output:
            write_json(args.output, result)
        if args.json:
            _print(result)
        else:
            print("Fair comparison: yes")
            print("Systems: " + " vs ".join(result["systems"]))
            print("Outcome: " + result["overall"]["outcome"])
            print(result["overall"]["statement"])
            for name, metric_result in result["metrics"].items():
                print(f"  {name}: {metric_result['winner']}")
            if args.output:
                print(f"Wrote {Path(args.output).resolve(strict=False)}")
        return

    report = run_benchmark(
        profile_name=args.profile,
        dataset_path=args.dataset,
        thresholds_path=args.thresholds,
    )
    if args.output:
        write_json(args.output, report)
    if args.json:
        _print(report)
    else:
        print(f"Memory benchmark: {report['status'].upper()}")
        print(f"Profile: {report['profile']['mode']}")
        print(f"Cases: {len(report['case_results'])}")
        print(f"Quality digest: {report['quality_sha256']}")
        for failure in report["failures"]:
            print(f"  FAIL: {failure}")
        if args.output:
            print(f"Wrote {Path(args.output).resolve(strict=False)}")
    if not report["passed"]:
        raise SystemExit(2 if report["status"] == "skipped" else 1)


def _confirm_control_host(
    manager: object, *, non_interactive: bool
) -> None:
    state = manager.state()  # type: ignore[attr-defined]
    if non_interactive:
        return
    if not sys.stdin.isatty():
        raise ValueError(
            f"confirmation required; rerun with --yes after reviewing host {state.host}"
        )
    entered = input(f"Type the host name `{state.host}` to confirm: ").strip()
    if entered != state.host:
        raise ValueError("host confirmation did not match")


if __name__ == "__main__":
    main()
