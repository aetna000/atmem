"""Synchronized process-kill trials; only processes created here are terminated."""
from __future__ import annotations

import multiprocessing as mp
from contextlib import closing
from multiprocessing.connection import wait
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

from .destination import serve
from .manifest import digest, environment_stamp
from .oracle import score_effects
from .runtime import worker

BARRIERS = ("before_dispatch", "after_intent", "in_flight", "after_commit",
            "after_response", "after_receipt_journaled", "after_task_committed", "after_checkpoint")


def trial(root: Path, *, capability: str = "I", fault: str | None = "after_commit",
          atmem: bool = False, naive: bool = False, retention: float = 3600,
          visibility: float = 0, timeout: float = 30, drop_request: bool = False) -> dict:
    if fault is not None and fault not in BARRIERS:
        raise ValueError("unknown fault barrier")
    if capability not in {"I", "Q", "N"} or timeout <= 0:
        raise ValueError("invalid trial configuration")
    stamp = environment_stamp()
    root.mkdir(parents=True, exist_ok=False)
    worker_dir = root / "worker"
    worker_dir.mkdir()
    ctx = mp.get_context("spawn")
    control, dest_control = ctx.Pipe()
    dest_events, dest_writer = ctx.Pipe(duplex=False)
    release = ctx.Event()
    token = secrets.token_urlsafe(32)
    destination = ctx.Process(target=serve, args=(dest_control, dest_writer, release,
                              capability, fault, token, retention, visibility, drop_request), daemon=True)
    processes = [destination]
    connections = [control, dest_control, dest_events, dest_writer]
    started = time.monotonic()
    execution_started = None
    terminal_time = None
    run_id = str(uuid.uuid4())
    observation = {"schema_version": 1, "trial_id": run_id, "task_id": "smoke-write-1",
                   "provenance": stamp,
                   "evidence_level": "smoke", "runtime": "langgraph",
                   "arm": "runtime+atmem" if atmem else "runtime",
                   "negative_control": naive, "capability": capability, "fault": fault,
                   "drop_request": drop_request,
                   "fault_reached": False, "events": [], "disposition": "infrastructure_failure",
                   "limitations": ["Generic fixture, not tau retail or production evaluation",
                                    "Process/API isolation, not adversarial OS sandbox",
                                    "Worker SIGKILL only; no power-loss, host or destination crash guarantee",
                                    "Shared runtime reconciliation; AtMem-specific benefit not measured",
                                    "No model calls; token, pricing and context metrics unavailable",
                                    "Full-fidelity evidence reconstruction not evaluated"]}
    config = {"worker_dir": str(worker_dir), "operation_id": "operation-1",
              "task_id": "task-1", "scope_id": run_id, "payload": {"fixture_value": 42},
              "atmem": atmem, "naive": naive, "fault": fault, "capability": capability,
              "token": token}
    restarted = None
    try:
        if atmem:
            from .adapters.atmem import AtMemTaskAdapter
            adapter = AtMemTaskAdapter(worker_dir / "atmem.db", run_id, "task-1")
            try:
                adapter.setup("operation-1")
            finally:
                adapter.close()
        destination.start()
        dest_control.close()
        dest_writer.close()
        if not control.poll(timeout):
            raise TimeoutError("destination startup")
        config.update(control.recv())

        def start_worker(resume: bool):
            parent, child = ctx.Pipe()
            connections.extend([parent, child])
            process = ctx.Process(target=worker, args=(config, child, resume), daemon=True)
            processes.append(process)
            process.start()
            child.close()
            return process, parent

        execution_started = time.monotonic()
        observation["fixture_setup_ms"] = (execution_started-started)*1000
        process, worker_events = start_worker(False)
        deadline = time.monotonic() + timeout
        terminal = None
        while time.monotonic() < deadline:
            ready = wait([worker_events, dest_events], timeout=max(0, deadline-time.monotonic()))
            if not ready:
                raise TimeoutError("worker/fault barrier")
            for connection in ready:
                try:
                    event = connection.recv()
                except EOFError as exc:
                    raise RuntimeError("process channel closed unexpectedly") from exc
                observation["events"].append(event)
                if "worker_error" in event:
                    raise RuntimeError(event["worker_error"])
                if "product_refusal" in event:
                    terminal = {"outcome": "product_refusal", "reason": event["product_refusal"]}
                    terminal_time = time.monotonic()
                    break
                if fault is not None and event.get("barrier") == fault and not observation["fault_reached"]:
                    observation["fault_reached"] = True
                    process.kill()
                    process.join(timeout)
                    if process.is_alive():
                        raise TimeoutError("worker did not terminate")
                    observation["killed_worker_exitcode"] = process.exitcode
                    if not destination.is_alive():
                        raise RuntimeError("destination died with worker")
                    release.set()
                    if fault in {"in_flight", "after_commit"}:
                        if not dest_events.poll(timeout):
                            raise TimeoutError("destination did not settle after kill")
                        settled = dest_events.recv()
                        observation["events"].append(settled)
                        if not settled.get("destination_settled"):
                            raise RuntimeError("missing settled confirmation")
                    restarted = time.monotonic()
                    process, worker_events = start_worker(True)
                    deadline = time.monotonic() + timeout
                    break
                if "worker_result" in event:
                    terminal = event["worker_result"]
                    terminal_time = time.monotonic()
                    break
            if terminal is not None:
                break
        if terminal is None:
            raise TimeoutError("no terminal result")
        process.join(timeout)
        if process.exitcode != 0:
            raise RuntimeError(f"worker exit {process.exitcode}")
        control.send("snapshot")
        if not control.poll(timeout):
            raise TimeoutError("destination snapshot")
        ledger = control.recv()
        outcome = terminal.get("outcome")
        if atmem:
            from .adapters.atmem import AtMemTaskAdapter
            adapter = AtMemTaskAdapter(worker_dir / "atmem.db", run_id, "task-1")
            try:
                durable_status = adapter.status("operation-1")
            finally:
                adapter.close()
        else:
            with closing(sqlite3.connect((worker_dir / 'dispatch.db').resolve().as_uri() + '?mode=ro', uri=True)) as db:
                status_row = db.execute("SELECT status FROM decisions WHERE operation='operation-1'").fetchone()
                durable_status = status_row[0] if status_row else "unknown"
        blocked = ["operation-1"] if durable_status == "blocked" else []
        scored = score_effects({"operation-1": digest(config["payload"])}, ledger, blocked)
        if outcome == "product_refusal":
            disposition = "product_refusal"
        elif scored["duplicate_effects"] or scored["wrong_effects"]:
            disposition = "invalid_effects"
        elif durable_status == "blocked":
            disposition = "blocked"
        elif scored["valid_completion"] and durable_status == "completed":
            disposition = "completed"
        else:
            disposition = "invalid_completion"
        observation.update({"disposition": disposition, "durable_status": durable_status,
                            "worker_outcome": outcome, "ledger": ledger,
                            "oracle": scored,
                            "restart_to_terminal_ms": (terminal_time-restarted)*1000 if restarted else None})
        if fault and not observation["fault_reached"]:
            observation["disposition"] = "fault_not_reached"
    except Exception as exc:
        observation["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        release.set()
        # Teardown does not inspect or terminate any user process.
        if destination.pid and destination.is_alive():
            try:
                control.send("stop")
            except (BrokenPipeError, EOFError, OSError):
                pass
        for process in reversed(processes):
            if process.pid is not None:
                try:
                    process.join(2)
                    if process.is_alive():
                        process.kill()
                        process.join(2)
                except (OSError, ValueError):
                    pass
        for connection in connections:
            try:
                connection.close()
            except OSError:
                pass
    observation["elapsed_ms"] = ((terminal_time-execution_started)*1000
                                  if terminal_time and execution_started else None)
    observation["trial_wall_ms"] = (time.monotonic()-started)*1000
    observation["storage_bytes"] = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    return observation
