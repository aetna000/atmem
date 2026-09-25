"""Single-attempt direct OpenAI transport for the public retail pilot only.

Independent of LiteLLM pricing/retries. No streaming, tools hosted by the provider,
fallback model, redirects, proxy, SDK retry or batch calls. Caller supplies only
public-corpus requests; files are experiment exports, NOT AtMem evidence storage.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import ssl
import time
import urllib.request
import urllib.error
import uuid

from .manifest import file_digest
from .spend import BudgetStop, SpendLedger, integer

MODEL = "gpt-4.1-2025-04-14"
PRICE = {
    "model": MODEL, "currency": "USD", "input_per_million": "2.00",
    "cached_input_per_million": "0.50", "output_per_million": "8.00",
    "source": "https://developers.openai.com/api/docs/models/gpt-4.1",
    "verified_date": "2026-09-25", "context_window": 1_047_576,
    "max_completion_tokens": 2048, "service_tier": "default",
    "upper_reserve_micro_usd": 2_200_000,
    "assumption": "standard text token billing; no hosted tools; full context upper bound plus margin",
}


def save_json(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise RuntimeError("provider redirects forbidden")


class ProviderFailure(RuntimeError):
    def __init__(self, evidence):
        super().__init__("provider response failure; see sanitized evidence")
        self.evidence = evidence


def post_openai(body: dict, api_key: str) -> dict:
    import certifi
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                         urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=json.dumps(body, allow_nan=False).encode(), method="POST",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    try:
        response = opener.open(request, timeout=90)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(16 * 1024 * 1024 + 1)
        metadata = {"http_status": response.status, "request_id": response.headers.get("x-request-id"),
                    "received_bytes": len(raw), "body_sha256": hashlib.sha256(raw).hexdigest()}
        if response.status != 200:
            try:
                details = json.loads(raw).get("error", {})
                metadata.update(error_type=details.get("type"), error_code=details.get("code"))
            except (ValueError, AttributeError):
                pass
            # Error messages/bodies can echo credentials. Retain classification,
            # correlation and digest, explicitly account for omitted raw bytes.
            metadata["raw_body_omitted"] = "provider_error_may_echo_credentials"
            raise ProviderFailure(metadata)
        if len(raw) > 16 * 1024 * 1024:
            metadata["raw_body_omitted"] = "oversized_body_limit"
            raise ProviderFailure(metadata)
        try:
            parsed = json.loads(raw)
        except ValueError:
            metadata["raw_body_omitted"] = "malformed_body_may_echo_credentials"
            raise ProviderFailure(metadata) from None
        parsed["_benchmark_http"] = metadata
        # Successful public-workload raw response; no request authentication headers.
        parsed["_benchmark_raw_response"] = raw.decode("utf-8")
        return parsed


def estimate_usage(response: dict) -> tuple[int, int, int]:
    usage = response["usage"]
    inputs = integer(usage["prompt_tokens"])
    outputs = integer(usage["completion_tokens"])
    cached = integer((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0))
    if cached > inputs:
        raise ValueError("invalid cached token count")
    # Half-micro dollars round UP. Invoice is not independently verified.
    micro = ((inputs - cached) * 4 + cached + outputs * 16 + 1) // 2
    return micro, inputs, outputs


class LoggedTransport:
    def __init__(self, ledger: SpendLedger, output: Path, api_key: str, trial_id: str,
                 *, sender=post_openai, arm='native-no-fault'):
        if arm not in {'native-no-fault', 'baseline', 'atmem', 'atflows', 'both'}:
            raise ValueError('unsupported comparison arm')
        self.ledger, self.output, self.api_key = ledger, output, api_key
        self.trial_id, self.sender = trial_id, sender
        self.arm = arm
        self.role = None
        self.calls = 0
        self.halted = None
        self.last_attempt_id = None

    def complete(self, **kwargs):
        self.last_attempt_id = None
        if self.halted is not None:
            raise BudgetStop("transport halted: " + self.halted)
        if self.role not in {"agent", "simulator", "grader"}:
            raise ValueError("unidentified model caller")
        allowed = {"model", "messages", "tools", "tool_choice", "temperature", "num_retries", "seed", "max_tokens"}
        if set(kwargs) - allowed or kwargs.get("model") != MODEL:
            raise ValueError("unapproved provider options/model")
        if kwargs.get("num_retries", 0) != 0 or kwargs.get("temperature", 0) != 0:
            raise ValueError("retries/temperature not pinned")
        if kwargs.get("max_tokens", 2048) != 2048:
            raise ValueError("unapproved output limit")
        body = {k: v for k, v in kwargs.items() if k in {"messages", "tools", "tool_choice", "seed"} and v is not None}
        body.update(model=MODEL, temperature=0, max_completion_tokens=2048, n=1,
                    stream=False, service_tier="default", store=False)
        if self.calls >= 60:
            self.halted = "call_limit"
            raise BudgetStop("trial maximum 60 model calls reached")
        attempt = str(uuid.uuid4())
        self.last_attempt_id = attempt
        request_path = self.output / f"{attempt}.request.json"
        save_json(request_path, {"attempt_id": attempt, "trial_id": self.trial_id,
                  "role": self.role, "request": body, "price": PRICE})
        # A save failure stops before dispatch. Reservation includes full model
        # context input plus maximum output, not an approximate tokenizer count.
        try:
            self.ledger.reserve(attempt, upper_micro_usd=PRICE["upper_reserve_micro_usd"],
                                trial_id=self.trial_id, arm=self.arm, role=self.role)
        except BudgetStop:
            self.halted = "budget_stopped"
            save_json(self.output / f"{attempt}.not-dispatched.json", {"attempt_id": attempt, "dispatched": False})
            raise
        self.calls += 1
        started = time.monotonic()
        try:
            response = self.sender(body, self.api_key)
            response_path = self.output / f"{attempt}.response.json"
            save_json(response_path, {"attempt_id": attempt, "latency_ms": (time.monotonic()-started)*1000,
                      "response": response})
            if response.get('model') != MODEL or response.get('service_tier') != 'default':
                raise ValueError('provider changed or omitted model/tier; cost remains unknown')
            amount, inputs, outputs = estimate_usage(response)
            self.ledger.settle(attempt, estimated_micro_usd=amount, input_tokens=inputs,
                               output_tokens=outputs, artifact_sha256=file_digest(response_path))
        except BaseException as error:
            self.halted = type(error).__name__
            save_json(self.output / f"{attempt}.failure.json", {"attempt_id": attempt,
                "error_type": type(error).__name__, "latency_ms": (time.monotonic()-started)*1000,
                "provider": getattr(error, "evidence", None)})
            # Never persist exception text: transport exceptions can expose headers.
            # If disk logging fails, the durable reservation still survives.
            if not any(e["kind"] == "settled" and e["attempt_id"] == attempt for e in self.ledger.snapshot()["events"]):
                self.ledger.settle(attempt, estimated_micro_usd=None, reason=type(error).__name__)
            raise
        response.pop("_benchmark_http", None)
        response.pop("_benchmark_raw_response", None)
        return response
