"""Synthetic document corpus and real AtMem credentials for integration tests."""

from hashlib import sha256
from types import SimpleNamespace

from atmem.contracts.feedback import FeedbackScope
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService
from atmem.knowledge.rag.contracts import RagHit, RagSource
from atmem.knowledge.rag.service import RagService
from atmem.knowledge.rag.sqlite import SQLiteRagProvider


def hit(source, chunk="current", *, text="The fictional filing deadline is ten days.", jurisdiction="XX",
        effective_from="2025-01-01", effective_to=None):
    return RagHit(source.source_id, source.scope, source.revision, "fictional-act", chunk,
                  "Synthetic Filing Act (not actual law)", "urn:fixture:filing-act", "section-"+chunk,
                  text, sha256(text.encode()).hexdigest(), jurisdiction, effective_from, effective_to)


def setup_rag(tmp_path):
    evidence = EvidenceService(tmp_path / "control", vault_id="rag", home_root=tmp_path)
    credentials = evidence.create_demo_accounts(subject_id="alice")
    owner, user = credentials[2], credentials[1]
    feedback = FeedbackService(evidence, clock=lambda: 1_700_000_000)
    scope = FeedbackScope("local", "alice", "writer", "project")
    feedback.grant_agent(owner["token"], scope, principal_id=user["principal_id"],
                         operations=("read", "search", "inspect"), expires_at=1_700_010_000)
    session = feedback.bind(user["token"], agent_id="writer", workspace_id="project")
    source = RagSource("law", scope, "sqlite-vault", "filing", "collection-v1", "none")
    provider = SQLiteRagProvider(feedback)
    rag = RagService(feedback)
    rag.register(owner["token"], source, provider)
    hits = (hit(source), hit(source, "old", text="The fictional filing deadline was five days.",
                             effective_from="2020-01-01", effective_to="2025-01-01"),
            hit(source, "unknown", text="Filing deadline not dated in this fictional note.",
                jurisdiction=None, effective_from=None),
            hit(source, "other", text="The fictional filing deadline in YY is twenty days.", jurisdiction="YY"))
    provider.put_documents(owner["token"], source, hits)
    return SimpleNamespace(evidence=evidence, feedback=feedback, owner=owner, user=user,
                           scope=scope, session=session, source=source, provider=provider, rag=rag, hits=hits)
