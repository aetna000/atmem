"""OpenAI-compatible DolphinBench agent loop used by the AtMem adapter."""

from __future__ import annotations

import json
import os
import time
from typing import Any
import urllib.error
import urllib.request


def _value(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        candidate = getattr(value, name, None)
        if candidate is not None:
            return candidate
    return default


def _tool_definition(tool: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": str(_value(tool, "name")),
            "description": str(_value(tool, "description", default="")),
            "parameters": _value(
                tool, "inputSchema", "input_schema", default={"type": "object"}
            ),
        },
    }


def _tool_result(value: Any) -> str:
    content = _value(value, "content", default=value)
    if isinstance(content, str):
        return content
    rows: list[Any] = []
    if isinstance(content, (list, tuple)):
        for item in content:
            text = _value(item, "text")
            rows.append(text if text is not None else item)
    else:
        rows.append(content)
    return json.dumps(rows, ensure_ascii=False, default=str)


def _structured_tool_result(value: Any) -> Any:
    """Recover the MCP result object without changing model-supplied arguments."""
    content = _value(value, "content", default=value)
    items = list(content) if isinstance(content, (list, tuple)) else [content]
    decoded: list[Any] = []
    for item in items:
        text = _value(item, "text")
        candidate = text if text is not None else item
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                pass
        decoded.append(candidate)
    return decoded[0] if len(decoded) == 1 else decoded


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    base_url = os.environ["ATMEM_DOLPHIN_AGENT_BASE_URL"].rstrip("/")
    request = urllib.request.Request(
        base_url + "/chat/completions",
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["ATMEM_DOLPHIN_AGENT_API_KEY"],
            "Content-Type": "application/json",
            "User-Agent": "OpenAI/Python 3.19.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2_000]
        raise RuntimeError(
            f"Dolphin agent provider returned HTTP {exc.code}: {detail}"
        ) from exc


async def run(*, request, tools, call_app, memory_context: str, model: str,
              max_cost_usd: float):
    from harness.adapter import InteractionRecord

    started = time.monotonic()
    tool_definitions = [_tool_definition(tool) for tool in tools]
    messages: list[dict[str, Any]] = [{
        "role": "system",
        "content": (
            "You are an action agent in a simulated personal workspace. Use the "
            "available tools whenever the request requires an app action. Treat "
            "the supplied memory as authoritative user-specific evidence. Before "
            "acting, identify every explicit part of the request and preserve all "
            "directly relevant memory details in the action: exact people and "
            "addresses, ownership or role relations, conditions and exceptions, "
            "ordered steps, complete enumerations, polarity, and current state. "
            "Resolve indirect references such as usual recipient or CEO from the "
            "evidence, including adjacent name/role statements; never substitute "
            "an unsupported identity. If the request asks you to contact someone "
            "for information, send that request when the recipient is known rather "
            "than asking the user to provide the requested information. Do not "
            "claim an action succeeded unless its tool result confirms it.\n\n"
            "AtMem memory:\n"
            + (memory_context or "No relevant memory was retrieved.")
        ),
    }, {"role": "user", "content": request.dated_message}]
    recorded = list(messages)
    app_calls: list[dict[str, Any]] = []
    prompt_tokens = 0
    completion_tokens = 0
    finish_reason = ""
    for _ in range(8):
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 4096,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tool_definitions:
            payload["tools"] = tool_definitions
            payload["tool_choice"] = "auto"
        response = _post(payload)
        choices = response.get("choices") or []
        if len(choices) != 1:
            raise RuntimeError("Dolphin agent returned an invalid choice count")
        choice = choices[0]
        provider_message = dict(choice.get("message") or {})
        message = {
            "role": str(provider_message.get("role") or "assistant"),
            "content": provider_message.get("content"),
        }
        raw_calls = list(provider_message.get("tool_calls") or ())
        if raw_calls:
            message["tool_calls"] = raw_calls
        usage = dict(response.get("usage") or {})
        if int(usage.get("prompt_tokens") or 0) <= 0 or int(
            usage.get("completion_tokens") or 0
        ) <= 0:
            raise RuntimeError("Dolphin agent response lacks token usage")
        prompt_tokens += int(usage["prompt_tokens"])
        completion_tokens += int(usage["completion_tokens"])
        recorded_message = {
            "role": message["role"],
            "content": message.get("content"),
            "usage": {
                "input_tokens": int(usage["prompt_tokens"]),
                "output_tokens": int(usage["completion_tokens"]),
            },
        }
        if raw_calls:
            recorded_message["tool_calls"] = [{
                "id": str(call.get("id") or ""),
                "name": str((call.get("function") or {}).get("name") or ""),
                "arguments": json.loads(
                    str((call.get("function") or {}).get("arguments") or "{}")
                ),
            } for call in raw_calls]
        finish_reason = str(choice.get("finish_reason") or "")
        recorded.append(recorded_message)
        messages.append(message)
        calls = raw_calls
        if not calls:
            if finish_reason != "stop" or not str(message.get("content") or "").strip():
                raise RuntimeError("Dolphin agent did not return a complete final answer")
            break
        for call in calls:
            function = dict(call.get("function") or {})
            name = str(function.get("name") or "")
            arguments = json.loads(str(function.get("arguments") or "{}"))
            result = await call_app(name, arguments)
            content = _tool_result(result)
            app_calls.append({
                "tool": name,
                "args": arguments,
                "result": _structured_tool_result(result),
            })
            tool_message = {
                "role": "tool",
                "tool_call_id": str(call.get("id") or ""),
                "content": content,
            }
            messages.append(tool_message)
            recorded.append(tool_message)
    else:
        raise RuntimeError("Dolphin agent exceeded the eight-turn tool bound")

    duration_ms = (time.monotonic() - started) * 1000
    usd_per_hour = float(os.environ.get("ATMEM_DOLPHIN_GPU_USD_PER_HOUR", "1.59"))
    cost = duration_ms / 3_600_000 * usd_per_hour
    if cost > max_cost_usd:
        raise RuntimeError("Dolphin agent interaction exceeded its cost cap")
    attempt = {
        "driver_ok": True,
        "error": None,
        "cost_usd": cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    return InteractionRecord(
        settings={
            "model": model,
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 4096,
        },
        messages=recorded,
        duration_ms=duration_ms,
        attempts=[attempt],
        # Preserve the exact arguments exposed to the model while retaining
        # the MCP server's structured result.  Server-side validation may add
        # optional defaults to its JSONL arguments, which no longer match the
        # conversation boundary required by the official submission validator.
        app_calls=app_calls,
    )
