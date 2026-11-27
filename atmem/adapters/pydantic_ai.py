"""Pydantic AI Hooks adapter for automatic governed memory."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any

from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle, _stable_text
from atmem.context_engine.read_deduplication import ReadDeduplication, normalized_call
from atmem.control.manager import ControlPlaneManager


class PydanticAIAtMemAdapter:
    """Create a reusable Pydantic AI capability without owning agent state."""

    def __init__(
        self,
        manager: ControlPlaneManager,
        identity: AtMemAdapterIdentity,
        *,
        read_deduplication: ReadDeduplication | None = None,
    ) -> None:
        self.manager = manager
        self.read_deduplication = read_deduplication
        self.identity = replace(identity, framework="pydantic-ai")
        self._turns: dict[str, AtMemTurnLifecycle] = {}
        self._lock = RLock()

    def capability(self) -> Any:
        """Return a native Pydantic AI capability."""
        try:
            from pydantic_ai.capabilities import AbstractCapability, CombinedCapability, Hooks
            from pydantic_ai.messages import ModelRequest, UserPromptPart
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "Install AtMem with `pip install 'atmem[pydantic-ai]'`"
            ) from exc

        hooks = Hooks(id="atmem-governed-memory-v1")

        @hooks.on.before_run
        async def before_run(ctx: Any) -> None:
            run_id = self._run_id(ctx)
            runtime_identity = _pydantic_execution_identity(ctx)
            turn = AtMemTurnLifecycle(
                self.manager,
                self.identity.for_execution(
                    run_id=run_id,
                    turn_id=runtime_identity.get("turn_id"),
                    task_id=runtime_identity.get("task_id"),
                    session_id=runtime_identity.get("session_id"),
                    user_id=runtime_identity.get("user_id"),
                ),
            )
            turn.begin(_prompt_text(ctx.prompt))
            with self._lock:
                self._turns[run_id] = turn

        def prepare_model_input(ctx: Any, request_context: Any) -> Any:
            turn = self._turn(ctx)
            governed = turn.context_for_model()
            task_governed = turn.task_context_for_model()
            messages = list(request_context.messages)
            if self.read_deduplication is not None:
                messages = project_pydantic_messages(messages, ctx, self.read_deduplication)
            additions = [UserPromptPart(text) for text in (governed, task_governed) if text]
            if additions and self.read_deduplication is not None and messages and isinstance(messages[-1], ModelRequest):
                last = messages[-1]
                messages[-1] = replace(last, parts=[*last.parts, *additions])
            else:
                messages.extend(ModelRequest(parts=[part]) for part in additions)
            model_name = str(
                getattr(request_context, "model_id", None)
                or getattr(request_context.model, "model_name", None)
                or getattr(request_context.model, "model_id", None)
                or "unknown"
            )
            turn.model_input(
                [str(message) for message in messages],
                context_segments=_message_segments(messages),
                context_location="pydantic-ai:user-prompt-part",
                provider=str(getattr(request_context.model, "system", "pydantic-ai")),
                model=model_name,
                history_count=len(messages),
                tools_count=len(
                    getattr(
                        request_context.model_request_parameters, "function_tools", ()
                    )
                    or ()
                ),
            )
            return replace(request_context, messages=messages)

        @hooks.on.before_model_request
        async def before_model_request(ctx: Any, request_context: Any) -> Any:
            if self.read_deduplication is None:
                return prepare_model_input(ctx, request_context)
            return request_context

        class ProjectModelInput(AbstractCapability):
            async def wrap_model_request(self, ctx, *, request_context, handler):
                return await handler(prepare_model_input(ctx, request_context))

        @hooks.on.after_model_request
        async def after_model_request(
            ctx: Any, *, request_context: Any, response: Any
        ) -> Any:
            self._turn(ctx).model_output(
                response,
                provider=str(getattr(response, "provider_name", None) or "pydantic-ai"),
                model=str(
                    getattr(response, "model_name", None)
                    or getattr(request_context, "model_id", None)
                    or "unknown"
                ),
            )
            return response

        @hooks.on.before_tool_execute
        async def before_tool_execute(
            ctx: Any, *, call: Any, tool_def: Any, args: Any
        ) -> Any:
            self._turn(ctx).tool_requested(
                str(
                    getattr(call, "tool_name", None)
                    or getattr(tool_def, "name", "tool")
                ),
                str(getattr(call, "tool_call_id", None) or f"tool_{id(call)}"),
                args,
            )
            return args

        @hooks.on.after_tool_execute
        async def after_tool_execute(
            ctx: Any,
            *,
            call: Any,
            tool_def: Any,
            args: Any,
            result: Any,
        ) -> Any:
            del args
            self._turn(ctx).tool_completed(
                str(
                    getattr(call, "tool_name", None)
                    or getattr(tool_def, "name", "tool")
                ),
                str(getattr(call, "tool_call_id", None) or f"tool_{id(call)}"),
                result,
            )
            return result

        @hooks.on.tool_execute_error
        async def tool_execute_error(
            ctx: Any,
            *,
            call: Any,
            tool_def: Any,
            args: Any,
            error: Exception,
        ) -> Any:
            del args
            self._turn(ctx).tool_completed(
                str(
                    getattr(call, "tool_name", None)
                    or getattr(tool_def, "name", "tool")
                ),
                str(getattr(call, "tool_call_id", None) or f"tool_{id(call)}"),
                "",
                error=error,
            )
            raise error

        @hooks.on.after_run
        async def after_run(ctx: Any, *, result: Any) -> Any:
            run_id = self._run_id(ctx)
            turn = self._turn(ctx)
            turn.end(success=True)
            with self._lock:
                self._turns.pop(run_id, None)
            return result

        @hooks.on.run_error
        async def run_error(ctx: Any, *, error: BaseException) -> Any:
            run_id = self._run_id(ctx)
            turn = self._turns.get(run_id)
            if turn is not None:
                turn.end(success=False, error=error)
            with self._lock:
                self._turns.pop(run_id, None)
            raise error

        if self.read_deduplication is not None:
            return CombinedCapability([hooks, ProjectModelInput()])
        return hooks

    def _run_id(self, ctx: Any) -> str:
        return str(
            getattr(ctx, "run_id", None) or self.identity.run_id or "pydantic-run"
        )

    def _turn(self, ctx: Any) -> AtMemTurnLifecycle:
        run_id = self._run_id(ctx)
        with self._lock:
            turn = self._turns.get(run_id)
        if turn is None:
            raise RuntimeError("AtMem Pydantic AI run hook did not initialize")
        return turn


def _prompt_text(prompt: Any) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, (list, tuple)):
        text = " ".join(
            str(getattr(item, "content", item))
            for item in prompt
            if isinstance(getattr(item, "content", item), str)
        )
        if text.strip():
            return text
    return _stable_text(prompt)


def _message_segments(messages: list[Any]) -> list[str]:
    """Return model-visible textual parts without rewriting their contents."""
    segments: list[str] = []
    for message in messages:
        for part in getattr(message, "parts", ()) or ():
            content = getattr(part, "content", None)
            if isinstance(content, str):
                segments.append(content)
    return segments


def _pydantic_execution_identity(ctx: Any) -> dict[str, str]:
    """Read optional identity from native run dependencies without mutation."""
    deps = getattr(ctx, "deps", None)
    values: dict[str, Any] = deps if isinstance(deps, dict) else {}

    def read(*names: str) -> str | None:
        for name in names:
            value = values.get(name) if values else getattr(deps, name, None)
            if value is not None and str(value).strip():
                return str(value)
        return None

    return {
        key: value
        for key, value in {
            "task_id": read("atmem_task_id", "task_id"),
            "turn_id": read("atmem_turn_id", "turn_id"),
            "session_id": read("atmem_session_id", "session_id"),
            "user_id": read("atmem_authenticated_user_id"),
        }.items()
        if value
    }


def project_pydantic_messages(messages, runtime, policy: ReadDeduplication):
    """Project a Pydantic AI request while preserving its original parts."""
    from pydantic_ai.messages import (
        ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart, UserPromptPart,
    )

    normalized = []
    result_parts = {}
    for index, message in enumerate(messages):
        if isinstance(message, ModelResponse):
            calls = [normalized_call(p.tool_call_id, p.tool_name, p.args)
                     for p in message.parts if isinstance(p, ToolCallPart)]
            normalized.append({"role": "assistant", "tool_calls": calls})
        elif isinstance(message, ModelRequest):
            for part_index, part in enumerate(message.parts):
                if isinstance(part, (ToolReturnPart, RetryPromptPart)) and part.tool_call_id:
                    entry = {"role": "tool", "tool_call_id": part.tool_call_id}
                    if (isinstance(part, ToolReturnPart) and getattr(part, "outcome", None) == "success"
                        and isinstance(part.content, str)):
                        entry["content"] = part.content
                        result_parts[len(normalized)] = (index, part_index)
                    normalized.append(entry)
                else:
                    normalized.append({"role": "user" if isinstance(part, UserPromptPart) else "other"})
        else:
            normalized.append({"role": "other"})

    projected = policy.project(runtime, messages, normalized)
    updated = list(messages)
    for position, (index, part_index) in result_parts.items():
        if projected[position] is normalized[position]:
            continue
        parts = list(updated[index].parts)
        parts[part_index] = replace(parts[part_index], content=projected[position]["content"])
        updated[index] = replace(updated[index], parts=parts)
    return updated
