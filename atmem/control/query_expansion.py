"""Local, content-free query expansion matching AtBot's v1 rules."""

from __future__ import annotations


def expand_query_v1(query: str) -> list[str]:
    clean = " ".join(query.split())
    if not clean:
        return []
    lowered = clean.casefold()
    expansions = [clean]
    concept_rules = (
        (("fav food", "favorite food", "favourite food"), ("favorite food", "food preference", "preferred meal", "likes to eat")),
        (("fav car", "favorite car", "favourite car"), ("favorite car", "car preference", "preferred vehicle")),
        (("fav book", "favorite book", "favourite book"), ("favorite book", "book preference", "preferred reading")),
    )
    for triggers, values in concept_rules:
        if any(trigger in lowered for trigger in triggers):
            expansions.extend(values)
    normalized: list[str] = []
    for value in expansions:
        item = " ".join(str(value).split())[:200]
        if item and item.casefold() not in {row.casefold() for row in normalized}:
            normalized.append(item)
        if len(normalized) >= 6:
            break
    return normalized
