# Copyright 2024 Topoteretes UG. (haftungsbeschränkt).
# SPDX-License-Identifier: Apache-2.0
# Incorporated from Cognee f154b32a9e544dac73e7ddf2010327cf9988edcd; modified by AtMem.
# Mechanical modifications: remove backend/cache/LLM integration and use an
# explicitly supplied in-memory authorized snapshot. See third_party/cognee/.
from typing import Any
from pathlib import Path
import json
import logging
logger = logging.getLogger(__name__)

_ENOLA_ID_LENGTH = 32

_HEX_DIGITS = frozenset("0123456789abcdef")

_RELATION_TYPE_KEYS = ("kind", "type", "relation", "rel")

_RELATION_TARGET_KEYS = ("target", "name", "to", "target_name")

def is_enola_id(value: Any) -> bool:
    """Whether value is a writer fact identity (32 lowercase hex chars, enola >= 0.4.10)."""
    return (
        isinstance(value, str)
        and len(value) == _ENOLA_ID_LENGTH
        and all(character in _HEX_DIGITS for character in value)
    )

def relation_target_id(relation: Any) -> str | None:
    """The writer-resolved target identity of a relation (``target_id``), or None.

    enola emits it only when the target resolves unambiguously (same-repo
    facts first, then snapshot-wide); when absent the readable ``target`` name
    is all there is, and the consumer must not pick an arbitrary match.
    """
    if not isinstance(relation, dict):
        return None
    value = relation.get("target_id")
    return value if is_enola_id(value) else None

def _synthesize_insight_facts(snapshot_dir: Path) -> list:
    """Convert insights.json explainer findings into fact dicts.

    enola's explainers (cycles, layers, hotspots, god-class, dead-methods,
    unused-routes, ...) write architecture findings to insights.json. Each
    becomes a synthetic fact of kind "insight" whose relations point at the
    evidence facts it cites — through the evidence's writer-resolved
    ``fact_id`` when present, else by name — so the ordinary fact-mapping and
    edge-resolution paths handle it. The machine-readable ``metrics`` block
    and the ``informational`` flag ride along in props. A missing or
    unparseable insights.json is not an error (0.1.x snapshots lack it).
    """
    insights_path = snapshot_dir / "insights.json"
    if not insights_path.is_file():
        return []
    try:
        with insights_path.open("r", encoding="utf-8") as insights_file:
            insights = json.load(insights_file)
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not parse insights.json in %s; ignoring it.", snapshot_dir)
        return []
    if not isinstance(insights, list):
        return []

    facts = []
    for insight in insights:
        if not isinstance(insight, dict):
            continue
        title = insight.get("title")
        if not isinstance(title, str) or not title:
            continue
        props = {
            key: insight[key]
            for key in (
                "source",
                "confidence",
                "description",
                "suggested_actions",
                "metrics",
                "informational",
            )
            if insight.get(key) is not None
        }
        relations = []
        evidence = insight.get("evidence")
        for entry in evidence if isinstance(evidence, list) else []:
            if not isinstance(entry, dict):
                continue
            # Same precedence the writer uses to resolve fact_id: symbol, then
            # fact; a bare file citation falls back to the file's own fact.
            target = entry.get("symbol") or entry.get("fact") or entry.get("file")
            if isinstance(target, str) and target:
                relation = {"kind": "evidences", "target": target}
                fact_id = entry.get("fact_id")
                if is_enola_id(fact_id):
                    relation["target_id"] = fact_id
                relations.append(relation)
        facts.append(
            {
                "kind": "insight",
                "name": title,
                "props": props,
                "relations": relations,
            }
        )
    return facts

def normalize_relation(relation: dict) -> tuple[str, str] | None:
    """Extract (relation_type, target_name) from a relation object, or None.

    Probes the alternate key spellings enola may use; returns None when either
    the relation type or the target name cannot be found.
    """
    if not isinstance(relation, dict):
        return None

    relation_type = None
    for key in _RELATION_TYPE_KEYS:
        value = relation.get(key)
        if isinstance(value, str) and value:
            relation_type = value
            break

    target_name = None
    for key in _RELATION_TARGET_KEYS:
        value = relation.get(key)
        if isinstance(value, str) and value:
            target_name = value
            break

    if relation_type is None or target_name is None:
        return None

    return relation_type, target_name
