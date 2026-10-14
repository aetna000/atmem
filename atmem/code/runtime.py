"""Host-neutral automatic recall/capture choreography for enabled turns."""

from __future__ import annotations

from hashlib import sha256

from atmem.code.context import build_context
from atmem.code.contracts import CodeContextPackage, CodeContextRequest, CodeObservation
from atmem.code.formation import CodeFormation
from atmem.code.service import CodeIntakeService
from atmem.memory import Memory


class CodeRuntime:
    def __init__(self, memory: Memory, intake: CodeIntakeService) -> None:
        if memory.store is not intake.store:
            raise ValueError("Code runtime and intake must share one canonical store")
        self.memory = memory
        self.intake = intake
        self.formation = CodeFormation(memory)

    def process_pending(self, *, limit: int = 100) -> list[dict]:
        results: list[dict] = []
        for observation in self.intake.pending(limit):
            with self.memory.store.transaction():
                self.intake.assert_active()
                # Recheck queue state under the write lock, then atomically
                # commit formation and queue disposition. Retrying after a
                # crash cannot create a second canonical record.
                rows = self.memory.store.list_code_observations(
                    subject_id=observation.scope.subject_id,
                    project_id=observation.scope.project_id,
                    profile_id=observation.scope.profile_id,
                    agent_id=observation.scope.agent_id,
                    state="pending", limit=500,
                )
                if not any(row["event_id"] == observation.event_id for row in rows):
                    continue
                result = self.formation.form(observation)
                self.memory.store.set_code_observation_state(
                    observation.event_id, "formed" if result["formed"] else "refused"
                )
                results.append(result)
        return results

    def on_user_turn(
        self, request: CodeContextRequest, observation: CodeObservation,
        signature: str,
    ) -> dict:
        if request.scope != self.intake.scope or observation.scope != request.scope:
            raise PermissionError("Code turn scope mismatch")
        if request.session_id != observation.session_id or request.turn_id != observation.turn_id:
            raise PermissionError("Code turn binding mismatch")
        if observation.kind != "user_turn":
            raise ValueError("on_user_turn requires a user_turn observation")
        with self.memory.store.transaction():
            try:
                self.intake.assert_active()
            except PermissionError:
                # The host hook stays installed while Code is paused. Return a
                # neutral package so it injects nothing and captures nothing.
                empty = CodeContextPackage(
                    request.request_id, "", sha256(b"").hexdigest(), (),
                )
                return {"context": empty,
                        "capture": {"accepted": False, "reason": "disabled"},
                        "formation": []}
            # Recall precedes capture: this turn cannot manufacture its own
            # recalled evidence, matching Mem0 Code's first-prompt ordering.
            context = build_context(self.memory, request)
            capture = self.intake.submit(observation.to_dict(), signature)
            formation = self.process_pending() if capture["accepted"] else []
            return {"context": context, "capture": capture, "formation": formation}
