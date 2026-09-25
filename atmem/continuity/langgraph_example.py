"""An ordinary persistent LangGraph application using governed document tools.

Start once, then use resume after interruption. No evaluator or fault hooks.
"""
import argparse
import json
import operator
import os
from pathlib import Path
import sqlite3
from typing import Annotated, TypedDict
import uuid

from .client import AtFlowsObserver, ContinuityClient, RecoveryBlocked
from .integrations import GovernedToolRunner, RegisteredTool, governed_langgraph_tools
from .tools import DirectoryPublisher


def main():
    parser = argparse.ArgumentParser(description="Publish a document through a persistent governed LangGraph workflow")
    parser.add_argument("action", choices=["start", "resume"])
    parser.add_argument("--url", default="http://127.0.0.1:8768")
    parser.add_argument("--thread", required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document", type=Path)
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--atflows-url")
    args = parser.parse_args()
    if not args.enabled:
        parser.error("explicit --enabled is required; governed execution is disabled by default")
    token = os.environ.get("ATMEM_EVIDENCE_TOKEN")
    if not token:
        parser.error("set ATMEM_EVIDENCE_TOKEN to a workspace coordinator credential")
    try:
        from langgraph.graph import StateGraph, START, END
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        parser.error("install the documented optional LangGraph dependency profile")
    observer = None
    if args.atflows_url:
        observer_token = os.environ.get("ATFLOWS_CONTINUITY_TOKEN")
        if not observer_token:
            parser.error("set ATFLOWS_CONTINUITY_TOKEN for the configured observer")
        observer = AtFlowsObserver(args.atflows_url, observer_token)
    client = ContinuityClient(args.url, token, observer=observer)
    publisher = DirectoryPublisher(args.output)
    runner = GovernedToolRunner(client, "document-publisher-v1", {
        "publish_document": RegisteredTool(publisher.tool(), capability="query")}, enabled=True)

    class State(TypedDict):
        messages: Annotated[list, operator.add]

    args.checkpoints.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.checkpoints, check_same_thread=False) as connection:
        builder = StateGraph(State)
        builder.add_node("tools", governed_langgraph_tools(runner))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        graph = builder.compile(checkpointer=SqliteSaver(connection))
        config = {"configurable": {"thread_id": args.thread, "continuity_namespace": "publish"}}
        prior = graph.get_state(config)
        if args.action == "start":
            if prior.values:
                parser.error("this thread already exists; use resume or explicitly choose a new thread")
            if not args.document:
                parser.error("start requires --document")
            text = args.document.read_text(encoding="utf-8")
            if len(text.encode("utf-8")) > 131072:
                parser.error("document exceeds 128 KiB")
            state = {"messages": [{"role": "assistant", "id": "message_" + uuid.uuid4().hex,
                "tool_calls": [{"id": "call_" + uuid.uuid4().hex, "name": "publish_document",
                    "args": {"text": text, "destination": str(publisher.directory)}}]}]}
        else:
            if not prior.values:
                parser.error("no saved thread found; use the original checkpoints file and thread")
            state = None
        try:
            result = graph.invoke(state, config, durability="sync")
            print(json.dumps({"result": result, "observation_errors": client.observation_errors,
                              "observation_error_count": client.observation_error_count}))
        except RecoveryBlocked as exc:
            print(json.dumps({"stopped_safely": str(exc), "next": "Review Decisions > Resume work; keep this checkpoint file."}))
            raise SystemExit(2)


if __name__ == "__main__":
    main()
