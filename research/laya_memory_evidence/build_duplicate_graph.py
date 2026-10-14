"""Build the corpus-wide exact and multilingual semantic duplicate graph.

This is an offline research utility.  Its optional ML dependencies are kept out
of the AtMem package so enabling the decision model never changes a user's
PyTorch installation.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Callable, Iterable, Sequence

import numpy as np

from .workdb import initialize, integrity_report, transaction


DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
METHOD_REVISION = "atmem-duplicate-graph-v1"
_SPACE = re.compile(r"\s+")


def normalized_text(value: str) -> str:
    """Return a conservative Unicode exact-match representation."""

    return _SPACE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


def exact_fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(normalized_text(value).encode("utf-8")).hexdigest()


def _digest(parts: Iterable[str]) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class _UnionFind:
    def __init__(self, values: Sequence[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            value, self.parent[value] = self.parent[value], root
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root


@dataclass(frozen=True)
class CandidateText:
    candidate_id: str
    scope_key: str
    turn_order: int
    text: str


def load_candidate_texts(connection: sqlite3.Connection) -> list[CandidateText]:
    rows = connection.execute(
        """
        SELECT c.candidate_id, c.scope_key, t.turn_order, t.content
        FROM candidate c
        JOIN turn t ON t.turn_id = c.candidate_turn_id
        WHERE c.eligibility = 'eligible'
        -- Length bucketing sharply reduces tokenizer padding while preserving
        -- deterministic graph identities (clusters are sorted before hashing).
        ORDER BY length(t.content), c.candidate_id
        """
    )
    return [CandidateText(row[0], row[1], row[2], row[3]) for row in rows]


def exact_edges(rows: Sequence[CandidateText]) -> list[tuple[str, str, str, float, int]]:
    groups: dict[str, list[CandidateText]] = defaultdict(list)
    for row in rows:
        groups[exact_fingerprint(row.text)].append(row)
    edges: list[tuple[str, str, str, float, int]] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        canonical = min(members, key=lambda item: (item.scope_key, item.turn_order, item.candidate_id))
        for member in members:
            if member.candidate_id == canonical.candidate_id:
                continue
            left, right = sorted((canonical.candidate_id, member.candidate_id))
            edges.append((left, right, "exact", 1.0, int(canonical.scope_key == member.scope_key)))
    return edges


def _semantic_edges(
    rows: Sequence[CandidateText], vectors: np.ndarray, *, threshold: float, neighbours: int
) -> list[tuple[str, str, str, float, int]]:
    try:
        import hnswlib  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised by offline command
        raise RuntimeError("install hnswlib in the isolated research environment") from exc

    index = hnswlib.Index(space="cosine", dim=int(vectors.shape[1]))
    index.init_index(max_elements=len(rows), ef_construction=240, M=32, random_seed=41)
    index.add_items(vectors, np.arange(len(rows)))
    index.set_ef(max(100, neighbours * 4))
    labels, distances = index.knn_query(vectors, k=min(neighbours + 1, len(rows)))
    seen: set[tuple[int, int]] = set()
    edges: list[tuple[str, str, str, float, int]] = []
    exact = [exact_fingerprint(row.text) for row in rows]
    for source_index, (matches, match_distances) in enumerate(zip(labels, distances)):
        for target_index, distance in zip(matches, match_distances):
            target_index = int(target_index)
            if target_index == source_index:
                continue
            pair = tuple(sorted((source_index, target_index)))
            if pair in seen:
                continue
            seen.add(pair)
            score = 1.0 - float(distance)
            if score < threshold or exact[source_index] == exact[target_index]:
                continue
            left_row, right_row = rows[pair[0]], rows[pair[1]]
            left, right = sorted((left_row.candidate_id, right_row.candidate_id))
            edges.append((left, right, "semantic", score, int(left_row.scope_key == right_row.scope_key)))
    return edges


def _encode(rows: Sequence[CandidateText], model: str, revision: str, batch_size: int) -> np.ndarray:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - exercised by offline command
        raise RuntimeError("install sentence-transformers in the isolated research environment") from exc
    encoder = SentenceTransformer(model, revision=revision, trust_remote_code=False)
    # E5 requires a prefix even for symmetric semantic-similarity inputs.
    values = ["query: " + row.text for row in rows]
    vectors = encoder.encode(
        values,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def build_duplicate_graph(
    database: Path,
    *,
    model: str = DEFAULT_MODEL,
    revision: str = DEFAULT_REVISION,
    threshold: float = 0.985,
    neighbours: int = 16,
    batch_size: int = 128,
    encoder: Callable[[Sequence[CandidateText], str, str, int], np.ndarray] = _encode,
    include_semantic: bool = True,
) -> dict[str, object]:
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    connection = initialize(database)
    try:
        if connection.execute("SELECT COUNT(*) FROM duplicate_cluster").fetchone()[0]:
            raise RuntimeError("duplicate graph already exists; immutable graph cannot be overwritten")
        rows = load_candidate_texts(connection)
        if not rows:
            raise RuntimeError("no eligible candidates")
        edges = exact_edges(rows)
        vectors: np.ndarray | None = None
        if include_semantic:
            vectors = encoder(rows, model, revision, batch_size)
            if vectors.ndim != 2 or vectors.shape[0] != len(rows):
                raise ValueError("encoder returned an invalid embedding matrix")
            edges.extend(_semantic_edges(rows, vectors, threshold=threshold, neighbours=neighbours))

        union = _UnionFind([row.candidate_id for row in rows])
        for left, right, _kind, _score, _same_scope in edges:
            union.union(left, right)
        components: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            components[union.find(row.candidate_id)].append(row.candidate_id)

        method = f"{METHOD_REVISION};model={model}@{revision};cosine>={threshold};k={neighbours}"
        with transaction(connection):
            connection.executemany(
                "INSERT INTO fingerprint VALUES (?, 'unicode_nfkc_casefold_ws_sha256', ?, ?)",
                ((row.candidate_id, METHOD_REVISION, exact_fingerprint(row.text)) for row in rows),
            )
            connection.executemany(
                "INSERT INTO fingerprint VALUES (?, 'authorized_state_sha256', ?, ?)",
                (
                    (row[0], METHOD_REVISION, "sha256:" + hashlib.sha256(row[1].encode("utf-8")).hexdigest())
                    for row in connection.execute(
                        "SELECT candidate_id, authorized_input_json FROM candidate ORDER BY candidate_id"
                    )
                ),
            )
            if vectors is not None:
                connection.executemany(
                    "INSERT INTO embedding VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        (
                            row.candidate_id,
                            model,
                            revision,
                            int(vectors.shape[1]),
                            np.asarray(vector, dtype="<f2").tobytes(),
                            _digest([np.asarray(vector, dtype="<f2").tobytes().hex()]),
                        )
                        for row, vector in zip(rows, vectors)
                    ),
                )
            connection.executemany(
                "INSERT INTO duplicate_edge VALUES (?, ?, ?, ?, ?, ?)",
                ((left, right, kind, method, score, same_scope) for left, right, kind, score, same_scope in edges),
            )
            for members in sorted(components.values(), key=lambda values: min(values)):
                members.sort()
                cluster_digest = _digest(members)
                cluster_id = "dup-" + cluster_digest.removeprefix("sha256:")[:24]
                connection.execute(
                    "INSERT INTO duplicate_cluster VALUES (?, ?, ?, ?)",
                    (cluster_id, method, members[0], cluster_digest),
                )
                connection.executemany(
                    "INSERT INTO duplicate_member VALUES (?, ?)",
                    ((cluster_id, candidate_id) for candidate_id in members),
                )
        report = integrity_report(connection)
        edge_counts = dict(connection.execute(
            "SELECT edge_kind, COUNT(*) FROM duplicate_edge GROUP BY edge_kind"
        ).fetchall())
        multi_member = connection.execute(
            """SELECT COUNT(*) FROM (
                SELECT cluster_id FROM duplicate_member GROUP BY cluster_id HAVING COUNT(*) > 1
            )"""
        ).fetchone()[0]
        return {
            "database": str(database),
            "method_revision": method,
            "candidates": len(rows),
            "dimensions": None if vectors is None else int(vectors.shape[1]),
            "edges": edge_counts,
            "clusters": len(components),
            "multi_member_clusters": multi_member,
            "integrity": report,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--threshold", type=float, default=0.985)
    parser.add_argument("--neighbours", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--exact-only", action="store_true")
    args = parser.parse_args()
    result = build_duplicate_graph(
        args.database,
        model=args.model,
        revision=args.revision,
        threshold=args.threshold,
        neighbours=args.neighbours,
        batch_size=args.batch_size,
        include_semantic=not args.exact_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
