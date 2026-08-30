"""LangChain/LangGraph middleware for automatic governed memory."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any

from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle, _stable_text
from atmem.control.manager import ControlPlaneManager


def create_langgraph_middleware(
    manager: ControlPlaneManager,
    identity: AtMemAdapterIdentity,
) -> Any:
    """Return native middleware for LangChain agents running on LangGraph."""
    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain.messages import HumanMessage
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "Install AtMem with `pip install 'atmem[langgraph]'`"
        ) from exc

    configured = replace(identity, framework="langgraph")

    class AtMemLangGraphMiddleware(AgentMiddleware):
        """Automatic memory hooks; framework state and checkpoints stay native."""

        def __init__(self) -> None:
            super().__init__()
            self._turns: dict[str, AtMemTurnLifecycle] = {}
            self._lock = RLock()

        def before_agent(self, state: Any, runtime: Any) -> None:
            self._begin(state, runtime)
            return None

        async def abefore_agent(self, state: Any, runtime: Any) -> None:
            self._begin(state, runtime)
            return None

        def wrap_model_call(self, request: Any, handler: Any) -> Any:
            turn = self._turn(request.runtime)
            governed = turn.context_for_model()
            messages = list(request.messages)
            if governed:
                messages.append(
                    HumanMessage(
                        content=governed,
                        additional_kwargs={"atmem_governed_context": True},
                    )
                )
            model_name = _model_name(request.model)
            turn.model_input(
                [_message_value(message) for message in messages],
                provider="langchain",
                model=model_name,
                history_count=len(messages),
                tools_count=len(request.tools or ()),
            )
            try:
                response = handler(request.override(messages=messages))
            except BaseException as exc:
                turn.end(success=False, error=exc)
                raise
            turn.model_output(
                _response_value(response), provider="langchain", model=model_name
            )
            return response

        async def awrap_model_call(self, request: Any, handler: Any) -> Any:
            turn = self._turn(request.runtime)
            governed = turn.context_for_model()
            messages = list(request.messages)
            if governed:
                messages.append(
                    HumanMessage(
                        content=governed,
                        additional_kwargs={"atmem_governed_context": True},
                    )
                )
            model_name = _model_name(request.model)
            turn.model_input(
                [_message_value(message) for message in messages],
                provider="langchain",
                model=model_name,
                history_count=len(messages),
                tools_count=len(request.tools or ()),
            )
            try:
                response = await handler(request.override(messages=messages))
            except BaseException as exc:
                turn.end(success=False, error=exc)
                raise
            turn.model_output(
                _response_value(response), provider="langchain", model=model_name
            )
            return response

        def wrap_tool_call(self, request: Any, handler: Any) -> Any:
            turn = self._turn(request.runtime)
            name, call_id, arguments = _tool_call(request.tool_call)
            turn.tool_requested(name, call_id, arguments)
            try:
                result = handler(request)
            except BaseException as exc:
                turn.tool_completed(name, call_id, "", error=exc)
                raise
            turn.tool_completed(name, call_id, result)
            return result

        async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
            turn = self._turn(request.runtime)
            name, call_id, arguments = _tool_call(request.tool_call)
            turn.tool_requested(name, call_id, arguments)
            try:
                result = await handler(request)
            except BaseException as exc:
                turn.tool_completed(name, call_id, "", error=exc)
                raise
            turn.tool_completed(name, call_id, result)
            return result

        def after_agent(self, state: Any, runtime: Any) -> None:
            del state
            self._finish(runtime)
            return None

        async def aafter_agent(self, state: Any, runtime: Any) -> None:
            del state
            self._finish(runtime)
            return None

        def _begin(self, state: Any, runtime: Any) -> None:
            run_id = _runtime_run_id(runtime, configured.run_id)
            turn = AtMemTurnLifecycle(
                manager,
                replace(configured, run_id=run_id),
            )
            turn.begin(_latest_user_text(state))
            with self._lock:
                self._turns[run_id] = turn

        def _turn(self, runtime: Any) -> AtMemTurnLifecycle:
            run_id = _runtime_run_id(runtime, configured.run_id)
            with self._lock:
                turn = self._turns.get(run_id)
            if turn is None:
                raise RuntimeError("AtMem LangGraph before_agent hook did not initialize")
            return turn

        def _finish(self, runtime: Any) -> None:
            run_id = _runtime_run_id(runtime, configured.run_id)
            with self._lock:
                turn = self._turns.pop(run_id, None)
            if turn is not None:
                turn.end(success=not turn.ended)

    return AtMemLangGraphMiddleware()


def _runtime_run_id(runtime: Any, fallback: str | None) -> str:
    execution = getattr(runtime, "execution_info", None)
    value = getattr(execution, "run_id", None)
    if value:
        return str(value)
    config = getattr(runtime, "config", None) or {}
    configurable = config.get("configurable") if isinstance(config, dict) else {}
    if isinstance(configurable, dict) and configurable.get("thread_id"):
        return str(configurable["thread_id"])
    return str(fallback or "langgraph-run")


def _latest_user_text(state: Any) -> str:
    messages = state.get("messages", ()) if isinstance(state, dict) else ()
    for message in reversed(list(messages)):
        role = str(getattr(message, "type", None) or getattr(message, "role", None) or "")
        if role in {"human", "user"}:
            return _message_value(message)
        if isinstance(message, dict) and str(message.get("role")) == "user":
            return _message_value(message)
    raise ValueError("LangGraph state has no authenticated user message")


def _message_value(message: Any) -> str:
    if isinstance(message, dict):
        return _stable_text(message.get("content", ""))
    return _stable_text(getattr(message, "content", message))


def _model_name(model: Any) -> str:
    return str(
        getattr(model, "model_name", None)
        or getattr(model, "model", None)
        or getattr(model, "_llm_type", None)
        or type(model).__name__
    )


def _response_value(response: Any) -> Any:
    result = getattr(response, "result", None)
    return result if result is not None else response


def _tool_call(value: Any) -> tuple[str, str, Any]:
    if isinstance(value, dict):
        name = str(value.get("name") or "tool")
        call_id = str(value.get("id") or f"tool_{id(value)}")
        return name, call_id, value.get("args") or {}
    name = str(getattr(value, "name", None) or "tool")
    call_id = str(getattr(value, "id", None) or f"tool_{id(value)}")
    return name, call_id, getattr(value, "args", {}) or {}
