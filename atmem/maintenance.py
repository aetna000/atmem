"""Scheduled graph consolidation using an independent SQLite connection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from typing import Callable

from atmem.memory import Memory


class GraphMaintenanceWorker:
    def __init__(
        self,
        database: str | Path,
        *,
        interval_seconds: float,
        archive_root: str | Path,
        archive_after_days: int = 365,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.database = str(database)
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.archive_root = Path(archive_root).expanduser()
        self.archive_after_days = max(0, int(archive_after_days))
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="atmem-graph-maintenance",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float | None = None) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if not self._thread.is_alive():
                self._thread = None

    def run_once(self) -> list[dict[str, object]]:
        memory = Memory(self.database)
        try:
            self._expire_due_tasks(memory)
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=self.archive_after_days)
            ).isoformat()
            reports: list[dict[str, object]] = []
            for subject_id in memory.store.subject_ids():
                reports.append(
                    memory.consolidate_graph(
                        subject_id,
                        archive_root=(
                            self.archive_root if self.archive_after_days else None
                        ),
                        archive_before=(cutoff if self.archive_after_days else None),
                        actor="graph-maintenance",
                    )
                )
                memory.store.verify_audit_chain_incremental(subject_id)
            memory.optimize()
            return reports
        finally:
            memory.close()

    def _expire_due_tasks(self, memory: Memory) -> dict[str, object]:
        """Retire governed tasks whose bound age rule is due.

        The scan is idempotent and safe to run alongside lazy evaluation: a
        task that expires here reaches exactly one terminal head, and a task
        already terminal is never re-evaluated. Failing here must not stop the
        rest of maintenance, so the outcome is returned rather than raised.
        """
        from atmem.task_state.service import TaskStateService

        try:
            return TaskStateService(memory.store).scan_for_expiry()
        except Exception as exc:  # a scan failure must not block consolidation
            if self.on_error is not None:
                self.on_error(exc)
            return {
                "format": "atmem-task-expiry-scan-v1",
                "expired_task_ids": [],
                "expired": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.run_once()
            except Exception as exc:  # maintenance failure must not stop the service
                if self.on_error is not None:
                    self.on_error(exc)
