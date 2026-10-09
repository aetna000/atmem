"""Credentialed minimal route probe; stores no model response content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import threading
import urllib.error
import urllib.request

from http.server import ThreadingHTTPServer

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.production_benchmarks.local_embedding_proxy import Handler, MODEL as EMBEDDING_MODEL

def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def request(
    url: str, token: str, body: dict, *, provider_route: str
) -> dict:
    started = time.monotonic()
    call = urllib.request.Request(
        url,
        data=canonical(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            # RunPod's edge rejects urllib's default user agent (HTTP 403/1010).
            # Match the paid reader proxy so this probe exercises the same route.
            "User-Agent": "OpenAI/Python 3.19.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(call, timeout=120) as response:
            value = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"route probe failed with HTTP {exc.code}: {detail}") from exc
    usage = value.get("usage") or {}
    return {
        "outcome": "succeeded",
        "status": status,
        "model": value.get("model"),
        "provider_route": provider_route,
        "response_id_sha256": hashlib.sha256(str(value.get("id") or "").encode()).hexdigest(),
        "usage": {
            key: usage.get(key) for key in (
                "prompt_tokens", "completion_tokens", "total_tokens",
                "input_tokens", "output_tokens",
            ) if usage.get(key) is not None
        },
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "content_retained": False,
    }


def embedding_request() -> dict:
    """Probe the exact content-blind local route shared by comparator arms."""
    started = time.monotonic()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    call = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/v1/embeddings",
        data=canonical({
            "model": EMBEDDING_MODEL,
            "input": "route probe",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        try:
            with urllib.request.urlopen(call, timeout=120) as response:
                value = json.loads(response.read())
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"embedding route probe failed with HTTP {exc.code}: {detail}"
            ) from exc
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    vectors = value.get("data") or []
    if len(vectors) != 1 or not isinstance(vectors[0].get("embedding"), list):
        raise RuntimeError("embedding route returned an unexpected OpenAI-compatible payload")
    return {
        "outcome": "succeeded",
        "status": status,
        "model": EMBEDDING_MODEL,
        "provider_route": "local-deterministic",
        "transport": "openai-compatible-v1-embeddings",
        "shape": [1, len(vectors[0]["embedding"])],
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "content_retained": False,
    }


def probe(name: str, operation) -> dict:
    started = time.monotonic()
    try:
        return operation()
    except Exception as exc:  # Evidence must survive a provider failure.
        return {
            "outcome": "failed",
            "error_type": type(exc).__name__,
            "error_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
            "route": name,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "content_retained": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm-paid-call", action="store_true")
    parser.add_argument(
        "--reader-base-url",
        default=os.environ.get("ATMEM_RUNPOD_READER_URL", ""),
    )
    args = parser.parse_args()
    if not args.confirm_paid_call:
        raise SystemExit("refusing provider calls without --confirm-paid-call")
    reader_key = os.environ.get("RUNPOD_READER_API_KEY")
    openai = os.environ.get("OPENAI_API_KEY")
    if not args.reader_base_url or not reader_key or not openai:
        raise SystemExit(
            "--reader-base-url, RUNPOD_READER_API_KEY and OPENAI_API_KEY are required"
        )
    output = Path(args.output).expanduser().resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise SystemExit("route-probe evidence must be written outside the repository")
    result = {
        "format": "atmem-provider-route-probe-v1",
        "routes": {
            "reader": probe(
                "runpod/Qwen3.5-9B",
                lambda: request(
                    args.reader_base_url.rstrip("/") + "/chat/completions", reader_key,
                    {"model": "Qwen/Qwen3.5-9B", "messages": [{"role": "user", "content": "Reply OK."}], "max_tokens": 8},
                    provider_route="runpod-vllm",
                ),
            ),
            "embedding": probe(
                "local/hash-bow-768-v1",
                embedding_request,
            ),
            "judge": probe(
                "openai/gpt-5.2-2025-12-11",
                lambda: request(
                    "https://api.openai.com/v1/responses", openai,
                    {"model": "gpt-5.2-2025-12-11", "input": "Reply OK.", "reasoning": {"effort": "medium"}, "max_output_tokens": 16},
                    provider_route="openai-direct",
                ),
            ),
        },
    }
    result["probe_sha256"] = hashlib.sha256(canonical(result).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "format": result["format"], "probe_sha256": result["probe_sha256"],
        "output": str(output), "content_retained": False,
    }))
    failures = [name for name, row in result["routes"].items() if row["outcome"] != "succeeded"]
    if failures:
        raise SystemExit(f"provider route probe failed for: {', '.join(failures)}; evidence was retained")


if __name__ == "__main__":
    main()
