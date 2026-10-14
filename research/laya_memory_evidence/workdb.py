"""SQLite work database for corpus-wide authentic conversation labeling."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator


SCHEMA_VERSION = 2
JUDGES = ("codex", "claude")
REVIEW_VIEWS = (
    "duplicate_clusters",
    "scope_chronology",
    "stratified",
    "contradiction_outliers",
)


SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS source_dataset (
    source_id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    license TEXT NOT NULL,
    collection_method TEXT NOT NULL,
    human_origin_evidence TEXT NOT NULL,
    inventory_digest TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(repo_id, revision)
) STRICT;

CREATE TABLE IF NOT EXISTS conversation (
    conversation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_dataset(source_id),
    source_conversation_id TEXT NOT NULL,
    source_user_id TEXT,
    source_session_id TEXT,
    scope_key TEXT NOT NULL,
    language TEXT NOT NULL,
    script TEXT,
    content_digest TEXT NOT NULL,
    UNIQUE(source_id, source_conversation_id)
) STRICT;

CREATE TABLE IF NOT EXISTS turn (
    turn_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversation(conversation_id),
    turn_order INTEGER NOT NULL CHECK(turn_order >= 0),
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    observed_at TEXT,
    UNIQUE(conversation_id, turn_order)
) STRICT;

CREATE TABLE IF NOT EXISTS candidate (
    candidate_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversation(conversation_id),
    candidate_turn_id TEXT NOT NULL REFERENCES turn(turn_id),
    scope_key TEXT NOT NULL,
    authorized_input_json TEXT NOT NULL CHECK(json_valid(authorized_input_json)),
    input_digest TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL,
    risk_tags_json TEXT NOT NULL CHECK(json_valid(risk_tags_json)),
    eligibility TEXT NOT NULL CHECK(eligibility IN ('eligible', 'excluded')),
    exclusion_reason TEXT,
    source_split_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK((eligibility = 'eligible' AND exclusion_reason IS NULL) OR eligibility = 'excluded')
) STRICT;

CREATE TABLE IF NOT EXISTS fingerprint (
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    method TEXT NOT NULL,
    revision TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY(candidate_id, method, revision)
) STRICT;

CREATE TABLE IF NOT EXISTS embedding (
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    model TEXT NOT NULL,
    revision TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK(dimensions > 0),
    vector BLOB NOT NULL,
    vector_digest TEXT NOT NULL,
    PRIMARY KEY(candidate_id, model, revision)
) STRICT;

CREATE TABLE IF NOT EXISTS duplicate_edge (
    left_candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    right_candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    edge_kind TEXT NOT NULL CHECK(edge_kind IN ('exact', 'semantic')),
    method_revision TEXT NOT NULL,
    score REAL NOT NULL,
    same_scope INTEGER NOT NULL CHECK(same_scope IN (0, 1)),
    PRIMARY KEY(left_candidate_id, right_candidate_id, edge_kind, method_revision),
    CHECK(left_candidate_id < right_candidate_id)
) STRICT;

CREATE TABLE IF NOT EXISTS duplicate_cluster (
    cluster_id TEXT PRIMARY KEY,
    method_revision TEXT NOT NULL,
    canonical_candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    cluster_digest TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE IF NOT EXISTS duplicate_member (
    cluster_id TEXT NOT NULL REFERENCES duplicate_cluster(cluster_id),
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    PRIMARY KEY(cluster_id, candidate_id),
    UNIQUE(candidate_id)
) STRICT;

CREATE TABLE IF NOT EXISTS judge_run (
    run_id TEXT PRIMARY KEY,
    judge TEXT NOT NULL CHECK(judge IN ('codex', 'claude')),
    cli_version TEXT NOT NULL,
    model TEXT NOT NULL,
    rubric_digest TEXT NOT NULL,
    schema_digest TEXT NOT NULL,
    pass_kind TEXT NOT NULL CHECK(pass_kind IN (
        'first_pass', 'duplicate_clusters', 'scope_chronology',
        'stratified', 'contradiction_outliers'
    )),
    pass_number INTEGER NOT NULL CHECK(pass_number >= 1),
    status TEXT NOT NULL CHECK(status IN ('running', 'complete', 'frozen', 'failed')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    run_digest TEXT,
    UNIQUE(judge, pass_kind, pass_number),
    UNIQUE(run_id, judge, pass_kind, pass_number)
) STRICT;

CREATE TABLE IF NOT EXISTS query_receipt (
    receipt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES judge_run(run_id),
    candidate_id TEXT REFERENCES candidate(candidate_id),
    query_kind TEXT NOT NULL,
    parameters_json TEXT NOT NULL CHECK(json_valid(parameters_json)),
    result_ids_json TEXT NOT NULL CHECK(json_valid(result_ids_json)),
    query_digest TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS judgment (
    judgment_id INTEGER PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    run_id TEXT NOT NULL REFERENCES judge_run(run_id),
    judge TEXT NOT NULL CHECK(judge IN ('codex', 'claude')),
    pass_kind TEXT NOT NULL,
    pass_number INTEGER NOT NULL CHECK(pass_number >= 1),
    prior_judgment_id INTEGER REFERENCES judgment(judgment_id),
    disposition TEXT NOT NULL CHECK(disposition IN (
        'STORE', 'UPDATE', 'DUPLICATE', 'DO_NOT_STORE', 'FORGET', 'REVIEW'
    )),
    memory_class TEXT NOT NULL,
    decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
    decision_digest TEXT NOT NULL,
    change_reason TEXT,
    query_receipt_ids_json TEXT NOT NULL CHECK(json_valid(query_receipt_ids_json)),
    output_digest TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    validation_state TEXT NOT NULL CHECK(validation_state IN ('valid', 'invalid')),
    created_at TEXT NOT NULL,
    UNIQUE(candidate_id, judge, pass_kind, pass_number),
    FOREIGN KEY(run_id, judge, pass_kind, pass_number)
        REFERENCES judge_run(run_id, judge, pass_kind, pass_number)
) STRICT;

CREATE TABLE IF NOT EXISTS judge_freeze (
    judge TEXT PRIMARY KEY CHECK(judge IN ('codex', 'claude')),
    frozen_at TEXT NOT NULL,
    first_pass_rows INTEGER NOT NULL,
    completed_review_views_json TEXT NOT NULL CHECK(json_valid(completed_review_views_json)),
    history_digest TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS labeling_policy_event (
    event_id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL CHECK(mode IN ('dual_codex_claude', 'codex_only_credit_exhausted')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS adjudication (
    adjudication_id INTEGER PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id),
    adjudicator TEXT NOT NULL,
    decision_json TEXT CHECK(decision_json IS NULL OR json_valid(decision_json)),
    decision_digest TEXT,
    status TEXT NOT NULL CHECK(status IN ('accepted', 'rejected', 'unresolved')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS work_queue (
    work_id INTEGER PRIMARY KEY,
    judge TEXT NOT NULL CHECK(judge IN ('codex', 'claude')),
    pass_kind TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    candidate_ids_json TEXT NOT NULL CHECK(json_valid(candidate_ids_json)),
    token_estimate INTEGER NOT NULL CHECK(token_estimate >= 0),
    state TEXT NOT NULL CHECK(state IN ('pending', 'leased', 'complete', 'failed')),
    lease_owner TEXT,
    lease_expires_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    last_error TEXT,
    UNIQUE(judge, pass_kind, cluster_key)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_turn_conversation_order ON turn(conversation_id, turn_order);
CREATE INDEX IF NOT EXISTS idx_candidate_scope ON candidate(scope_key, candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_language ON candidate(language, eligibility);
CREATE INDEX IF NOT EXISTS idx_duplicate_edge_left ON duplicate_edge(left_candidate_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_edge_right ON duplicate_edge(right_candidate_id);
CREATE INDEX IF NOT EXISTS idx_judgment_candidate_judge ON judgment(candidate_id, judge, judgment_id DESC);
CREATE INDEX IF NOT EXISTS idx_work_queue_state ON work_queue(judge, pass_kind, state, work_id);

CREATE VIEW IF NOT EXISTS latest_valid_judgment AS
SELECT j.*
FROM judgment j
JOIN (
    SELECT candidate_id, judge, MAX(judgment_id) AS judgment_id
    FROM judgment
    WHERE validation_state = 'valid'
    GROUP BY candidate_id, judge
) latest ON latest.judgment_id = j.judgment_id;

CREATE VIEW IF NOT EXISTS final_label AS
SELECT
    c.candidate_id,
    CASE
      WHEN a.status = 'accepted' THEN 'adjudicated'
      WHEN (SELECT mode FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1)
           = 'codex_only_credit_exhausted' AND jf_c.judge IS NULL THEN 'pending_freeze'
      WHEN (SELECT mode FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1)
           = 'codex_only_credit_exhausted' AND cj.judgment_id IS NULL THEN 'pending_judgment'
      WHEN (SELECT mode FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1)
           = 'codex_only_credit_exhausted' THEN 'single_judge_reviewed'
      WHEN jf_c.judge IS NULL OR jf_l.judge IS NULL THEN 'pending_freeze'
      WHEN cj.judgment_id IS NULL OR lj.judgment_id IS NULL THEN 'pending_judgment'
      WHEN cj.decision_digest = lj.decision_digest THEN 'agreed'
      ELSE 'disagreement'
    END AS final_status,
    CASE
      WHEN a.status = 'accepted' THEN a.decision_json
      WHEN (SELECT mode FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1)
           = 'codex_only_credit_exhausted' THEN cj.decision_json
      WHEN cj.decision_digest = lj.decision_digest THEN cj.decision_json
      ELSE NULL
    END AS final_decision_json,
    cj.judgment_id AS codex_judgment_id,
    lj.judgment_id AS claude_judgment_id,
    a.adjudication_id
FROM candidate c
LEFT JOIN latest_valid_judgment cj
  ON cj.candidate_id = c.candidate_id AND cj.judge = 'codex'
LEFT JOIN latest_valid_judgment lj
  ON lj.candidate_id = c.candidate_id AND lj.judge = 'claude'
LEFT JOIN judge_freeze jf_c ON jf_c.judge = 'codex'
LEFT JOIN judge_freeze jf_l ON jf_l.judge = 'claude'
LEFT JOIN adjudication a ON a.adjudication_id = (
    SELECT MAX(a2.adjudication_id) FROM adjudication a2
    WHERE a2.candidate_id = c.candidate_id
);
"""


IMMUTABLE_TABLES = (
    "source_dataset", "conversation", "turn", "candidate", "fingerprint",
    "embedding", "duplicate_edge", "duplicate_cluster", "duplicate_member",
    "query_receipt", "judgment", "judge_freeze", "labeling_policy_event",
    "adjudication",
)


def _install_immutable_triggers(connection: sqlite3.Connection) -> None:
    for table in IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            name = f"deny_{operation.casefold()}_{table}"
            connection.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {name}
                BEFORE {operation} ON {table}
                BEGIN
                    SELECT RAISE(ABORT, '{table} is append-only');
                END
            """)


def initialize(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1, SCHEMA_VERSION):
        connection.close()
        raise RuntimeError(f"unsupported work database schema {version}")
    with connection:
        if version == 1:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS labeling_policy_event (
                    event_id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL CHECK(mode IN (
                        'dual_codex_claude', 'codex_only_credit_exhausted'
                    )),
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                ) STRICT
            """)
            connection.execute("DROP VIEW IF EXISTS final_label")
        connection.executescript(SCHEMA)
        _install_immutable_triggers(connection)
        if connection.execute("SELECT COUNT(*) FROM labeling_policy_event").fetchone()[0] == 0:
            connection.execute(
                "INSERT INTO labeling_policy_event(mode, reason, created_at) VALUES(?, ?, ?)",
                ("dual_codex_claude", "initial preferred labeling policy", "schema-initialization"),
            )
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def insert_json(connection: sqlite3.Connection, sql: str, values: tuple[Any, ...]) -> None:
    normalized = tuple(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if isinstance(value, (dict, list)) else value
        for value in values
    )
    connection.execute(sql, normalized)


def integrity_report(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "schema_version": connection.execute("PRAGMA user_version").fetchone()[0],
        "integrity": integrity,
        "foreign_key_errors": [tuple(row) for row in foreign_keys],
        "counts": {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "source_dataset", "conversation", "turn", "candidate",
                "duplicate_cluster", "judge_run", "judgment", "adjudication",
                "work_queue",
            )
        },
    }
