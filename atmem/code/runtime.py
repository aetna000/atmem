"""Host-neutral automatic recall/capture choreography for enabled turns."""

from __future__ import annotations

from hashlib import sha256

from atmem.code.context import build_context
from atmem.code.contracts import CodeContextPackage, CodeContextRequest, CodeObservation
from atmem.code.formation import CodeFormation
from atmem.code.service import CodeIntakeService
from atmem.code.receipts import CodeReceipts
from atmem.code.application import DEFAULT_SETTINGS
from atmem.code.application import digest
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
                settings = self.memory.store.code_document(observation.scope.subject_id, observation.scope.project_id, "settings", "effective") or {}
                if not settings.get("auto_capture", True):
                    continue
                if settings.get("review_workflow", False):
                    self.memory.store.put_code_document(observation.scope.subject_id, observation.scope.project_id,
                                                         "review", observation.event_id, observation.to_dict())
                    results.append({"event_id": observation.event_id, "formed": False, "review_required": True})
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
        *, tags: tuple[str, ...] = (), repository_root: str | None = None,
    ) -> dict:
        if request.scope != self.intake.scope or observation.scope != request.scope:
            raise PermissionError("Code turn scope mismatch")
        if request.session_id != observation.session_id or request.turn_id != observation.turn_id:
            raise PermissionError("Code turn binding mismatch")
        if observation.kind != "user_turn":
            raise ValueError("on_user_turn requires a user_turn observation")
        self.intake.authenticate(observation, signature)
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
            from atmem.extract.validation import screen_content
            from atmem.memory import _screenable_metadata
            if any(not screen_content(value, trusted=True).admissible
                   for value in _screenable_metadata({"request": request.to_dict(), "observation": observation.to_dict()})):
                return {"context": CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ()),
                        "capture": {"accepted": False, "reason": "secret_screen"}, "formation": []}
            # Recall precedes capture: this turn cannot manufacture its own
            # recalled evidence, matching Mem0 Code's first-prompt ordering.
            settings = {**DEFAULT_SETTINGS, **(self.memory.store.code_document(
                request.scope.subject_id, request.scope.project_id, "settings", "effective") or {})}
            effective_tags = tags or tuple(settings["context_tags"])
            replay_key = digest([request.to_dict(), observation.to_dict(), list(effective_tags)])
            previous = self.memory.store.code_document(request.scope.subject_id, request.scope.project_id, "turn-result", request.request_id)
            if previous is not None:
                if previous["input_sha256"] != replay_key:
                    raise ValueError("turn request ID replay conflict")
                saved = previous["context"]
                from atmem.code.formation import memory_subject_id
                from atmem.code.context import source_current
                live = all((record := self.memory.store.get_record(memory_subject_id(request.scope), record_id))
                           is not None and record["status"] == "active" and source_current(self.memory.store, request, record, repository_root)
                           for record_id in saved["memory_ids"])
                unchanged = previous.get("settings_sha256") == digest(settings)
                context = (CodeContextPackage(saved["request_id"], saved["content"], saved["content_sha256"], tuple(saved["memory_ids"]))
                           if live and unchanged and settings["auto_recall"] else CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ()))
                return {"context": context, "capture": {**previous.get("capture", {}), "queued": False, "replayed": True},
                        "formation": [], "exposure": previous["exposure"]}
            from dataclasses import replace
            bounded = replace(request, max_context_bytes=min(request.max_context_bytes, settings["max_context_bytes"]))
            route = None
            if settings["auto_recall"] and effective_tags:
                from atmem.code.providers import CodeRouter
                from atmem.code.application import CodeApplication
                route = CodeRouter(CodeApplication(self.memory, subject_id=request.scope.subject_id)).prepare(bounded, tags=effective_tags, repository_root=repository_root)
            context = ((route["package"] if route else build_context(self.memory, bounded, repository_root=repository_root)) if settings["auto_recall"] else
                       CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ()))
            graph_evidence = None
            if settings["auto_recall"] and settings["graph_enabled"] and repository_root and (not route or route["authority"] in {"atmem", "atmem_fallback"}):
                from atmem.code.graph import CodeGraph
                from atmem.code.application import CodeApplication
                from atmem.knowledge.projections import CodeKnowledge
                app = CodeApplication(self.memory, subject_id=request.scope.subject_id)
                knowledge = CodeKnowledge(app, request.scope)
                # Prefer the incorporated richer projection when current. The
                # pre-existing syntax fallback remains explicitly labelled.
                if knowledge.current(repository_root) is not None:
                    graph_context = knowledge.context(repository_root, request.task,
                                                      budget=bounded.max_context_bytes - len(context.content.encode()))
                else:
                    graph_context = CodeGraph(app, request.scope.project_id).context(
                        repository_root, request.task, budget=bounded.max_context_bytes - len(context.content.encode()))
                if graph_context["content"]:
                    content = context.content + graph_context["content"]
                    context = CodeContextPackage(context.request_id, content, sha256(content.encode()).hexdigest(), context.memory_ids)
                    graph_evidence = graph_context["evidence"]
            evidence = CodeReceipts(self.memory.store).prepare(bounded, context, host=self.intake.host, graph_evidence=graph_evidence,
                                                              repository_root=repository_root)
            capture = (self.intake.submit(observation.to_dict(), signature) if settings["auto_capture"] else
                       {"accepted": False, "reason": "auto_capture_disabled"})
            formation = self.process_pending() if capture["accepted"] else []
            self.memory.store.put_code_document(request.scope.subject_id, request.scope.project_id, "turn-result", request.request_id,
                                                 {"input_sha256": replay_key, "settings_sha256": digest(settings), "context": context.to_dict(), "exposure": evidence, "capture": capture})
            return {"context": context, "capture": capture, "formation": formation, "exposure": evidence}
