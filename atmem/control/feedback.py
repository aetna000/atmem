"""Dashboard facade over the same authenticated feedback and review services.

A trusted application supplies the local-identity-to-credential binding. There
is no browser token field, arbitrary subject selector or global owner credential.
"""
from atmem.evidence.models import EvidenceOperation, EvidenceScope
from atmem.feedback.store import FeedbackError
from atmem.feedback.store import snapshot


class FeedbackDashboard:
    def __init__(self, feedback, *, session_factory, runtime_versions=None, memory_factory=None, export_signer=None):
        if not callable(session_factory):
            raise ValueError("application-owned identity binding required")
        self.feedback = feedback
        self.session_factory = session_factory
        self.runtime_versions = snapshot(runtime_versions) if runtime_versions is not None else None
        if memory_factory is not None and not callable(memory_factory):
            raise ValueError("application-owned memory factory required")
        self.memory_factory = memory_factory
        if export_signer is not None and not callable(export_signer):
            raise ValueError("application-owned export signer required")
        self.export_signer = export_signer

    def _session(self, identity, *, owner=False):
        account = identity["account"]
        if account.get("password_change_required") or account["role"] == "viewer":
            raise FeedbackError("denied")
        if owner and account["role"] not in ("administrator", "evidence_collector"):
            raise FeedbackError("denied")
        session = self.session_factory(identity)
        principal = self.feedback._principal(session.credential)
        if principal.principal_id != account["username"] or not EvidenceScope(**account["scope"]).permits(session.scope.evidence_scope()):
            raise FeedbackError("denied")
        self.feedback.capabilities(session)
        if owner:
            try:
                principal.authorize(EvidenceOperation.GRANT, session.scope.evidence_scope())
            except PermissionError:
                raise FeedbackError("denied") from None
        return session

    def status(self, identity):
        session = self._session(identity)
        with self.feedback._authorized(session, "read") as (tx, _):
            proposals = []
            for kind in ("rule", "profile"):
                for value in tx.iter_kind(kind+"_proposal"):
                    key = value["candidate"][kind+"_id"]
                    proposals.append({"kind": kind, "artifact_id": key, "proposal": value,
                                      "lifecycle": tx.get(kind+"_lifecycle", key)})
            return {"available": True, "scope": session.scope.to_dict(), "proposals": proposals[:128],
                    "schedules": [{"schedule_id": item["schedule_id"], "tasks": len(item["tasks"])} for item in tx.list("schedule")],
                    "qualifications": tx.list("qualification"),
                    "can_review": identity["account"]["role"] in ("administrator", "evidence_collector"),
                    "activation_available": self.runtime_versions is not None,
                    "export_available": self.export_signer is not None,
                    "runtime_versions": self.runtime_versions,
                    "observed_at": int(self.feedback.clock()),
                    "activation": "requires_accepted_qualification"}

    def quality(self, identity, *, schedule_id):
        return self.feedback.quality(self._session(identity), schedule_id=schedule_id)

    def action(self, identity, body):
        session = self._session(identity, owner=True)
        memory = self.memory_factory(identity) if self.memory_factory is not None else self.feedback.memory
        from atmem.feedback.service import FeedbackService
        feedback = FeedbackService(self.feedback.evidence, clock=self.feedback.clock, memory=memory,
                                   observability=self.feedback.observability, memory_tenant_id=self.feedback.memory_tenant_id,
                                   egress_class=self.feedback.egress_class)
        try:
            return self._action(feedback, identity, session, body)
        finally:
            if self.memory_factory is not None and memory is not None:
                memory.close()

    def _action(self, feedback, identity, session, body):
        if type(body) is dict and type(body.get("operation")) is str and body["operation"].startswith("export_"):
            return self._export_action(feedback, identity, session, body)
        if type(body) is not dict or set(body) - {"operation", "kind", "artifact_id", "candidate_sha256", "reason",
                                               "decision", "state", "expected_generation", "qualification_id", "target_generation"}:
            raise FeedbackError("invalid_arguments")
        kind = body.get("kind")
        if kind not in ("rule", "profile"):
            raise FeedbackError("invalid_arguments")
        if feedback.memory is None:
            raise FeedbackError("missing_evidence")
        if body.get("operation") == "review":
            from atmem.extract.review import ReviewService
            authorization = feedback.memory.issue_review_authorization(identity["account"]["username"], scopes=("procedure:review",))
            from atmem.feedback.review import decide
            return decide(ReviewService(feedback.memory), feedback, session, rule_id=body["artifact_id"],
                          kind=kind, candidate_sha256=body["candidate_sha256"], decision=body["decision"],
                          reason=body["reason"], authorization=authorization)
        if body.get("operation") == "transition":
            if body.get("state") in ("qualified", "active") and self.runtime_versions is None:
                raise FeedbackError("enforcement_unavailable")
            from atmem.rules.lifecycle import RuleLifecycle
            return RuleLifecycle(feedback).transition(session.credential, session.scope,
                artifact_id=body["artifact_id"], kind=kind, state=body["state"],
                expected_generation=body["expected_generation"], qualification_id=body.get("qualification_id"),
                versions=self.runtime_versions, candidate_sha256=body["candidate_sha256"])
        if body.get("operation") == "rollback":
            if self.runtime_versions is None:
                raise FeedbackError("enforcement_unavailable")
            from atmem.rules.lifecycle import RuleLifecycle
            return RuleLifecycle(feedback).rollback(session.credential, session.scope,
                artifact_id=body["artifact_id"], kind=kind, expected_generation=body["expected_generation"],
                target_generation=body["target_generation"], versions=self.runtime_versions)
        raise FeedbackError("invalid_arguments")

    def _export_action(self, feedback, identity, session, body):
        import base64
        import binascii
        from atmem.feedback.export import ExampleExportService
        service = ExampleExportService(feedback)
        # A dashboard owner role alone does not grant plaintext export. Check
        # the actual scoped credential before loading any signing key.
        service._owner(session.credential, session.scope)
        operation = body.get("operation")
        fields = {"export_consent": {"consent_id", "purpose", "recipient_public_key", "outcome_ids", "expires_at", "split"},
                  "export_preview": {"consent_id"}, "export_withdraw": {"consent_id"},
                  "export_confirm": {"consent_id", "preview_sha256", "confirm_sha256", "recipient_public_key"}}
        if operation not in fields or set(body) != fields[operation] | {"operation"}:
            raise FeedbackError("invalid_arguments")
        if self.export_signer is None:
            raise FeedbackError("export_unavailable")
        args = {k:v for k,v in body.items() if k != "operation"}
        try:
            if "recipient_public_key" in args:
                value = args["recipient_public_key"]
                if type(value) is not str or len(value) > 1600:
                    raise ValueError("bounded public key required")
                args["recipient_public_key"] = base64.b64decode(value, validate=True)
                if len(args["recipient_public_key"]) != 1184:
                    raise ValueError("ML-KEM-768 public key required")
            if operation == "export_consent":
                if type(args["outcome_ids"]) is not list:
                    raise ValueError("outcome list required")
                args["outcome_ids"] = tuple(args["outcome_ids"])
                return service.consent(session.credential, session.scope, **args)
            if operation == "export_preview":
                return service.preview(session.credential, session.scope, **args)
            if operation == "export_withdraw":
                return service.withdraw(session.credential, session.scope, **args)
            # The signer is trusted application configuration, never request
            # data. Keys remain server-side and are not returned to the browser.
            signing_public, signing_secret = self.export_signer(identity)
            return service.export(session.credential, session.scope, **args,
                                  signing_public_key=signing_public, signing_secret_key=signing_secret)
        except (ValueError, TypeError, binascii.Error):
            raise FeedbackError("invalid_arguments") from None
