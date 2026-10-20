"""Graph-independent, conservative source/config applicability receipts."""
from atmem.knowledge.contracts import ApplicabilityReceipt, SourceSnapshot, ExperienceProposal
from atmem.code.formation import memory_subject_id


_CONFIG_NAMES = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "poetry.lock", "uv.lock",
                 "package.json", "package-lock.json", "Cargo.toml", "Cargo.lock", "go.mod", "go.sum"}


def assess(proposal: ExperienceProposal, baseline: SourceSnapshot, current: SourceSnapshot):
    reasons = []
    if proposal.snapshot_id != baseline.snapshot_id:
        reasons.append("BASELINE_BINDING_MISMATCH")
    if memory_subject_id(proposal.scope) != memory_subject_id(current.scope) or proposal.scope != baseline.scope:
        reasons.append("SCOPE_MISMATCH")
    if baseline.worktree_id != current.worktree_id:
        reasons.append("WORKTREE_MISMATCH")
    if baseline.configuration_sha256 != current.configuration_sha256:
        reasons.append("ENVIRONMENT_OR_EXTRACTION_CONFIGURATION_CHANGED")
    before, after = dict(baseline.files), dict(current.files)
    for anchor in proposal.anchors:
        if before.get(anchor.path) != anchor.content_sha256 or after.get(anchor.path) != anchor.content_sha256:
            reasons.append("ANCHOR_CHANGED_OR_MISSING")
    configs = {p for p in before.keys() | after.keys() if p.rsplit("/", 1)[-1] in _CONFIG_NAMES}
    if any(before.get(p) != after.get(p) for p in configs):
        reasons.append("DEPENDENCY_CONFIGURATION_CHANGED")
    # This is source applicability, never a proof of runtime semantic validity.
    return ApplicabilityReceipt(proposal.proposal_id, current.snapshot_id,
                                "withheld" if reasons else "applicable",
                                tuple(dict.fromkeys(reasons)) or ("DECLARED_ANCHORS_AND_CONFIGURATION_MATCH",))
