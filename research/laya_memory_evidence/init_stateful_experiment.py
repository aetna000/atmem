"""Initialize a scaled, stateful memory experiment from the authentic work DB."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from atmem import Memory
from atmem.semantic import default_index_path

from .scale_manifest import (
    allocate_scope_groups, requested_allocation, validate_scale_manifest,
)


FORMAT = "atmem-stateful-experiment-init-v1"
WORK_SCHEMA_VERSION = 1
SELECTION_PROTOCOL = "authentic-state-enriched-stratification-v2"

LANGUAGE_SHARES = {
    "english": 0.50, "chinese": 0.20,
    "arabic": 0.05, "french": 0.05, "german": 0.05, "spanish": 0.05,
    "indonesian": 0.01, "japanese": 0.01, "korean": 0.01,
    "portuguese": 0.01, "russian": 0.01,
}
MEMORY_CUES = (
    "my name", "call me", "i prefer", "i like", "i dislike", "i hate",
    "i live", "i work", "remember", "from now on", "always", "never",
    "me llamo", "prefiero", "recuerda", "a partir de ahora",
    "je m'appelle", "je préfère", "souviens", "désormais",
    "ich heiße", "ich bevorzuge", "merke dir", "ab jetzt",
    "我叫", "我喜欢", "我不喜欢", "记住", "从现在开始", "我的",
    "اسمي", "أفضل", "أحب", "تذكر", "من الآن",
)
RELATIONAL_CUES = (
    "actually", "instead", "not anymore", "changed", "correction",
    "forget", "delete", "don't remember", "do not remember",
    "en realidad", "olvida", "corrijo", "désormais", "oublie",
    "eigentlich", "vergiss", "stattdessen", "其实", "改为", "忘记",
    "في الواقع", "انس", "بدلاً",
)


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
CREATE TABLE scale_group(
  group_id TEXT PRIMARY KEY,
  split_family TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL UNIQUE,
  history_count INTEGER NOT NULL CHECK(history_count >= 0),
  challenge_count INTEGER NOT NULL CHECK(challenge_count = 1),
  assignment_digest TEXT NOT NULL
) STRICT;
CREATE TABLE baseline_observation(
  observation_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL REFERENCES scale_group(group_id),
  scope_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
  role TEXT NOT NULL CHECK(role='user'),
  content TEXT NOT NULL,
  source_digest TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('awaiting_adjudication','accepted','rejected')),
  UNIQUE(group_id, ordinal)
) STRICT;
CREATE TABLE challenge(
  transition_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL REFERENCES scale_group(group_id),
  split_family TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,
  source_digest TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('blocked_on_baseline','ready','adjudicated','sealed'))
) STRICT;
CREATE TABLE baseline_adjudication(
  receipt_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL REFERENCES baseline_observation(observation_id),
  expected_operation TEXT NOT NULL,
  expected_target_id TEXT,
  expected_response_json TEXT NOT NULL CHECK(json_valid(expected_response_json)),
  pre_state_digest TEXT NOT NULL,
  post_state_digest TEXT NOT NULL,
  judge TEXT NOT NULL,
  judge_revision TEXT NOT NULL,
  receipt_digest TEXT NOT NULL UNIQUE,
  accepted INTEGER NOT NULL CHECK(accepted IN (0,1)),
  created_at TEXT NOT NULL
) STRICT;
CREATE TABLE snapshot_freeze(
  snapshot_id TEXT PRIMARY KEY,
  adjudication_set_digest TEXT NOT NULL,
  atmem_sqlite_digest TEXT NOT NULL,
  vector_sqlite_digest TEXT NOT NULL,
  manifest_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _selected_conversations(source: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = source.execute(
        """
        WITH latest_judgment AS (
          SELECT candidate_id,disposition FROM (
            SELECT candidate_id,disposition,
                   ROW_NUMBER() OVER (
                     PARTITION BY candidate_id ORDER BY created_at DESC,judgment_id DESC
                   ) AS rn
            FROM judgment WHERE validation_state='valid'
          ) WHERE rn=1
        ), ranked AS (
          SELECT c.candidate_id,c.conversation_id,c.scope_key,c.authorized_input_json,
                 c.input_digest,c.language,t.turn_order,lj.disposition
          FROM candidate c JOIN turn t ON t.turn_id=c.candidate_turn_id
          LEFT JOIN latest_judgment lj ON lj.candidate_id=c.candidate_id
          WHERE c.eligibility='eligible'
        )
        SELECT r.*,dm.cluster_id
        FROM ranked r LEFT JOIN duplicate_member dm ON dm.candidate_id=r.candidate_id
        ORDER BY r.candidate_id
        """
    ).fetchall()
    by_conversation: dict[str, list[tuple[int, str | None]]] = {}
    for row in rows:
        by_conversation.setdefault(str(row["conversation_id"]), []).append(
            (int(row["turn_order"]), row["disposition"])
        )
    for values in by_conversation.values():
        values.sort()
    # A split unit is the transitive closure of security scope, source
    # conversation and semantic-duplicate cluster.  Grouping by only the
    # duplicate cluster allowed one longitudinal scope to leak across splits.
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for row in rows:
        scope_node = "scope:" + str(row["scope_key"])
        conversation_node = "conversation:" + str(row["conversation_id"])
        union(scope_node, conversation_node)
        if row["cluster_id"] is not None:
            union(scope_node, "cluster:" + str(row["cluster_id"]))
    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = dict(row)
        authorized = json.loads(value.pop("authorized_input_json"))
        prior_ids = set(authorized.get("prior_user_turn_ids") or ())
        prior = [
            turn for turn in authorized.get("turns") or ()
            if turn.get("role") == "user" and turn.get("turn_id") in prior_ids
        ][-3:]
        candidate_turn_id = authorized.get("candidate_turn_id")
        candidate_turn = next(
            (turn for turn in authorized.get("turns") or () if turn.get("turn_id") == candidate_turn_id),
            None,
        )
        if not candidate_turn or candidate_turn.get("role") != "user" or not str(candidate_turn.get("content") or "").strip():
            continue
        earlier = [
            disposition for order, disposition in by_conversation[value["conversation_id"]]
            if order < int(value["turn_order"])
        ][-3:]
        memory_dispositions = {"STORE", "UPDATE", "DUPLICATE", "FORGET"}
        prior_memory_labels = sum(item in memory_dispositions for item in earlier)
        prior_relational_labels = sum(item in {"UPDATE", "DUPLICATE", "FORGET"} for item in earlier)
        candidate_label_priority = {
            "UPDATE": 4, "DUPLICATE": 4, "FORGET": 4,
            "STORE": 3, "REVIEW": 1,
        }.get(str(value.get("disposition") or ""), 0)
        component_root = find("scope:" + str(value["scope_key"]))
        leakage_group = "component-" + hashlib.sha256(
            component_root.encode("utf-8")
        ).hexdigest()[:24]
        record = {
            **value,
            "group_id": leakage_group,
            "prior_turns": prior,
            "candidate_turn": candidate_turn,
            "selector_candidate_disposition": value.get("disposition") or "UNJUDGED",
            "selector_prior_memory_labels": prior_memory_labels,
            "selector_prior_relational_labels": prior_relational_labels,
            "memory_priority": (
                prior_relational_labels,
                prior_memory_labels,
                candidate_label_priority,
                int(any(cue in str(candidate_turn["content"]).casefold() for cue in RELATIONAL_CUES)),
                int(any(cue in str(candidate_turn["content"]).casefold() for cue in MEMORY_CUES)),
                int(bool(prior)),
            ),
        }
        current = candidates.get(leakage_group)
        if current is None or (
            record["memory_priority"], len(record["prior_turns"]), record["candidate_id"]
        ) > (
            current["memory_priority"], len(current["prior_turns"]), current["candidate_id"]
        ):
            candidates[leakage_group] = record
    return list(candidates.values())


def _history_mix(available: dict[int, int], rows: int, history: int) -> dict[int, int]:
    choices: list[tuple[tuple[int, int, int], dict[int, int]]] = []
    for x3 in range(min(available.get(3, 0), history // 3, rows) + 1):
        remainder_after_3 = history - 3 * x3
        max_x2 = min(available.get(2, 0), remainder_after_3 // 2, rows - x3)
        for x2 in range(max_x2 + 1):
            x1 = remainder_after_3 - 2 * x2
            x0 = rows - x1 - x2 - x3
            counts = {0: x0, 1: x1, 2: x2, 3: x3}
            if all(0 <= counts[key] <= available.get(key, 0) for key in counts):
                choices.append(((x0, x3, x2), counts))
    if not choices:
        raise RuntimeError(
            f"cannot select {rows} groups with {history} history rows from {available}"
        )
    targets = {
        0: round(rows * 0.5625),
        1: round(rows * 0.3125),
        2: round(rows * 0.0625),
    }
    targets[3] = rows - sum(targets.values())
    return min(
        choices,
        key=lambda item: (
            sum(abs(item[1][key] - targets[key]) for key in range(4)),
            -item[1][3], -item[1][2], item[1][0],
        ),
    )[1]


def _select_language_cohort(
    records: list[dict[str, Any]], *, total_rows: int, history_rows: int, seed: int,
) -> list[dict[str, Any]]:
    quotas = {name: round(total_rows * share) for name, share in LANGUAGE_SHARES.items()}
    quotas["__other__"] = total_rows - sum(quotas.values())
    history_targets = {
        name: round(history_rows * count / total_rows)
        for name, count in quotas.items()
    }
    history_targets["__other__"] += history_rows - sum(history_targets.values())

    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in quotas}
    for row in records:
        language = str(row.get("language") or "unknown")
        bucket = language if language in LANGUAGE_SHARES else "__other__"
        buckets[bucket].append(row)
    selected: list[dict[str, Any]] = []
    for bucket, count in quotas.items():
        by_history: dict[int, list[dict[str, Any]]] = {index: [] for index in range(4)}
        for row in buckets[bucket]:
            by_history[len(row["prior_turns"])].append(row)
        mix = _history_mix(
            {key: len(value) for key, value in by_history.items()},
            count, history_targets[bucket],
        )
        for history_count, take in mix.items():
            ranked = sorted(
                by_history[history_count],
                key=lambda row: (
                    -row["memory_priority"][0], -row["memory_priority"][1],
                    -row["memory_priority"][2],
                    hashlib.sha256(
                        f"{seed}:{row['group_id']}".encode("utf-8")
                    ).digest(),
                    row["candidate_id"],
                ),
            )
            if len(ranked) < take:
                raise RuntimeError(f"language cohort {bucket} is undersupplied")
            selected.extend(ranked[:take])
    if len(selected) != total_rows or sum(len(row["prior_turns"]) for row in selected) != history_rows:
        raise AssertionError("stratified cohort does not match frozen row totals")
    return selected


def initialize(source_db: Path, output_dir: Path, *, scale_percent: str, seed: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        quick = source.execute("PRAGMA quick_check").fetchone()[0]
        if quick != "ok":
            raise RuntimeError(f"source database integrity failed: {quick}")
        records = _selected_conversations(source)
        requested = requested_allocation(scale_percent)
        challenge_total = sum(
            requested[name]
            for name in ("train", "validation", "calibration", "sealed_test", "holdback")
        )
        records = _select_language_cohort(
            records, total_rows=challenge_total,
            history_rows=requested["state_history"], seed=seed,
        )
        by_group = {row["group_id"]: row for row in records}
        scale = allocate_scope_groups(
            ({
                "group_id": row["group_id"],
                "history_count": len(row["prior_turns"]),
                "challenge_count": 1,
            } for row in records),
            experiment_scale_percent=scale_percent,
            seed=seed,
        )
        validate_scale_manifest(scale, require_minimum=True)

        work_path = output_dir / "transition-work.sqlite3"
        work = sqlite3.connect(work_path)
        try:
            work.executescript(SCHEMA)
            metadata = {
                "schema_version": str(WORK_SCHEMA_VERSION),
                "format": FORMAT,
                "created_at": _now(),
                "source_db_digest": _sha(source_db.read_bytes()),
                "scale_manifest_digest": _sha(_canonical(scale)),
            }
            work.executemany("INSERT INTO schema_meta(key,value) VALUES (?,?)", sorted(metadata.items()))
            for assignment in scale["assignments"]:
                row = by_group[assignment["group_id"]]
                assignment_digest = _sha(_canonical(assignment))
                work.execute(
                    "INSERT INTO scale_group VALUES (?,?,?,?,?,?,?,?)",
                    (
                        assignment["group_id"], assignment["split_family"], row["scope_key"],
                        row["conversation_id"], row["candidate_id"], assignment["history_count"],
                        assignment["challenge_count"], assignment_digest,
                    ),
                )
                for ordinal, turn in enumerate(row["prior_turns"]):
                    content = str(turn["content"])
                    observation_id = "base_" + hashlib.sha256(
                        f"{assignment['group_id']}:{turn['turn_id']}".encode("utf-8")
                    ).hexdigest()[:24]
                    work.execute(
                        "INSERT INTO baseline_observation VALUES (?,?,?,?,?,?,?,?)",
                        (
                            observation_id, assignment["group_id"], row["scope_key"], ordinal,
                            "user", content, _sha(content), "awaiting_adjudication",
                        ),
                    )
                challenge_content = str(row["candidate_turn"]["content"])
                transition_id = "transition_" + hashlib.sha256(row["candidate_id"].encode("utf-8")).hexdigest()[:24]
                work.execute(
                    "INSERT INTO challenge VALUES (?,?,?,?,?,?,?,?)",
                    (
                        transition_id, assignment["group_id"], assignment["split_family"],
                        row["scope_key"], row["candidate_id"], challenge_content,
                        _sha(challenge_content), "blocked_on_baseline",
                    ),
                )
            work.commit()
            if work.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("initialized transition work DB failed integrity check")
            conflicts = work.execute(
                """SELECT scope_id FROM scale_group GROUP BY scope_id
                   HAVING COUNT(DISTINCT split_family) != 1 LIMIT 1"""
            ).fetchone()
            if conflicts is not None:
                raise RuntimeError("initialized cohort leaks one scope across split families")
        finally:
            work.close()

        atmem_path = output_dir / "atmem-baseline-working.sqlite3"
        memory = Memory(atmem_path)
        memory.close()
        vector_path = default_index_path(atmem_path)
        manifest = {
            "format": FORMAT,
            "created_at": _now(),
            "experiment_scale_percent": scale["experiment_scale_percent"],
            "seed": seed,
            "state": "initialized_awaiting_baseline_adjudication",
            "source_database": {"path": source_db.name, "digest": _sha(source_db.read_bytes())},
            "scale_manifest": scale,
            "selection": {
                "protocol": SELECTION_PROTOCOL,
                "uses_labels_as_training_targets": False,
                "description": (
                    "Superseded isolated weak labels are sampling signals only; "
                    "all canonical state and transition targets require fresh "
                    "state-aware adjudication."
                ),
                "history_count_distribution": dict(sorted(Counter(
                    int(item["history_count"]) for item in scale["assignments"]
                ).items())),
                "candidate_signal_distribution": dict(sorted(Counter(
                    str(by_group[item["group_id"]]["selector_candidate_disposition"])
                    for item in scale["assignments"]
                ).items())),
                "groups_with_prior_memory_signal": sum(
                    int(by_group[item["group_id"]]["selector_prior_memory_labels"] > 0)
                    for item in scale["assignments"]
                ),
                "groups_with_prior_relational_signal": sum(
                    int(by_group[item["group_id"]]["selector_prior_relational_labels"] > 0)
                    for item in scale["assignments"]
                ),
            },
            "artifacts": {
                "transition_work": {"path": work_path.name, "digest": _sha(work_path.read_bytes())},
                "atmem_sqlite": {"path": atmem_path.name, "digest": _sha(atmem_path.read_bytes())},
                "vector_sqlite": {"path": vector_path.name, "digest": _sha(vector_path.read_bytes())},
            },
            "publication_eligible": False,
            "publication_blockers": [
                "baseline_adjudication_incomplete",
                "canonical_state_not_applied",
                "snapshot_not_frozen",
                "privacy_and_license_gates_not_run",
            ],
        }
        manifest["manifest_digest"] = _sha(_canonical(manifest))
        (output_dir / "init-manifest.json").write_bytes(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        )
        return manifest
    except Exception:
        # Preserve the directory for forensic inspection. The manifest is only
        # written on success, so an incomplete initialization cannot be mistaken
        # for a publishable artifact.
        raise
    finally:
        source.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scale-percent", default="10")
    parser.add_argument("--seed", type=int, default=410)
    args = parser.parse_args()
    manifest = initialize(args.source_db, args.output_dir, scale_percent=args.scale_percent, seed=args.seed)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "manifest_digest": manifest["manifest_digest"],
        "requested_counts": manifest["scale_manifest"]["requested_counts"],
        "achieved_counts": manifest["scale_manifest"]["achieved_counts"],
        "publication_eligible": manifest["publication_eligible"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
