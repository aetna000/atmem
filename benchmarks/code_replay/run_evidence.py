"""Benchmark-only per-run vault topology, reusing ordinary governed evidence."""
from hashlib import sha256
import os

from benchmarks.code_replay.atmem_bridge import ReplayEvidence


class RunReplayEvidence:
    def __init__(self, root, *, vault_id, scope, writing_run):
        if type(writing_run) is not str or not 1 <= len(writing_run) <= 256:
            raise ValueError("one explicit operational writing run required")
        self.root, self.vault_id, self.scope = root, vault_id, scope
        self.writing_run = writing_run
        self._runs, self._legacy = {}, None

    def _location(self, run):
        identity = sha256(run.encode()).hexdigest()
        return self.root.parent / "run-vaults-v1" / identity / "vault", "run-" + identity[:32]

    def for_run(self, run):
        """Return a normal protected vault, including its normal export/audit API."""
        path, identity = self._location(run)
        if run == self.writing_run or path.exists():
            if run not in self._runs:
                self._runs[run] = ReplayEvidence(path, vault_id=identity, scope=self.scope)
            return self._runs[run]
        if self._legacy is None:
            self._legacy = ReplayEvidence(self.root, vault_id=self.vault_id, scope=self.scope)
        return self._legacy

    def capture(self, *, run_id, kind, payload, principal):
        if run_id != self.writing_run:
            raise PermissionError("operational writer is bound to exactly one evidence run")
        return self.for_run(run_id).capture(run_id=run_id, kind=kind, payload=payload, principal=principal)

    def inspect(self, principal, run_id):
        return self.for_run(run_id).inspect(principal, run_id)


def operational_evidence(root, *, vault_id, scope, writing_run):
    if os.environ.get("ATMEM_BENCHMARK_PER_RUN_VAULTS") == "1":
        return RunReplayEvidence(root, vault_id=vault_id, scope=scope, writing_run=writing_run)
    return ReplayEvidence(root, vault_id=vault_id, scope=scope)
