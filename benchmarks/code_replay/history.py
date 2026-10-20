"""Arm-local product bridge. No labeler, memory engine or oracle lessons."""
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import time

from atmem.code.application import CodeApplication
from atmem.code.contracts import CodeContextRequest, CodeObservation
from atmem.code.experience import CodeExperience
from atmem.code.identity import CodeIdentity
from atmem.code.runtime import CodeRuntime
from atmem.code.service import CodeIntakeService
from atmem.core.canonical import canonical_json
from atmem.knowledge.contracts import ExperienceProposal, SourceAnchor, SourceSnapshot
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.applicability import assess
from atmem.knowledge.worker import ExtractionWorker


class ProductLane:
    """Only an isolated, explicit benchmark installation; not normal hooks."""
    def __init__(self, memory, root, *, environment_sha256, experience):
        self.memory, self.root, self.experience_enabled = memory, Path(root), experience
        self.scope = CodeIdentity(memory.store).resolve(root, subject_id="benchmark-operator", profile_id="shared", agent_id="codex")
        self.app = CodeApplication(memory, subject_id="benchmark-operator")
        self.app.settings(self.scope.project_id, {"graph_enabled": True, "max_context_bytes": 8192,
                                                "auto_capture": False, "review_workflow": False})
        memory.store.put_code_installation(subject_id=self.scope.subject_id, project_id=self.scope.project_id, host="codex", enabled=True)
        self.secret = os.urandom(32)
        self.experiences = CodeExperience(self.app, self.scope, producer_keys={"benchmark-supervisor": self.secret},
                                          environment_sha256=environment_sha256)
        self.knowledge = CodeKnowledge(self.app, self.scope)

    def prepare(self, *, run_id, task, image_id, max_context_bytes=8192):
        start = time.monotonic()
        indexed = self.knowledge.index(str(self.root), ExtractionWorker(image_id))
        index_ms = int((time.monotonic() - start) * 1000)
        if self.experience_enabled:
            current, _, _ = self.experiences.capture_snapshot(str(self.root))
            previous = self.memory.store.code_documents(self.scope.subject_id, self.scope.project_id, "code-experience")
        else:
            # Structure-only does not issue execution receipts or assess lessons.
            # Use the covered graph identity for the turn's revision, never
            # relabel it as a complete execution-source identity.
            generation = self.knowledge.current(str(self.root))
            if generation is None:
                raise ValueError("structural source changed before context preparation")
            current = SourceSnapshot.from_dict(generation["snapshot"])
            previous = []
        applicable = []
        for value in previous:
            proposal = ExperienceProposal.from_dict(value["proposal"])
            result = assess(proposal, SourceSnapshot.from_dict(value["snapshot"]), current)
            applicable.append(result.to_dict())
        intake = CodeIntakeService(self.memory.store, scope=self.scope, host="codex", session_id=run_id,
                                   secret=self.secret, enabled=True)
        request = CodeContextRequest(run_id, run_id, "task-start", task, max_context_bytes, self.scope)
        observation = CodeObservation(run_id, run_id, "task-start", "codex", "user_turn", task,
                                      "2026-10-17T00:00:00Z", "benchmark:permitted-task", current.revision, self.scope)
        start = time.monotonic()
        prepared = CodeRuntime(self.memory, intake).on_user_turn(request, observation, intake.sign(observation), repository_root=str(self.root))
        context_ms = int((time.monotonic() - start) * 1000)
        if prepared["capture"]["accepted"]:
            raise RuntimeError("task requirements must not become experience")
        return {"request": request, "package": prepared["context"], "exposure": prepared["exposure"],
                "index": indexed, "index_ms": index_ms, "context_ms": context_ms,
                "previous_candidates": len(previous), "applicability": applicable,
                "state_identity": "strict_execution_source" if self.experience_enabled else "covered_structure_source"}

    def capture_report(self, run_id, task_title, events, changed_paths):
        if not self.experience_enabled:
            return {"candidates": 0, "admitted": 0, "reason": "structure_only"}
        report = None
        for event in events:
            if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
                try:
                    value = json.loads(event["item"]["text"])
                except (ValueError, KeyError):
                    continue
                if type(value) is dict and set(value) == {"summary", "paths"} and isinstance(value["summary"], str):
                    report = value
        if report is None:
            return {"candidates": 0, "admitted": 0, "reason": "no_typed_agent_observation"}
        snapshot, files, _ = self.experiences.capture_snapshot(str(self.root))
        # Anchors come from supervisor-observed changed source paths, not a
        # model-selected source identity. Whole-file hashes remain conservative.
        anchors = tuple(SourceAnchor(path, sha256(files[path]).hexdigest(), 1,
                                     max(1, len(files[path].splitlines())))
                        for path in sorted(changed_paths) if path in files and path.startswith("src/click/") and path.endswith(".py"))
        if not anchors or len(anchors) > 64:
            return {"candidates": 0, "admitted": 0, "reason": "no_bounded_source_anchors"}
        if len(report["summary"]) > 1000:
            return {"candidates": 1, "admitted": 0, "reason": "agent_observation_over_budget"}
        proposal = ExperienceProposal("attempt-" + run_id, self.scope, snapshot.snapshot_id,
                                      task_title, report["summary"], "unknown", anchors, ())
        self.app.settings(self.scope.project_id, {"auto_capture": True})
        try:
            result = self.experiences.form(proposal, snapshot, producer_id="benchmark-supervisor",
                signature=hmac.new(self.secret, canonical_json(proposal.to_dict()).encode(), sha256).hexdigest())
        finally:
            self.app.settings(self.scope.project_id, {"auto_capture": False})
        return {"candidates": 1, "admitted": len(result.get("record_ids", [])), "formation": result,
                "proposal": proposal.to_dict(), "outcome_assurance": "unknown_no_hidden_grader_feedback"}
