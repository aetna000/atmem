"""Pydantic AI 2.x Hooks adapter for automatic governed memory."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any

from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle, _stable_text
from atmem.control.manager import ControlPlaneManager


class PydanticAIAtMemAdapter:
    """Create a reusable Pydantic AI capability without owning agent state."""

    def __init__(
        self,
        manager: ControlPlaneManager,
        identity: AtMemAdapterIdentity,
    ) -> None:
        self.manager = manager
        self.identity = replace(identity, framework="pydantic-ai")
        self._turns: dict[str, AtMemTurnLifecycle] = {}
        self._lock = RLock()

    def capability(self) -> Any:
        """Return a native ``pydantic_ai.capabilities.Hooks`` capability."""
        try:
            from pydantic_ai.capabilities import Hooks
            from pydantic_ai.messages import ModelRequest, UserPromptPart
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "Install AtMem with `pip install 'atmem[pydantic-ai]'`"
            ) from exc

        hooks = Hooks(id="atmem-governed-memory-v1")

        @hooks.on.before_run
        async def before_run(ctx: Any) -> None:
            run_id = self._run_id(ctx)
            turn = AtMemTurnLifecycle(
                self.manager,
                replace(self.identity, run_id=run_id),
            )
            turn.begin(_prompt_text(ctx.prompt))
            with self._lock:
                self._turns[run_id] = turn

        @hooks.on.before_model_request
        async def before_model_request(ctx: Any, request_context: Any) -> Any:
            turn = self._turn(ctx)
            governed = turn.context_for_model()
            messages = list(request_context.messages)
            if governed:
                messages.append(ModelRequest(parts=[UserPromptPart(governed)]))
            model_name = str(
                request_context.model_id
                or getattr(request_context.model, "model_name", None)
                or getattr(request_context.model, "model_id", None)
                or "unknown"
            )
            turn.model_input(
                [str(message) for message in messages],
                provider=str(getattr(request_context.model, "system", "pydantic-ai")),
                model=model_name,
                history_count=len(messages),
                tools_count=len(
                    getattr(request_context.model_request_parameters, "function_tools", ())
                    or ()
                ),
            )
            return replace(request_context, messages=messages)

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
                str(getattr(call, "tool_name", None) or getattr(tool_def, "name", "tool")),
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
                str(getattr(call, "tool_name", None) or getattr(tool_def, "name", "tool")),
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
                str(getattr(call, "tool_name", None) or getattr(tool_def, "name", "tool")),
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

        return hooks

    def _run_id(self, ctx: Any) -> str:
        return str(getattr(ctx, "run_id", None) or self.identity.run_id or "pydantic-run")

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
