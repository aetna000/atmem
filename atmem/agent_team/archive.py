"""Portable execution events in AtMem's existing per-run encrypted evidence vault."""

from contextlib import contextmanager
from datetime import datetime, timezone

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.evidence import CaptureMode, EvidenceScope


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return sha256_hex(canonical_json(value))


class RunArchive:
    def __init__(self, store, scope: EvidenceScope):
        if not scope.workspace_id or scope.run_id:
            raise PermissionError("An exact project workspace is required.")
        self.store, self.scope = store, scope
        self.index = "teamindex_" + digest(scope.to_dict())

    def _envelopes(self, key, origin):
        return [
            doc["envelope"]
            for doc in self.store.documents(partition_id="run:" + key)
            if doc.get("origin") == origin
            and self.scope.permits(
                EvidenceScope(
                    doc["envelope"]["tenant_id"],
                    doc["envelope"]["subject_id"],
                    doc["envelope"]["workspace_id"],
                    key,
                )
            )
        ]

    def ids(self, *, recipient=None):
        entries = self._envelopes(self.index, "agent-team-index-v1")
        if recipient is None:
            return [e["payload"]["run_id"] for e in entries]
        return [e["payload"]["run_id"] for e in entries if e["payload"].get("recipient") == recipient]

    def host_events(self, run_id, recipient):
        if run_id not in self.ids(recipient=recipient):
            return []
        return self._envelopes(run_id, "agent-team-v1")

    def events(self, run_id):
        if run_id not in self.ids():
            return []
        return self._envelopes(run_id, "agent-team-v1")

    def _write(self, run_id, origin, event, data):
        if self.store.capture_mode() is not CaptureMode.FULL:
            raise PermissionError("Portable runs require full encrypted evidence capture.")
        envelope = {
            **self.scope.to_dict(),
            "run_id": run_id,
            "event_type": event,
            "occurred_at": now(),
            "payload": data,
        }
        self.store.append(
            {
                "record_type": "evidence",
                "origin": origin,
                "capture_mode": "full",
                "reconstructable": True,
                "envelope": envelope,
            },
            partition_id="run:" + run_id,
        )

    def start(self, report, **bindings):
        key = report["run_id"]
        if key in self.ids():
            raise ValueError("Run already exists.")
        if any(e["payload"]["run_id"] == key for e in self._envelopes(self.index, "agent-team-deleted-v1")):
            raise ValueError("This request ID belongs to a deleted run.")
        entry = {"run_id": key}
        if "recipient" in bindings:
            entry["recipient"] = bindings["recipient"]
        self._write(self.index, "agent-team-index-v1", "team.indexed", entry)
        self._write(key, "agent-team-v1", "team.started", {"report": report, **bindings})

    def append(self, run_id, event, data):
        self._write(run_id, "agent-team-v1", event, data)

    @staticmethod
    def project(events):
        if not events:
            raise PermissionError("Run unavailable in this workspace.")
        base = events[0]["payload"]
        run = {**base["report"], "steps": list(base["report"]["steps"]), "outcomes": []}
        for envelope in events[1:]:
            data = envelope["payload"]
            if "step" in data:
                run["steps"].append(data["step"])
                run.update(data["update"])
            if envelope["event_type"] == "team.outcome":
                run["outcomes"].append(data)
        return run

    def list_runs(self, *, outcome_ref="", before="", limit=30):
        ids = self.ids()[::-1]
        if before:
            if before not in ids:
                raise ValueError("Unknown workspace cursor.")
            ids = ids[ids.index(before) + 1 :]
        result = []
        for key in ids:
            events = self._envelopes(key, "agent-team-v1")
            if not events:
                continue
            run = self.project(events)
            if outcome_ref and not any(
                outcome_ref.casefold() in item["reference"].casefold() for item in run["outcomes"]
            ):
                continue
            result.append(
                {
                    field: run.get(field)
                    for field in (
                        "run_id",
                        "question",
                        "started_at",
                        "policy",
                        "outcome",
                        "outcomes",
                        "rerun_of",
                        "elapsed_ms",
                        "input_tokens",
                        "output_tokens",
                        "usage_complete",
                        "cost_microusd",
                    )
                }
            )
            if len(result) > limit:
                break
        return {
            "runs": result[:limit],
            "next_cursor": result[limit - 1]["run_id"] if len(result) > limit else None,
        }


@contextmanager
def archive_transaction(manager):
    evidence = manager.evidence_service()
    with evidence.key_transition_lock():
        fresh = manager.evidence_service()
        with fresh._store() as store, store.atomic():
            yield fresh, store
