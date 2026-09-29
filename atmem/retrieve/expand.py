"""Bounded authority-preserving expansion around already eligible evidence."""

from __future__ import annotations

from atmem.contracts import EvidenceNeighborhood, EvidencePath, RetrievalBudget
from atmem.core.canonical import canonical_json, sha256_hex


def expand_evidence_neighborhood(
    store,
    *,
    subject_id: str,
    workspace_id: str,
    need_id: str,
    seed_record_ids: tuple[str, ...],
    budget: RetrievalBudget,
    remote: bool = False,
) -> EvidenceNeighborhood:
    if not seed_record_ids:
        raise ValueError("evidence expansion requires at least one eligible seed")
    selected = list(dict.fromkeys(seed_record_ids))
    paths = {
        record_id: EvidencePath(record_id, record_id, (), 0, "eligible_seed")
        for record_id in selected
    }
    frontier = list(selected)
    visited_sources: set[str] = set()
    visits = len(selected)
    truncated = False
    for depth in range(1, budget.neighbor_depth + 1):
        typed = store.typed_units_for_records(
            subject_id, workspace_id, frontier, remote=remote
        )
        source_to_seed: dict[str, str] = {}
        for row in typed:
            for evidence in row["unit"].get("evidence") or ():
                source_id = str(evidence.get("source_id") or "")
                if source_id and source_id not in visited_sources:
                    source_to_seed[source_id] = str(row["record_id"])
                    visited_sources.add(source_id)
        remaining = budget.graph_visits - visits
        if remaining <= 0:
            truncated = True
            break
        neighbors = (
            store.adjacent_typed_records(
                subject_id,
                workspace_id,
                list(source_to_seed),
                limit=remaining,
                remote=remote,
            )
            if source_to_seed else []
        )
        next_frontier: list[str] = []
        for row in neighbors:
            record_id = str(row["record_id"])
            if record_id in paths:
                continue
            seed_record = source_to_seed.get(str(row["seed_source_id"]))
            if seed_record is None:
                continue
            root = paths[seed_record].seed_record_id
            edge_types = paths[seed_record].edge_types + (str(row["direction"]),)
            paths[record_id] = EvidencePath(
                root, record_id, edge_types, depth, "ordered_source_neighbor"
            )
            selected.append(record_id)
            next_frontier.append(record_id)
            visits += 1
            if visits >= budget.graph_visits:
                truncated = True
                break
        if not truncated:
            remaining = budget.graph_visits - visits
            related = store.related_typed_records(
                subject_id,
                workspace_id,
                frontier,
                limit=remaining,
                remote=remote,
            ) if remaining > 0 else []
            for row in related:
                record_id = str(row["record_id"])
                if record_id in paths:
                    continue
                seed_record = str(row["seed_record_id"])
                if seed_record not in paths:
                    continue
                root = paths[seed_record].seed_record_id
                relation = str(row["relation"])
                paths[record_id] = EvidencePath(
                    root,
                    record_id,
                    paths[seed_record].edge_types + (relation,),
                    depth,
                    "explicit_provenance_neighbor",
                )
                selected.append(record_id)
                next_frontier.append(record_id)
                visits += 1
                if visits >= budget.graph_visits:
                    truncated = True
                    break
        frontier = next_frontier
        if not frontier or truncated:
            break
    identity = canonical_json({
        "need_id": need_id,
        "seeds": seed_record_ids,
        "selected": selected,
        "depth": budget.neighbor_depth,
    })
    return EvidenceNeighborhood(
        neighborhood_id=f"neighborhood-{sha256_hex(identity)[:24]}",
        need_id=need_id,
        seed_record_ids=seed_record_ids,
        paths=tuple(paths[record_id] for record_id in selected),
        selected_record_ids=tuple(selected),
        visited_count=visits,
        max_depth=budget.neighbor_depth,
        truncated=truncated,
        reason_codes=(("graph_visit_budget_exhausted",) if truncated else ()),
    )
