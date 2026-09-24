"""LangGraph durable worker for the isolated smoke workload only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, TypedDict
import uuid

from .destination import request
from .manifest import digest


def worker(config: dict, events: Any, resume: bool) -> None:
    try:
        _run(config, events, resume)
    except Exception as exc:
        if hasattr(exc, "product_refusal"):
            events.send({"product_refusal": str(exc)})
            return
        events.send({"worker_error": type(exc).__name__ + ": " + str(exc)})
        raise


def _run(config: dict, events: Any, resume: bool) -> None:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    root = Path(config["worker_dir"])
    run_id, attempt_id = str(uuid.uuid4()), str(uuid.uuid4())
    events.send({"run_id": run_id, "attempt_id": attempt_id, "resume": resume})
    operation = config["operation_id"]
    journal = sqlite3.connect(root / "dispatch.db")
    journal.execute("PRAGMA synchronous=FULL")
    journal.execute("CREATE TABLE IF NOT EXISTS dispatch (operation TEXT PRIMARY KEY, phase TEXT, receipt TEXT)")
    if not config["atmem"]:
        journal.execute("CREATE TABLE IF NOT EXISTS decisions (operation TEXT PRIMARY KEY, status TEXT)")
    task_adapter = None
    if config["atmem"]:
        from .adapters.atmem import AtMemTaskAdapter
        task_adapter = AtMemTaskAdapter(root / "atmem.db", config["scope_id"], config["task_id"])

    def barrier(name: str) -> None:
        if not resume and config["fault"] == name:
            events.send({"barrier": name, "producer": "worker", "time_ns": time.monotonic_ns()})
            # No sleep heuristic: supervisor observes this handshake then kills us.
            events.recv()

    def phase(value: str, receipt: dict | None = None) -> None:
        journal.execute("INSERT OR REPLACE INTO dispatch VALUES(?,?,?)",
                        (operation, value, json.dumps(receipt) if receipt else None))
        journal.commit()

    def task_status(value: str, receipt: dict | None = None) -> None:
        if task_adapter:
            task_adapter.set_status(operation, value, attempt_id, receipt)
        else:
            journal.execute("INSERT OR REPLACE INTO decisions VALUES(?,?)", (operation, value))
            journal.commit()

    class State(TypedDict, total=False):
        operation_id: str
        outcome: str

    def prepare(state: State) -> State:
        if journal.execute("SELECT 1 FROM dispatch WHERE operation=?", (operation,)).fetchone() is None:
            phase("prepared")
        return {"operation_id": operation}

    def dispatch(state: State) -> State:
        row = journal.execute("SELECT phase,receipt FROM dispatch WHERE operation=?", (operation,)).fetchone()
        if row and row[0] == "received" and not config["naive"]:
            receipt = json.loads(row[1])
            if receipt.get("payload_digest") != digest(config["payload"]):
                task_status("blocked")
                return {"outcome": "blocked_receipt_conflict"}
            if not task_adapter or task_adapter.status(operation) != "completed":
                task_status("completed", receipt)
            return {"outcome": "confirmed_succeeded"}
        if task_adapter and task_adapter.status(operation) == "completed" and not config["naive"]:
            return {"outcome": "confirmed_succeeded"}
        barrier("before_dispatch")
        ambiguous = row and row[0] == "in_flight" and not config["naive"]
        if ambiguous and config["capability"] == "N":
            task_status("blocked")
            return {"outcome": "blocked_unknown"}
        task_status("running")
        if ambiguous and config["capability"] == "Q":
            receipt = request(config["url"], config["token"], "/status", {"operation_id": operation})
            if receipt.get("outcome") == "confirmed_failed" and receipt.get("reason") == "fenced_abort_no_inflight_writer":
                receipt = request(config["url"], config["token"], "/effects",
                                  {"operation_id": operation, "payload": config["payload"]})
        else:
            phase("in_flight")
            barrier("after_intent")
            receipt = request(config["url"], config["token"], "/effects",
                              {"operation_id": operation, "payload": config["payload"]})
        barrier("after_response")
        if (receipt.get("outcome") != "confirmed_succeeded" or
                receipt.get("payload_digest") != digest(config["payload"]) or
                not receipt.get("effect_id")):
            task_status("blocked")
            return {"outcome": "blocked_unknown"}
        phase("received", receipt)
        barrier("after_receipt_journaled")
        task_status("completed", receipt)
        barrier("after_task_committed")
        return {"outcome": "confirmed_succeeded"}

    graph = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("dispatch", dispatch)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "dispatch")
    graph.add_edge("dispatch", END)
    try:
        with SqliteSaver.from_conn_string(str(root / "checkpoints.db")) as saver:
            app = graph.compile(checkpointer=saver)
            invocation = {"configurable": {"thread_id": config["task_id"]}}
            previous = app.get_state(invocation)
            result = app.invoke(None if resume and previous.values and not config["naive"] else {},
                                invocation, durability="sync")
            # invoke returned with sync durability, so this barrier is after commit.
            barrier("after_checkpoint")
            events.send({"worker_result": result, "run_id": run_id, "attempt_id": attempt_id})
    finally:
        journal.close()
        if task_adapter:
            task_adapter.close()
