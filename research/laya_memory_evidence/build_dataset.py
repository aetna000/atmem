"""Build unlabeled multilingual teacher inputs from authentic conversations.

This module deliberately does not infer memory labels. Generated conversations
and translations are not accepted.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import heapq
import json
from pathlib import Path
import re
from typing import Any, Iterable, Iterator

import fsspec
import pyarrow.parquet as pq


FORMAT = "atmem-memory-decision-candidate-v1"
MANIFEST_FORMAT = "atmem-authentic-conversation-manifest-v1"
WILDCHAT_REPO = "allenai/WildChat-1M"
WILDCHAT_REVISION = "7d6490e462285cf85d91eabea0f9a954fbddcd1f"
WILDCHAT_LICENSE = "ODC-By-1.0"
LUFY_REPO = "RuiSumida/LUFY"
LUFY_REVISION = "1b3fcb1682eae1f034ecdce03e183ebd3f34d179"
LUFY_LICENSE = "CC-BY-4.0"
WILDCHAT_SHARDS = tuple(
    f"data/train-{index:05d}-of-00014.parquet" for index in range(14)
)

# Fixed final-corpus policy. The language ranking is versioned from Microsoft
# AI Diffusion Q2 2026 joined to Unicode CLDR language populations, then shaped
# by the product requirement. A missing authentic source must fail the build;
# generated or translated rows are never acceptable quota substitutes.
LANGUAGE_SHARES = {
    "english": 0.50,
    "chinese": 0.20,
    "french": 0.05,
    "spanish": 0.05,
    "arabic": 0.05,
    "german": 0.05,
    "portuguese": 0.01,
    "japanese": 0.01,
    "russian": 0.01,
    "indonesian": 0.01,
    "korean": 0.01,
}
OTHER_LANGUAGE_SHARE = 0.05
UNUSABLE_LANGUAGE_TAGS = {"", "unknown", "nolang"}
WILDCHAT_MAX_CANDIDATES_PER_CONVERSATION = 4
STRATUM_SHARES = {
    "memory_intent": 0.25,
    "chronology": 0.35,
    "representative": 0.40,
}

_MEMORY_INTENT = re.compile(
    r"(?:\b(?:remember|forget|prefer|always|never|call me|my name is|from now on|"
    r"no longer|actually|changed my)\b|"
    r"记住|忘记|我喜欢|我叫|从现在|不再|其实|"
    r"souviens|oublie|je préfère|appelle[- ]moi|désormais|en fait|"
    r"recuerda|olvida|prefiero|llámame|a partir de ahora|en realidad|"
    r"تذكر|انس|أفضل|اسمي|من الآن|في الواقع|"
    r"merk dir|vergiss|ich bevorzuge|nenn mich|ab jetzt|eigentlich|"
    r"lembre|esqueça|prefiro|me chame|a partir de agora|"
    r"覚えて|忘れて|好み|これから|実は|"
    r"запомни|забудь|предпочитаю|зови меня|с этого момента|"
    r"ingat|lupakan|saya lebih suka|panggil saya|mulai sekarang|"
    r"기억해|잊어|선호|불러 줘|지금부터)",
    re.IGNORECASE,
)

_SECRET_OR_PII = re.compile(
    r"(?:\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b|"
    r"\bhf_[A-Za-z0-9]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b|"
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_]{0,32})?"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key|secret)"
    r"\s*[:=]\s*['\"]?(?:https?://[^\s'\"]+/[A-Za-z0-9_-]{20,}|[A-Za-z0-9_./+=-]{20,})|"
    r"\b(?:bearer\s+)[A-Za-z0-9_./+=-]{16,}\b|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+|"
    r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w))",
    re.IGNORECASE,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value else None


def _language(value: Any) -> str:
    value = _clean(value)
    return value.casefold() if value else "unknown"


def _split(source: str, group_id: str) -> str:
    bucket = int(_digest([source, group_id])[:8], 16) % 100
    if bucket < 90:
        return "train"
    if bucket < 95:
        return "validation"
    return "calibration"


def _safe_turns(raw_turns: Any) -> list[dict[str, str]] | None:
    if not isinstance(raw_turns, list):
        return None
    turns: list[dict[str, str]] = []
    for index, turn in enumerate(raw_turns):
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", "")).casefold()
        text = _clean(turn.get("content"))
        if role not in {"user", "assistant"} or text is None:
            continue
        if bool(turn.get("toxic", False)) or _SECRET_OR_PII.search(text):
            return None
        turns.append({"turn_id": f"t{index:04d}", "role": role, "content": text})
    return turns if any(turn["role"] == "user" for turn in turns) else None


def _bounded_state(
    turns: list[dict[str, str]], *, candidate_position: int | None = None,
    maximum_turns: int = 16,
) -> dict[str, Any]:
    user_positions = [index for index, turn in enumerate(turns) if turn["role"] == "user"]
    candidate_position = user_positions[-1] if candidate_position is None else candidate_position
    if candidate_position not in user_positions:
        raise ValueError("candidate_position must identify a user turn")
    start = max(0, candidate_position - maximum_turns + 1)
    window = turns[start : candidate_position + 1]
    candidate_id = turns[candidate_position]["turn_id"]
    return {
        "turns": window,
        "candidate_turn_id": candidate_id,
        "prior_user_turn_ids": [
            turn["turn_id"] for turn in window
            if turn["role"] == "user" and turn["turn_id"] != candidate_id
        ],
    }


def _candidate(
    *, source: str, group_id: str, record_id: str, language: str,
    country: str | None, turns: list[dict[str, str]], license_id: str,
    revision: str, collection: str, candidate_position: int | None = None,
    selection_stratum: str = "representative",
) -> dict[str, Any]:
    state = _bounded_state(turns, candidate_position=candidate_position)
    identity = [source, group_id, record_id, state["candidate_turn_id"]]
    model_input_digest = "sha256:" + _digest(state)
    return {
        "format": FORMAT,
        "candidate_id": "mdc-" + _digest(identity)[:24],
        "split": _split(source, group_id),
        "authorized_input": state,
        # input_digest is the unique source-bound row identity; the separate
        # model_input_digest permits exact cross-scope duplicate discovery.
        "input_digest": "sha256:" + _digest([identity, state]),
        "model_input_digest": model_input_digest,
        "provenance": {
            "source": source,
            "repo_id": WILDCHAT_REPO if source == "wildchat-1m" else LUFY_REPO,
            "revision": revision,
            "license": license_id,
            "collection": collection,
            "group_id": group_id,
            "record_id": record_id,
            "language": language,
            "country": country,
            "selection_stratum": selection_stratum,
        },
    }


def _wildchat_candidate_positions(turns: list[dict[str, str]]) -> list[int]:
    positions = [index for index, turn in enumerate(turns) if turn["role"] == "user"]
    return positions[-WILDCHAT_MAX_CANDIDATES_PER_CONVERSATION:]


def _selection_stratum(state: dict[str, Any]) -> str:
    candidate_id = state["candidate_turn_id"]
    text = next(turn["content"] for turn in state["turns"] if turn["turn_id"] == candidate_id)
    if _MEMORY_INTENT.search(text):
        return "memory_intent"
    if state["prior_user_turn_ids"]:
        return "chronology"
    return "representative"


def _wildchat_url(shard: str) -> str:
    return f"https://huggingface.co/datasets/{WILDCHAT_REPO}/resolve/{WILDCHAT_REVISION}/{shard}"


def _wildchat_tables(columns: list[str], root: Path | None = None) -> Iterator[tuple[str, Any]]:
    for shard in WILDCHAT_SHARDS:
        if root is not None:
            # Direct paths are materially more reliable than a buffered fsspec
            # wrapper on removable/exFAT volumes.
            parquet = pq.ParquetFile(root / shard)
            for group in range(parquet.num_row_groups):
                yield shard, parquet.read_row_group(group, columns=columns)
        else:
            location = _wildchat_url(shard)
            stream = fsspec.open(location, "rb", block_size=8 * 1024 * 1024).open()
            try:
                parquet = pq.ParquetFile(stream)
                for group in range(parquet.num_row_groups):
                    yield shard, parquet.read_row_group(group, columns=columns)
            finally:
                stream.close()


def count_wildchat_inventory(
    root: Path | None = None, *, excluded_input_digests: set[str] | None = None,
) -> tuple[Counter[str], dict[str, Counter[str]]]:
    """Count only rows that can pass the later conversation-content gates."""
    counts: Counter[str] = Counter()
    strata: dict[str, Counter[str]] = defaultdict(Counter)
    _ = excluded_input_digests  # duplicates are retained for the global graph
    for _, table in _wildchat_tables(["language", "toxic", "conversation"], root):
        for row in table.to_pylist():
            language = _language(row.get("language"))
            if language in UNUSABLE_LANGUAGE_TAGS or bool(row.get("toxic", False)):
                continue
            turns = _safe_turns(row.get("conversation"))
            if turns is None:
                continue
            for position in _wildchat_candidate_positions(turns):
                state = _bounded_state(turns, candidate_position=position)
                stratum = _selection_stratum(state)
                counts[language] += 1
                strata[language][stratum] += 1
    return counts, strata


def count_wildchat_languages(
    root: Path | None = None, *, excluded_input_digests: set[str] | None = None,
) -> Counter[str]:
    return count_wildchat_inventory(root, excluded_input_digests=excluded_input_digests)[0]


def _allocate_strata(available: Counter[str], total: int) -> dict[str, int]:
    allocated = {name: 0 for name in STRATUM_SHARES}
    for _ in range(total):
        eligible = [name for name in STRATUM_SHARES if allocated[name] < available.get(name, 0)]
        if not eligible:
            raise ValueError("candidate strata cannot satisfy the language quota")
        name = max(eligible, key=lambda value: (STRATUM_SHARES[value] / (allocated[value] + 1), value))
        allocated[name] += 1
    return {name: count for name, count in allocated.items() if count}


def _allocate_quotas(
    counts: Counter[str], total: int, *, alpha: float = 0.3,
    english_cap_fraction: float = 0.50,
) -> dict[str, int]:
    """Allocate XLM-R-style smoothed language quotas deterministically."""
    if total <= 0 or not counts:
        raise ValueError("a positive target and non-empty language counts are required")
    weights = {language: count**alpha for language, count in counts.items() if count > 0}
    quotas = {language: 0 for language in weights}
    english_names = {"english", "en"}
    english_cap = int(total * english_cap_fraction)
    for _ in range(total):
        eligible = [
            language for language in weights
            if quotas[language] < counts[language]
            and not (language in english_names and quotas[language] >= english_cap)
        ]
        if not eligible:
            raise ValueError("source inventory cannot satisfy requested language caps")
        language = max(eligible, key=lambda name: (weights[name] / (quotas[name] + 1), name))
        quotas[language] += 1
    return {language: quota for language, quota in quotas.items() if quota}


def _allocate_language_policy(
    counts: Counter[str], total: int, *, preselected_english: int = 0,
) -> dict[str, int]:
    """Apply the fixed 50/40/5/5 policy to the source inventory."""
    if total <= 0 or total % 100:
        raise ValueError("target must be a positive multiple of 100")
    desired = {
        language: int(total * share)
        for language, share in LANGUAGE_SHARES.items()
    }
    other_total = int(total * OTHER_LANGUAGE_SHARE)
    if sum(desired.values()) + other_total != total:
        raise AssertionError("configured language shares do not total 100%")
    if preselected_english > desired["english"]:
        raise ValueError("preselected English rows exceed the 50% policy")
    desired["english"] -= preselected_english
    shortages = {
        language: {"available": counts.get(language, 0), "required": quota}
        for language, quota in desired.items()
        if counts.get(language, 0) < quota
    }
    if shortages:
        raise ValueError(f"source inventory cannot satisfy fixed language policy: {shortages}")
    quotas = dict(desired)
    other_counts = Counter({
        language: count
        for language, count in counts.items()
        if language not in LANGUAGE_SHARES
        and language not in UNUSABLE_LANGUAGE_TAGS
        and count > 0
    })
    quotas.update(_allocate_quotas(
        other_counts, other_total, alpha=0.3, english_cap_fraction=0.0,
    ))
    if sum(quotas.values()) + preselected_english != total:
        raise AssertionError("language policy allocation does not equal target")
    return {language: quota for language, quota in quotas.items() if quota}


@dataclass(order=True)
class _Ranked:
    negative_rank: int
    candidate: dict[str, Any] = field(compare=False)


def sample_wildchat(
    quotas: dict[str, int], root: Path | None = None,
    *, excluded_input_digests: set[str] | None = None,
    stratum_inventory: dict[str, Counter[str]] | None = None,
) -> list[dict[str, Any]]:
    if stratum_inventory is None:
        _, stratum_inventory = count_wildchat_inventory(
            root, excluded_input_digests=excluded_input_digests,
        )
    stratum_quotas = {
        language: _allocate_strata(stratum_inventory.get(language, Counter()), quota)
        for language, quota in quotas.items()
    }
    reservoirs: dict[tuple[str, str], list[_Ranked]] = defaultdict(list)
    seen_candidate_ids: set[str] = set()
    columns = ["conversation_hash", "conversation", "language", "country", "toxic"]
    for shard, table in _wildchat_tables(columns, root):
        for row_index, row in enumerate(table.to_pylist()):
            language = _language(row.get("language"))
            quota = quotas.get(language, 0)
            if quota == 0 or bool(row.get("toxic", False)):
                continue
            turns = _safe_turns(row.get("conversation"))
            if turns is None:
                continue
            group_id = str(row["conversation_hash"])
            for position in _wildchat_candidate_positions(turns):
                state = _bounded_state(turns, candidate_position=position)
                stratum = _selection_stratum(state)
                stratum_quota = stratum_quotas.get(language, {}).get(stratum, 0)
                if stratum_quota == 0:
                    continue
                candidate = _candidate(
                    source="wildchat-1m", group_id=group_id,
                    record_id=f"{shard}:{row_index}", language=language,
                    country=_clean(row.get("country")), turns=turns,
                    license_id=WILDCHAT_LICENSE, revision=WILDCHAT_REVISION,
                    collection="organic_production_human_ai",
                    candidate_position=position, selection_stratum=stratum,
                )
                if candidate["candidate_id"] in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(candidate["candidate_id"])
                rank = int(_digest(candidate["candidate_id"]), 16)
                heap = reservoirs[(language, stratum)]
                item = _Ranked(-rank, candidate)
                if len(heap) < stratum_quota:
                    heapq.heappush(heap, item)
                elif item > heap[0]:
                    heapq.heapreplace(heap, item)
    short = {
        f"{language}:{stratum}": (len(reservoirs[(language, stratum)]), quota)
        for language, values in stratum_quotas.items() for stratum, quota in values.items()
        if len(reservoirs[(language, stratum)]) < quota
    }
    if short:
        raise ValueError(f"eligible WildChat inventory fell below quota: {short}")
    return [
        item.candidate for key in sorted(reservoirs) for item in reservoirs[key]
    ]


def load_lufy(turns_path: Path) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    excluded_groups: set[tuple[str, str]] = set()
    for line in turns_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        role = str(row.get("role", "")).casefold()
        text = _clean(row.get("content"))
        group = (str(row.get("user_name", "unknown")), str(row.get("conversation_id", "unknown")))
        if text is not None and _SECRET_OR_PII.search(text):
            excluded_groups.add(group)
            continue
        if role not in {"user", "assistant"} or text is None:
            continue
        groups[group].append({
            "turn_id": f"t{len(groups[group]):04d}",
            "role": role,
            "content": text,
        })
    candidates = []
    for (user, conversation), turns in sorted(groups.items()):
        if (user, conversation) in excluded_groups:
            continue
        if not any(turn["role"] == "user" for turn in turns):
            continue
        group_id = f"{user}:{conversation}"
        for position, turn in enumerate(turns):
            if turn["role"] != "user":
                continue
            state = _bounded_state(turns, candidate_position=position)
            candidates.append(_candidate(
                source="lufy", group_id=group_id,
                record_id=f"{group_id}:{turn['turn_id']}",
                language="english", country=None, turns=turns,
                license_id=LUFY_LICENSE, revision=LUFY_REVISION,
                collection="controlled_longitudinal_human_ai_study",
                candidate_position=position,
                selection_stratum=_selection_stratum(state),
            ))
    return candidates


def _validate(rows: Iterable[dict[str, Any]], expected: int) -> dict[str, Any]:
    rows = list(rows)
    ids = [row["candidate_id"] for row in rows]
    inputs = [row["input_digest"] for row in rows]
    groups = [(row["provenance"]["source"], row["provenance"]["group_id"]) for row in rows]
    if len(rows) != expected:
        raise ValueError(f"expected {expected} rows, found {len(rows)}")
    if len(set(ids)) != len(ids) or len(set(inputs)) != len(inputs):
        raise ValueError("candidate IDs and source-bound row digests must be unique")
    group_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row, group in zip(rows, groups):
        group_splits[group].add(row["split"])
    if any(len(splits) != 1 for splits in group_splits.values()):
        raise ValueError("a source conversation crosses dataset splits")
    return {
        "rows": len(rows),
        "sources": dict(sorted(Counter(row["provenance"]["source"] for row in rows).items())),
        "languages": dict(sorted(Counter(row["provenance"]["language"] for row in rows).items())),
        "splits": dict(sorted(Counter(row["split"] for row in rows).items())),
        "countries": len({row["provenance"]["country"] for row in rows if row["provenance"]["country"]}),
        "unique_groups": len(set(groups)),
    }


def build(
    *, output: Path, target: int, lufy_turns: Path | None,
    wildchat_root: Path | None = None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    lufy_all = load_lufy(lufy_turns) if lufy_turns else []
    # The user-authorized policy is to retain every privacy-eligible authentic
    # LUFY user turn, not one terminal row per conversation.
    lufy = sorted(lufy_all, key=lambda row: row["candidate_id"])
    if len(lufy) >= target:
        raise ValueError("LUFY inventory unexpectedly exceeds the full target")
    lufy_input_digests = {row["input_digest"] for row in lufy}
    language_counts, stratum_inventory = count_wildchat_inventory(
        wildchat_root, excluded_input_digests=lufy_input_digests,
    )
    quotas = _allocate_language_policy(
        language_counts, target, preselected_english=len(lufy),
    )
    rows = sample_wildchat(
        quotas, wildchat_root, excluded_input_digests=lufy_input_digests,
        stratum_inventory=stratum_inventory,
    ) + lufy
    rows.sort(key=lambda row: row["candidate_id"])
    summary = _validate(rows, target)

    data_path = output / "candidates.jsonl"
    with data_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(_canonical(row) + "\n")
    manifest = {
        "format": MANIFEST_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rows": target,
        "unlabeled": True,
        "generated_or_translated_conversations": 0,
        "source_revisions": {
            "wildchat-1m": {"repo_id": WILDCHAT_REPO, "revision": WILDCHAT_REVISION, "license": WILDCHAT_LICENSE},
            "lufy": {"repo_id": LUFY_REPO, "revision": LUFY_REVISION, "license": LUFY_LICENSE, "included": bool(lufy)},
        },
        "sampling": {
            "method": "fixed_language_policy_with_authentic_memory_intent_and_chronology_strata_v2",
            "selection_strata": {
                "target_shares": STRATUM_SHARES,
                "actual": dict(sorted(Counter(
                    row["provenance"]["selection_stratum"] for row in rows
                ).items())),
                "wildchat_max_candidates_per_conversation": WILDCHAT_MAX_CANDIDATES_PER_CONVERSATION,
                "lufy_policy": "all_privacy_eligible_user_turns",
            },
            "ranking_source": {
                "ai_adoption": "Microsoft AI Diffusion Q2 2026",
                "language_population": "Unicode CLDR territory language populations",
                "limitations": [
                    "Language-level active-user counts are estimates, not a direct census.",
                    "Microsoft reports that Chinese adoption is under-measured because several domestic tools are absent.",
                ],
            },
            "target_shares": {
                **LANGUAGE_SHARES,
                "all_remaining_supported_languages": OTHER_LANGUAGE_SHARE,
            },
            "other_language_smoothing_alpha": 0.3,
            "quotas": dict(sorted(quotas.items())),
        },
        "summary": summary,
        "files": {data_path.name: {"sha256": _file_digest(data_path), "bytes": data_path.stat().st_size}},
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=int, default=130_000)
    parser.add_argument("--lufy-turns", type=Path)
    parser.add_argument("--wildchat-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(
        output=args.output, target=args.target, lufy_turns=args.lufy_turns,
        wildchat_root=args.wildchat_root,
    ), indent=2))


if __name__ == "__main__":
    main()
