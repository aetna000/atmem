"""Bounded process-local operational counters, never prompts or tool payloads.

Detailed evidence stays in the encrypted vault. Metrics use closed operation and
reason buckets and are scoped internally by a digest, never a caller label. They
reset at process restart and are not an externally durable monotonic authority.
"""
from collections import deque
from contextlib import contextmanager
from functools import wraps
import math
import threading
import time

from atmem.contracts.feedback import FeedbackScope


OPERATIONS = frozenset({"rag.search", "rag.inspect", "outcome.report", "context.retain", "verification.readback",
                        "proxy.execute", "rule.evaluate"})


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered)*fraction)-1)]


def reason_bucket(code):
    # Do not retain arbitrary exception strings or dynamic provider labels.
    if type(code) is not str:
        return "error"
    if code == "denied" or code in {"not_independent", "verifier_changed"}:
        return "denied"
    if "timeout" in code:
        return "timeout"
    if "uncertain" in code:
        return "uncertain"
    if "expired" in code:
        return "expired"
    if "stale" in code or "conflict" in code:
        return "conflict"
    if "unavailable" in code or "busy" in code:
        return "unavailable"
    return "error"


class FeedbackObservability:
    def __init__(self, *, timer=time.perf_counter):
        self.timer = timer
        self._scopes = {}
        self._lock = threading.Lock()

    @contextmanager
    def measure(self, scope, operation):
        if type(scope) is not FeedbackScope or operation not in OPERATIONS:
            raise ValueError("closed metric operation and fixed scope required")
        started, reason = self.timer(), "ok"
        result = {"reason":"ok"}
        try:
            yield result
            reason = result["reason"] if result["reason"] in {"ok", "blocked", "uncertain"} else "error"
        except BaseException as exc:
            reason = reason_bucket(getattr(exc, "code", "error"))
            raise
        finally:
            duration = max(0, (self.timer()-started)*1000)
            with self._lock:
                key = scope.content_digest
                # Exhaustion drops telemetry, never authority/evidence or effects.
                if key in self._scopes or len(self._scopes) < 64:
                    rows = self._scopes.setdefault(key, {})
                    row = rows.setdefault(operation, {"calls":0, "reasons":{}, "latencies":deque(maxlen=256)})
                    row["calls"] += 1
                    row["reasons"][reason] = row["reasons"].get(reason, 0)+1
                    row["latencies"].append(duration)

    def snapshot(self, scope):
        if type(scope) is not FeedbackScope:
            raise ValueError("fixed metric scope required")
        with self._lock:
            rows = self._scopes.get(scope.content_digest, {})
            return {"format":"atmem-feedback-runtime-v1", "retention":"process_local",
                    "window":"last_256_calls_per_operation", "scope_limit":64,
                    "operations":{name:{"calls":row["calls"], "reasons":dict(row["reasons"]),
                        "latency_ms":{"p50":percentile(row["latencies"], .5), "p95":percentile(row["latencies"], .95),
                                      "samples":len(row["latencies"])}}
                        for name,row in sorted(rows.items())},
                    "external_usage":"not_measured_by_runtime_counters"}


def measured(operation):
    def decorate(method):
        @wraps(method)
        def call(self, session, *args, **kwargs):
            feedback = getattr(self, "feedback", self)
            scope = getattr(session, "scope", None)
            if type(scope) is not FeedbackScope:
                return method(self, session, *args, **kwargs)
            with feedback.observability.measure(scope, operation) as metric:
                result = method(self, session, *args, **kwargs)
                if type(result) is dict and result.get("status") in ("blocked", "uncertain"):
                    metric["reason"] = result["status"]
                return result
        return call
    return decorate
