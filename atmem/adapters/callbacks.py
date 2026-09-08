"""Small host-neutral callback binding used by optional framework adapters."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any

from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle, _stable_text
from atmem.control.manager import ControlPlaneManager


class CallbackAtMemAdapter:
    """Map native framework callbacks onto the authoritative AtMem lifecycle.

    Framework packages can wrap these methods in their native hook objects.  The
    class deliberately owns no framework state and never imports an optional SDK.
    """

    def __init__(self, manager: ControlPlaneManager, identity: AtMemAdapterIdentity, *, framework: str) -> None:
        self.manager = manager
        self.identity = replace(identity, framework=framework)
        self.framework = framework
        self._turns: dict[str, AtMemTurnLifecycle] = {}
        self._lock = RLock()

    def begin(self, run_id: str, user_text: str, **identity: str | None) -> None:
        turn = AtMemTurnLifecycle(
            self.manager,
            self.identity.for_execution(run_id=run_id, **identity),
        )
        turn.begin(user_text)
        with self._lock:
            if run_id in self._turns:
                raise RuntimeError(f"duplicate active framework run: {run_id}")
            self._turns[run_id] = turn

    def model_input(self, run_id: str, messages: list[Any], *, provider: str | None = None, model: str = "unknown") -> list[Any]:
        turn = self._turn(run_id)
        context = turn.context_for_model()
        task_context = turn.task_context_for_model()
        result = list(messages)
        segments: list[str] = [_stable_text(value) for value in result]
        for value in (context, task_context):
            if value:
                result.append(value)
                segments.append(value)
        turn.model_input(
            result,
            context_segments=segments,
            context_location=f"{self.framework}:model-input",
            provider=provider or self.framework,
            model=model,
            history_count=len(result),
        )
        return result

    def model_output(self, run_id: str, response: Any, *, provider: str | None = None, model: str = "unknown") -> Any:
        self._turn(run_id).model_output(response, provider=provider or self.framework, model=model)
        return response

    def tool_requested(self, run_id: str, name: str, call_id: str, arguments: Any) -> None:
        self._turn(run_id).tool_requested(name, call_id, arguments)

    def tool_completed(self, run_id: str, name: str, call_id: str, result: Any, *, error: BaseException | None = None) -> None:
        self._turn(run_id).tool_completed(name, call_id, result, error=error)

    def finish(self, run_id: str, *, error: BaseException | None = None, cancelled: bool = False) -> None:
        with self._lock:
            turn = self._turns.pop(run_id, None)
        if turn is not None:
            turn.end(success=error is None and not cancelled, error=error, cancelled=cancelled)

    def _turn(self, run_id: str) -> AtMemTurnLifecycle:
        with self._lock:
            turn = self._turns.get(run_id)
        if turn is None:
            raise RuntimeError(f"AtMem {self.framework} run hook did not initialize")
        return turn


def callback_adapter(manager: ControlPlaneManager, identity: AtMemAdapterIdentity, framework: str) -> CallbackAtMemAdapter:
    return CallbackAtMemAdapter(manager, identity, framework=framework)
