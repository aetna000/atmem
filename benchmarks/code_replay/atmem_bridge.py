"""Replay evidence through AtMem's existing protected, audited boundary.

This is not a substitute memory engine or a normal-host qualification claim.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from atmem.core.canonical import canonical_json
from atmem.evidence import EvidenceOperation, EvidencePrincipal, EvidenceScope
from atmem.evidence.service import EvidenceService


class ReplayEvidence:
    def __init__(self, root: Path, *, vault_id: str, scope: EvidenceScope):
        self.scope = scope
        # Explicit benchmark home: never inherit the owner's ATMEM_HOME.
        self.service = EvidenceService(root, vault_id=vault_id, home_root=root.parent)
        status = self.service.protection_status()
        if status["at_rest_state"] != "encrypted" or status["capture_mode"] != "full":
            raise PermissionError("full protected benchmark evidence is required")

    def capture(self, *, run_id: str, kind: str, payload: dict, principal: EvidencePrincipal):
        target = EvidenceScope(self.scope.tenant_id, self.scope.subject_id, self.scope.workspace_id, run_id)
        principal.authorize(EvidenceOperation.RETENTION, target)
        if not self.scope.permits(target):
            raise PermissionError("benchmark run outside evidence scope")
        raw = canonical_json(payload)
        if len(raw.encode()) > 16_000_000:
            raise ValueError("benchmark evidence event budget exceeded")
        envelope = {"format": "atmem-click-benchmark-evidence-v1", "tenant_id": target.tenant_id,
                    "subject_id": target.subject_id, "workspace_id": target.workspace_id,
                    "run_id": run_id, "event_id": "replay-event-" + uuid4().hex,
                    "producer_instance_id": "atmem-click-evaluator", "producer_epoch": "replay-v2",
                    "event_time": datetime.now(timezone.utc).isoformat(), "event_type": kind,
                    "payload": payload, "capture_coverage": "declared_event_only",
                    "solver_reconstruction": "not_claimed"}
        receipt = self.service.capture(envelope)
        if not receipt["captured"] or receipt["capture_mode"] != "full":
            raise RuntimeError("benchmark evidence was not fully retained")
        return {"object_id": receipt["object_id"], "payload_sha256": sha256(raw.encode()).hexdigest(),
                "run_id": run_id, "encrypted": True}

    def inspect(self, principal: EvidencePrincipal, run_id: str):
        target = EvidenceScope(self.scope.tenant_id, self.scope.subject_id, self.scope.workspace_id, run_id)
        try:
            principal.authorize(EvidenceOperation.VIEW, target)
        except PermissionError:
            self.service._record_access(principal, "view", target, False)
            raise
        return self.service.events(principal, run_id)

    def delete(self, principal: EvidencePrincipal, run_id: str, confirmation: str):
        target = EvidenceScope(self.scope.tenant_id, self.scope.subject_id, self.scope.workspace_id, run_id)
        try:
            principal.authorize(EvidenceOperation.DELETE, target)
        except PermissionError:
            self.service._record_access(principal, "delete", target, False)
            raise
        return self.service.delete_run(principal, run_id, confirmation=confirmation)

    def encrypted_archive(self, principal, run_id, *, recipient_public_key, signing_public_key, signing_secret_key):
        from benchmarks.code_replay.archive import seal
        target = EvidenceScope(self.scope.tenant_id, self.scope.subject_id, self.scope.workspace_id, run_id)
        try:
            principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)
            raw = canonical_json(self.service.events(principal, run_id)).encode()
            bundle = seal(raw, run_id=run_id, recipient_public_key=recipient_public_key,
                          signing_public_key=signing_public_key, signing_secret_key=signing_secret_key)
            self.service._record_access(principal, "encrypted_export", target, True)
            return bundle
        except PermissionError:
            self.service._record_access(principal, "encrypted_export", target, False)
            raise
