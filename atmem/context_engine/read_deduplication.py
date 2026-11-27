"""Conservative projection of normalized, verified file-read results."""

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)

CALL_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def project_read_results(messages, successful_read_ids, grace, count):
    """Replace old results only when a mature, producer-verified match remains."""
    boundary = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)
    calls = {}
    call_counts = Counter()
    result_counts = Counter()
    correlated_results = set()
    pending = set()
    batch_results = set()
    completed_batches = set()
    round_number = 0
    for index, message in enumerate(messages):
        if message.get("role") == "tool":
            result_id = message["tool_call_id"]
            result_counts[result_id] += 1
            if result_id in pending:
                pending.remove(result_id)
                batch_results.add(index)
                if not pending:
                    completed_batches.add(round_number)
                    correlated_results.update(batch_results)
            else:
                pending.clear()
            continue
        pending.clear()
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            continue
        round_number += 1
        batch_results = set()
        pending = {call["id"] for call in message["tool_calls"]}
        for call in message["tool_calls"]:
            call_id = call["id"]
            call_counts[call_id] += 1
            function = call.get("function")
            if (index <= boundary or call.get("type") != "function"
                or not isinstance(function, dict) or function.get("name") != "read"
                or not isinstance(call_id, str) or not CALL_ID.fullmatch(call_id)):
                continue
            try:
                args = json.loads(function["arguments"])
            except (KeyError, TypeError, ValueError):
                continue
            if (not isinstance(args, dict) or not args.keys() <= {"path", "offset", "limit"}
                or not isinstance(args.get("path"), str) or not args["path"]
                or any(type(args[key]) is not int or args[key] < 1 for key in args.keys() - {"path"})):
                continue
            calls[call_id] = (round_number, function["arguments"])

    projected = messages.copy()
    retained = {}
    eligible = []
    verified = set(successful_read_ids)
    # Any read in this prefix has at least `grace` completed batches after it.
    mature_before = round_number + 1
    if grace:
        mature_before = sorted(completed_batches)[-grace] if grace <= len(completed_batches) else 0
    for index in range(len(messages) - 1, boundary, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        call_id = message["tool_call_id"]
        body = message.get("content")
        if (index not in correlated_results or call_id not in calls or call_id not in verified
            or not isinstance(body, str) or not body
            or call_counts[call_id] != 1 or result_counts[call_id] != 1):
            continue
        read_round, args = calls[call_id]
        identity = (args, body)
        replacement = retained.get(identity)
        if replacement and replacement[0] > read_round:
            reference = f"[Identical read result retained at tool call {replacement[1]}.]"
            if count(wire(reference)) < count(wire(body)):
                eligible.append(body)
                projected[index] = {**message, "content": reference}
        elif replacement is None and read_round < mature_before:
            retained[identity] = (read_round, call_id)
    return projected, eligible


def normalized_call(call_id, name, arguments):
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        arguments = wire(parsed) if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        arguments = None
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


@dataclass(frozen=True)
class VerifiedRead:
    """A successful read attested by the host for the current run."""

    call_id: str
    arguments_sha256: str
    result_sha256: str

    @classmethod
    def from_result(cls, call_id: str, arguments: dict[str, Any], result: str) -> "VerifiedRead":
        return cls(call_id, sha256(wire(arguments).encode()).hexdigest(), sha256(result.encode()).hexdigest())


@dataclass(frozen=True)
class ReadDeduplication:
    """Opt-in projection for the read tool with path and optional offset/limit."""

    verified_reads: Callable[[Any, Sequence[Any]], Iterable[VerifiedRead]]
    count_tokens: Callable[[str], int]
    grace: int = 2

    def __post_init__(self):
        if type(self.grace) is not int or self.grace < 0:
            raise ValueError("read deduplication grace must be a nonnegative integer")

    def _count(self, text: str) -> int:
        count = self.count_tokens(text)
        if type(count) is not int or count < 0:
            raise ValueError("token counter must return a nonnegative integer")
        return count

    def project(self, runtime, native_messages, normalized_messages):
        if not any(message.get("role") == "user" for message in normalized_messages):
            return normalized_messages
        try:
            receipts = set(self.verified_reads(runtime, tuple(native_messages)))
            if not receipts:
                return normalized_messages
            arguments = {
                call["id"]: call["function"]["arguments"]
                for message in normalized_messages for call in message.get("tool_calls", ())
                if call["function"]["name"] == "read" and call["function"]["arguments"] is not None
            }
            verified_ids = set()
            for message in normalized_messages:
                call_id = message.get("tool_call_id")
                body = message.get("content")
                if call_id in arguments and isinstance(body, str) and VerifiedRead(
                    call_id, sha256(arguments[call_id].encode()).hexdigest(), sha256(body.encode()).hexdigest(),
                ) in receipts:
                    verified_ids.add(call_id)

            projected, replaced = project_read_results(
                normalized_messages, verified_ids, self.grace, self._count,
            )
            if replaced and self._count(wire(projected)) < self._count(wire(normalized_messages)):
                return projected
        except Exception as exc:
            logger.warning("Skipping read deduplication after %s", type(exc).__name__)
        return normalized_messages
