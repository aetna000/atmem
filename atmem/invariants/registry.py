"""The eleven standing AtMem guarantees as executable registry entries."""

from __future__ import annotations

from .models import Invariant, InvariantRegistry


_DEFINITIONS = (
    ("INV-001", "AtMem remains the only canonical authority.", "I", "authority.canonical_only"),
    ("INV-002", "Authorization happens before intelligence sees candidate content.", "I", "authority.before_intelligence"),
    ("INV-003", "Rankings are revalidated against record scope and lifecycle.", "I, IV", "authority.ranking_revalidation"),
    ("INV-004", "Shadow mode and activation remain explicit.", "III", "delivery.explicit_activation"),
    ("INV-005", "Context construction remains byte-stable and receipt-bound.", "II", "delivery.byte_stable_receipt"),
    ("INV-006", "Provenance and memory history remain human-readable.", "II", "delivery.provenance_history"),
    ("INV-007", "Deletion covers canonical, graph, vector, and derived copies.", "IV", "deletion.all_registered_copies"),
    ("INV-008", "Agent Black Box retains honest proof boundaries.", "II, VI", "proof.blackbox_boundaries"),
    ("INV-009", "Host integration remains reversible.", "III, V", "delivery.openclaw_restore"),
    ("INV-010", "Local operation and deterministic fallback remain available.", "III, VII", "local.deterministic_fallback"),
    ("INV-011", "Persisted-data upgrades remain backward compatible.", "V, VI", "upgrade.persisted_compatibility"),
)


REGISTRY = InvariantRegistry(
    version="1.1.0",
    invariants=tuple(
        Invariant(
            invariant_id=invariant_id,
            guarantee=guarantee,
            principle=principle,
            owning_spec="specs/018-cross-cutting-invariants",
            assertions=(assertion,),
            amendments=(
                {
                    "id": "018-A001",
                    "date": "2026-09-09",
                    "principle": "III, V, VI",
                    "previous_guarantee": "OpenClaw migration remains reversible.",
                    "reason": "Apply reversibility to host integrations while retaining host-specific proof.",
                    "compatibility_impact": "Stable INV-009, v1 wire format and delivery.openclaw_restore assertion retained; registry content version is 1.1.0.",
                    "replacement_coverage": "OpenClaw remains the baseline assertion; other hosts require separately executed conformance evidence. Legacy base results do not prove other host configurations.",
                    "record": "specs/018-cross-cutting-invariants/amendments/018-A001-host-reversibility.md",
                },
            ) if invariant_id == "INV-009" else (),
        )
        for invariant_id, guarantee, principle, assertion in _DEFINITIONS
    ),
)


def load_registry() -> InvariantRegistry:
    """Return the immutable built-in registry."""

    return REGISTRY
