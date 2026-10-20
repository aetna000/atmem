"""Authenticated attempt observations routed through existing typed admission.

Producer signatures attest origin, not semantic truth or a successful fix.
Only bounded test execution outcomes are inferred from bound receipts. The
caller must be the authenticated application, never an arbitrary model tool.
"""
import base64
import hashlib
import hmac

from atmem.code.contracts import CodeScope, _sha256
from atmem.code.formation import memory_subject_id
from atmem.core.canonical import canonical_json
from atmem.knowledge.contracts import ExecutionReceipt, ExperienceProposal, SourceSnapshot
from atmem.knowledge.contracts import text
from atmem.knowledge.code.environment import environment_digest


class CodeExperience:
    def __init__(self, application, scope: CodeScope, *, producer_keys: dict[str, bytes], environment_sha256: str | None = None):
        if scope.subject_id != application.subject_id:
            raise PermissionError("experience subject mismatch")
        application.authorize(scope.project_id)
        if not producer_keys or any(not isinstance(v, bytes) or len(v) < 32 for v in producer_keys.values()):
            raise ValueError("approved producer keys required")
        self.app, self.scope, self.producer_keys = application, scope, dict(producer_keys)
        if environment_sha256 is not None:
            _sha256("approved tool environment", environment_sha256)
        self.environment_sha256 = environment_sha256

    def _environment(self):
        return self.environment_sha256 or environment_digest()

    def capture_snapshot(self, root):
        """Hash the authorized source state without requiring graph extraction.

        Larger files can participate in execution identity even when the optional
        extractor's stricter materialization budget cannot accept them.
        """
        from atmem.knowledge.projections import CodeKnowledge
        return CodeKnowledge(self.app, self.scope).capture(root, self._environment(),
                                                          max_file_bytes=2_000_000, max_source_bytes=64_000_000)

    def _verify(self, producer_id, value, signature):
        self.app.authorize(self.scope.project_id)
        key = self.producer_keys.get(producer_id)
        if key is None or not isinstance(signature, str):
            raise PermissionError("unknown experience producer")
        expected = hmac.new(key, canonical_json(value).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("producer signature mismatch")

    def receipt(self, receipt: ExecutionReceipt, snapshot: SourceSnapshot, result: bytes, signature: str):
        self._verify(receipt.producer_id, receipt.to_dict(), signature)
        if receipt.scope != self.scope or snapshot.scope != self.scope or receipt.snapshot_id != snapshot.snapshot_id:
            raise PermissionError("receipt source/scope mismatch")
        if receipt.environment_sha256 != snapshot.configuration_sha256 or receipt.environment_sha256 != self._environment():
            raise ValueError("execution environment does not match the approved producer contract")
        if type(result) is not bytes or len(result) > 2_000_000 or hashlib.sha256(result).hexdigest() != receipt.result_sha256:
            raise ValueError("execution result digest or size mismatch")
        text(result.decode("utf-8"), "execution result", 2_000_000)
        value = {"scope": self.scope.to_dict(), "receipt": receipt.to_dict(), "snapshot": snapshot.to_dict(),
                 "result": base64.b64encode(result).decode(), "producer_assurance": "authenticated_producer_report",
                 "signature": signature}
        with self.app.store.transaction():
            if not self.app.settings(self.scope.project_id)["auto_capture"]:
                return {"accepted": False, "reason": "auto_capture_disabled"}
            previous = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "execution-receipt", receipt.receipt_id)
            if previous is not None and previous != value:
                raise ValueError("execution receipt identity conflict")
            self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "execution-receipt", receipt.receipt_id, value)
        return {"receipt_id": receipt.receipt_id, "assurance": value["producer_assurance"]}

    def form(self, proposal: ExperienceProposal, snapshot: SourceSnapshot, *, producer_id: str, signature: str):
        self._verify(producer_id, proposal.to_dict(), signature)
        if proposal.scope != self.scope or snapshot.scope != self.scope or proposal.snapshot_id != snapshot.snapshot_id:
            raise PermissionError("experience source/scope mismatch")
        if snapshot.configuration_sha256 != self._environment():
            raise ValueError("experience environment changed or is unqualified")
        files = dict(snapshot.files)
        if any(files.get(a.path) != a.content_sha256 for a in proposal.anchors):
            raise ValueError("experience anchor outside source snapshot")
        with self.app.store.transaction():
            self.app.authorize(self.scope.project_id)
            if not self.app.settings(self.scope.project_id)["auto_capture"]:
                return {"formed": False, "reason": "auto_capture_disabled"}
            environment = {"scope": self.scope.to_dict(), "environment_sha256": self._environment(),
                           "assurance": "producer_declared_tool_environment" if self.environment_sha256 else "local_python_host",
                           "producer_id": producer_id}
            key = memory_subject_id(self.scope)
            previous_environment = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "experience-environment", key)
            if previous_environment != environment:
                self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "experience-environment", key, environment)
                self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.experience_environment_bound", actor="atmem",
                                                  payload={"project_id": self.scope.project_id, "environment_sha256": environment["environment_sha256"],
                                                           "assurance": environment["assurance"], "producer_id": producer_id})
            existing = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "code-experience", proposal.proposal_id)
            if self.app.store.code_document(self.app.subject_id, self.scope.project_id, "experience-tombstone", proposal.proposal_id):
                return {"formed": False, "reason": "experience_was_deleted"}
            if existing:
                if existing["proposal"] != proposal.to_dict():
                    raise ValueError("experience identity conflict")
                return {**existing["formation"], "replayed": True}
            receipts = []
            for identity in proposal.receipt_ids:
                value = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "execution-receipt", identity)
                if value is None:
                    raise ValueError("experience references uncaptured execution")
                receipt = ExecutionReceipt.from_dict(value["receipt"])
                if receipt.scope != self.scope or receipt.snapshot_id != snapshot.snapshot_id or receipt.producer_id != producer_id:
                    raise PermissionError("execution evidence binding mismatch")
                receipts.append(receipt)
            if len({r.attempt_id for r in receipts}) > 1 or len({r.environment_sha256 for r in receipts}) > 1:
                raise ValueError("experience mixes attempts or environments")
            if proposal.outcome == "observed_pass" and (not receipts or any(r.exit_code != 0 for r in receipts)):
                raise ValueError("pass not supported by bound execution receipts")
            if proposal.outcome == "observed_failure" and not any(r.exit_code is not None and r.exit_code != 0 for r in receipts):
                raise ValueError("failure not supported by bound execution receipts")
            return self._admit(proposal, snapshot, receipts)

    def _admit(self, proposal, snapshot, receipts):
        from atmem.contracts import AuthorityScope, SourceCaptureRequest
        from atmem.extract.models import (MemoryUnit, MemoryUnitKind, EnvironmentStatePayload, ProposalEvidence,
                                          ExtractionProposal, ProposalAction, MemoryClass)
        from atmem.extract.review import ReviewPolicy
        subject = memory_subject_id(self.scope)
        agent = "shared" if self.scope.profile_id == "shared" else self.scope.agent_id
        scope = AuthorityScope(subject, agent, self.scope.project_id)
        # Attributed observation, not an instruction or an inferred general fix.
        value = f"{proposal.outcome}. Intent: {proposal.intent}. Producer observation: {proposal.observation}"
        text(value, "bounded experience", 1600)
        content = f"coding attempt {proposal.proposal_id} reported outcome {value}"
        # Preserve the source as an attributed historical observation. Parsing
        # "rejects controls" or "no tests ran" as an objective positive/negative
        # durable fact would both distort meaning and misapply polarity checks.
        payload = EnvironmentStatePayload("source episode", "source statement", content)
        source_id = "experience-source-" + hashlib.sha256(proposal.proposal_id.encode()).hexdigest()
        captured = self.app.memory.capture_source(SourceCaptureRequest(
            source_id, source_id, scope, content, source_type="tool_output",
            binding_method="host_asserted", binding_assurance="host_authenticated"))
        evidence = (ProposalEvidence(source_id, captured.source_sha256, 0, len(content), captured.source_sha256),)
        unit = MemoryUnit("experience-unit-" + hashlib.sha256(proposal.proposal_id.encode()).hexdigest(),
                          proposal.proposal_id, MemoryUnitKind.ENVIRONMENT_STATE, scope, payload, evidence, 1.0)
        request = ExtractionProposal(proposal.proposal_id, proposal.proposal_id, scope, ProposalAction.ADD,
                                     MemoryClass.TEMPORARY_STATE, 1.0, ("historical_observation", "authenticated_coding_attempt"),
                                     evidence, fact=unit.canonical_text(), unit=unit,
                                     review_required=self.app.settings(self.scope.project_id)["review_workflow"])
        admitted = self.app.memory.submit_extraction_proposal(
            request, source_text=content, actor="atmem-code-experience",
            review_policy=ReviewPolicy(quarantine_non_durable=False))
        record_ids = admitted.get("record_ids", [])
        self.app.store.register_code_scope_subject(owner_subject_id=self.scope.subject_id, derived_subject_id=subject,
                                                   project_id=self.scope.project_id, profile_id=self.scope.profile_id, agent_id=agent)
        result = {"formed": bool(record_ids), "record_ids": record_ids,
                  "review_state": admitted["review_state"], "reason_codes": admitted.get("reason_codes", []),
                  "assurance": "authenticated_attempt_observation_not_verified_fix"}
        self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "code-experience", proposal.proposal_id,
                                        {"scope": self.scope.to_dict(), "proposal": proposal.to_dict(), "snapshot": snapshot.to_dict(),
                                         "receipt_ids": list(proposal.receipt_ids), "formation": result})
        for record_id in record_ids:
            self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "origin", record_id,
                                            {"code_memory_class": "coding_experience", "code_profile_id": self.scope.profile_id,
                                             "code_agent_id": self.scope.agent_id, "experience_proposal_id": proposal.proposal_id,
                                             "code_project_id": self.scope.project_id, "code_source_ref": source_id,
                                             "code_git_revision": snapshot.revision})
        return result
