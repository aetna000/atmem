"""Build explicit OTLP fixture identities; never infer them from span names."""
from __future__ import annotations

import hashlib


def otlp_attempt(*, workflow_id: str, scope_id: str, task_id: str,
                 operation_id: str, run_id: str, attempt_id: str,
                 charge_id: str, retry: bool = False, recovery: bool = False) -> dict:
    fields = {"session.id": workflow_id, "continuity.schema_version": 1,
              "continuity.scope_id": scope_id, "continuity.task_id": task_id,
              "continuity.logical_operation_id": operation_id, "continuity.run_id": run_id,
              "continuity.attempt_id": attempt_id, "continuity.charge_id": charge_id,
              "continuity.retry": retry, "continuity.recovery": recovery}
    if any(not isinstance(v, str) or not v for k, v in fields.items()
           if k not in {"continuity.schema_version", "continuity.retry", "continuity.recovery"}):
        raise ValueError("all identity fields must be explicit nonempty strings")
    attributes = [{"key": key, "value": {"boolValue" if isinstance(value, bool)
                  else "intValue" if isinstance(value, int) else "stringValue":
                  str(value) if isinstance(value, int) and not isinstance(value, bool) else value}}
                  for key, value in fields.items()]
    identity = f"{scope_id}:{workflow_id}"
    return {"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [{
        "scope": {"name": "atmem.continuity", "version": "1"}, "spans": [{
            "traceId": hashlib.sha256(identity.encode()).hexdigest()[:32],
            "spanId": hashlib.sha256((identity + ':' + attempt_id).encode()).hexdigest()[:16],
            "name": "continuity.tool.attempt", "attributes": attributes,
            "startTimeUnixNano": "1700000000000000000", "endTimeUnixNano": "1700000000100000000",
            "status": {"code": 0}}]}]}]}
