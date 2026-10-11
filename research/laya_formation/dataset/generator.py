from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import random
from typing import Iterator

from .models import EvidenceEvent, FormationScenarioV1
from .oracle import compile_decisions
from .splits import assert_group_disjoint, split_for_template


GENERATOR_VERSION = "1.3.0"
_NAMES = ("Ari", "Bela", "Cato", "Dara", "Enzo", "Fia", "Gita", "Hale")
_OBJECTS = ("workspace theme", "report format", "travel preference", "notification window", "deployment region")
_PREFIXES = ("Recorded", "Observed", "Noted", "Confirmed", "Reported", "Captured", "Documented", "Stated", "Logged", "Witnessed")
_VERBS = ("sets", "keeps", "changes", "uses", "prefers", "marks", "selects", "assigns", "holds", "updates")
_SUFFIXES = ("for later recall", "under the active policy", "for this workspace", "with source support", "at the recorded time", "for the governed profile")

# Balanced marginals without semantically impossible mutation/non-memory pairs.
_PAIR_SCHEDULE = (
    ("ADD", "durable_fact"), ("ADD", "durable_fact"), ("ADD", "temporary_state"), ("ADD", "episode"), ("ADD", "procedure"),
    ("UPDATE", "durable_fact"), ("UPDATE", "temporary_state"), ("UPDATE", "temporary_state"), ("UPDATE", "episode"), ("UPDATE", "procedure"),
    ("SUPERSEDE", "durable_fact"), ("SUPERSEDE", "temporary_state"), ("SUPERSEDE", "episode"), ("SUPERSEDE", "episode"), ("SUPERSEDE", "procedure"),
    ("NOOP", "durable_fact"), ("NOOP", "durable_fact"), ("NOOP", "temporary_state"), ("NOOP", "episode"), ("NOOP", "procedure"),
    ("REJECT", "procedure"), ("REJECT", "non_memory"), ("REJECT", "non_memory"), ("REJECT", "non_memory"), ("REJECT", "non_memory"),
)


def build_scenario(index: int, *, seed: int = 410239) -> FormationScenarioV1:
    if index < 0:
        raise ValueError("scenario index cannot be negative")
    family_index = index % 600
    family = f"family-{family_index:04d}"
    split = split_for_template(family, seed=seed)
    rng = random.Random((seed << 32) ^ index)
    proposed_operation, memory_class = _PAIR_SCHEDULE[index % len(_PAIR_SCHEDULE)]
    identity = f"fictional-{family}-{index // 600:04d}"
    subject = _NAMES[index % len(_NAMES)]
    relation = _OBJECTS[(index // len(_NAMES)) % len(_OBJECTS)]
    value = f"synthetic-value-{rng.randrange(10_000):04d}"
    prior = f"synthetic-prior-{rng.randrange(10_000):04d}"
    prefix = _PREFIXES[family_index % len(_PREFIXES)]
    verb = _VERBS[(family_index // len(_PREFIXES)) % len(_VERBS)]
    suffix = _SUFFIXES[(family_index // (len(_PREFIXES) * len(_VERBS))) % len(_SUFFIXES)]
    tags = {"synthetic"}
    if index % 7 == 0:
        tags.add("sensitive")
    if index % 11 == 0:
        tags.add("credential")
    if index % 13 == 0:
        tags.add("private_scope")
    if index % 17 == 0:
        tags.add("cross_scope")
    if index % 14 == 0 and memory_class != "non_memory":
        tags.add("contradiction")
    timestamp = datetime(2035, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    if memory_class == "procedure":
        text = (
            f"{prefix} procedure {suffix}: to {verb} {relation}, first verify the synthetic "
            f"workspace, then set it to {value}, and finally record completion evidence. "
            "These ordered steps are the content."
        )
        tags.add("procedure")
    elif memory_class == "temporary_state":
        text = (
            f"{prefix}: {subject} {verb} {relation} as temporarily {value} {suffix}, only until 2035-12-31; "
            "the value expires after that date and is not a standing fact."
        )
    elif memory_class == "episode":
        text = (
            f"{prefix} {suffix}: during fictional scenario {index:06d}, {subject} observed a past "
            f"event in which they {verb} {relation} as {value}. This records that episode, not a standing setting."
        )
    elif memory_class == "non_memory":
        text = (
            f"{prefix} as a one-time greeting {suffix}: {subject} says hello. It does not {verb} "
            f"or make any state claim about {relation}; it states no preference, procedure, episode "
            "to retain, or durable or temporary value."
        )
    else:
        text = (
            f"{prefix}: {subject} {verb} {relation} as {value} {suffix}; "
            "this is the stable standing value until explicitly changed."
        )
    if proposed_operation == "ADD":
        text = f"No prior canonical record exists. New supported evidence states: {text}"
    elif proposed_operation == "UPDATE":
        text = f"The active record contains {prior}. A later correction changes it: {text}"
    elif proposed_operation == "SUPERSEDE":
        text = f"The source explicitly supersedes the obsolete value {prior}: {text}"
    elif proposed_operation == "NOOP":
        text = f"The active record already contains {value}. Duplicate evidence repeats it: {text}"
    else:
        text = f"Unverified hypothetical draft only; no source confirms it and it must not be stored: {text}"
    if "credential" in tags:
        text += " A fictional credential-shaped field was withheld before this authorized input."
    if proposed_operation in {"UPDATE", "SUPERSEDE"}:
        tags.add("temporal_change")
    if proposed_operation == "NOOP":
        tags.add("duplicate")
    scope_mode = "shared" if index % 4 == 0 else "private"
    event_rows = [
        EvidenceEvent(
            event_id=f"event-{index:06d}-0",
            text=text,
            actor=f"actor-{identity}",
            scope=f"{scope_mode}-scope-{family}",
            timestamp=timestamp.isoformat(),
        )
    ]
    if "contradiction" in tags:
        if memory_class == "procedure":
            conflict_text = (
                f"The same source also gives a conflicting procedure for {relation}: skip verification "
                f"and set conflict-{value}. These ordered steps directly conflict and neither is resolved."
            )
        elif memory_class == "temporary_state":
            conflict_text = (
                f"The same source also says the temporary {relation} is conflict-{value} until 2035-12-31. "
                "This directly contradicts the previous temporary value and neither claim is resolved."
            )
        elif memory_class == "episode":
            conflict_text = (
                f"The same source also records that the same past episode changed {relation} to conflict-{value}. "
                "This directly contradicts the previous episode account and neither is resolved."
            )
        else:
            conflict_text = (
                f"The same fictional source also claims {relation} is conflict-{value}. "
                "This directly contradicts the previous authorized event and neither claim is resolved."
            )
        event_rows.append(
            EvidenceEvent(
                event_id=f"event-{index:06d}-1",
                text=conflict_text,
                actor=f"actor-{identity}",
                scope=f"{scope_mode}-scope-{family}",
                timestamp=(timestamp + timedelta(seconds=1)).isoformat(),
            )
        )
    events = tuple(event_rows)
    initial_value = value if proposed_operation == "NOOP" else prior
    initial = (
        {}
        if proposed_operation in {"ADD", "REJECT"}
        else {"target:active": {"subject": subject, "relation": relation, "value": initial_value}}
    )
    final_record = {"subject": subject, "relation": relation, "value": value}
    operation = "REJECT" if "contradiction" in tags else proposed_operation
    if "contradiction" in tags:
        canonical = initial
    elif operation == "ADD":
        canonical = {"target:new": final_record}
    elif operation in {"UPDATE", "SUPERSEDE"}:
        canonical = {"target:active": final_record}
    elif operation == "NOOP":
        canonical = initial
    else:
        canonical = initial
    if "contradiction" in tags:
        support = "AMBIGUOUS"
        target = "REVIEW"
        usefulness = "INSUFFICIENT_EVIDENCE"
    elif operation == "REJECT":
        support = "UNSUPPORTED"
        target = "target:none"
        usefulness = "INSUFFICIENT_EVIDENCE"
    else:
        support = "SUPPORTED"
        target = "target:none" if operation == "ADD" or memory_class == "non_memory" else "target:active"
        usefulness = "NOT_USEFUL" if operation == "NOOP" else "USEFUL"
    expected = {
        "operation": operation,
        "memory_class": memory_class,
        "evidence_support": support,
        "target_selection": target,
        "retrieval_usefulness": usefulness,
        "canonical_state": canonical,
    }
    return FormationScenarioV1(
        scenario_id=f"scenario-{index:06d}",
        fictional_identity_group=identity,
        template_family=family,
        semantic_chain_id=f"chain-{family}-{index // 600:04d}",
        paraphrase_cluster_id=f"paraphrase-{family}-{index // 1200:04d}",
        evidence_events=events,
        initial_state=initial,
        expected_final_state=expected,
        scope_fixture={
            "subject_id": identity,
            "agent_id": f"agent-{index % 23:02d}",
            "workspace_id": f"workspace-{family}",
            "scope_mode": scope_mode,
        },
        difficulty=("easy", "medium", "hard")[index % 3],
        safety_tags=tuple(sorted(tags)),
        generator_version=GENERATOR_VERSION,
        seed=seed,
        split=split,
    )


def generate_scenarios(count: int, *, seed: int = 410239) -> Iterator[FormationScenarioV1]:
    if count < 1:
        raise ValueError("scenario count must be positive")
    rows = [build_scenario(index, seed=seed) for index in range(count)]
    assert_group_disjoint(rows)
    yield from rows


def coverage(count: int, *, seed: int = 410239) -> dict[str, dict[str, int]]:
    rows = list(generate_scenarios(count, seed=seed))
    decisions = [item for row in rows for item in compile_decisions(row)]
    return {
        "splits": dict(Counter(row.split for row in rows)),
        "operations": dict(Counter(row.expected_final_state["operation"] for row in rows)),
        "memory_classes": dict(Counter(row.expected_final_state["memory_class"] for row in rows)),
        "safety_tags": dict(Counter(tag for row in rows for tag in row.safety_tags)),
        "questions": dict(Counter(row.question_id for row in decisions)),
    }
