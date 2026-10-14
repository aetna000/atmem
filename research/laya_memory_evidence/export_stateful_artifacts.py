"""Export the frozen 10%-scale stateful database and typed transition dataset."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from atmem import Memory
from atmem.core.canonical import canonical_json
from atmem.laya_formation.formation_v2 import (
    MUTATING_OPERATIONS,
    TARGET_REQUIRED,
    context_sufficient_question,
    durable_question,
    evaluation_request,
    future_utility_question,
    memory_class_question,
    operation_question,
    target_question,
)

from .transition_contract import validate_transition_example
from .build_dataset import _SECRET_OR_PII


DATASET_FORMAT = "atmem-stateful-memory-transitions-manifest-v2"
DATABASE_FORMAT = "atmem-stateful-memory-database-publication-v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")
            count += 1
    return count


def _memories(retrieval_json: str) -> list[dict[str, Any]]:
    """Convert the frozen production-retrieval output into the public contract."""

    result = []
    for row in json.loads(retrieval_json):
        content = str(row.get("content") or "")
        digest = _sha(content)
        result.append({
            "id": str(row["id"]), "content": content, "lifecycle": "active",
            "source_digest": digest, "content_digest": digest,
            "memory_class": str(row.get("memory_class") or "unknown"),
            "retrieval_score": float(row.get("retrieval_score") or 0.0),
        })
    return result


def _canonical_records(memory: Memory, scope_id: str) -> list[dict[str, Any]]:
    result = []
    for row in memory.store.list_records(scope_id, statuses=("active",)):
        raw = row.get("raw") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        result.append({
            "id": str(row["id"]), "content": str(row.get("content") or ""),
            "status": str(row.get("status") or "active"),
            "generation": int(row.get("generation") or 0),
            "memory_class": str(raw.get("memory_class") or "unknown"),
        })
    return result


def _choice_response(request_id: str, question: dict[str, Any], choice: str) -> dict[str, Any]:
    option_ids = [str(item["id"]) for item in question["options"]]
    if choice not in option_ids:
        raise ValueError(f"expected choice {choice!r} is not available")
    return {
        "format": "laya-choice-response-v2", "schema_version": "2.0.0",
        "request_id": request_id, "question_id": question["question_id"],
        "type": "choice", "choice": choice,
        "probabilities": {item: float(item == choice) for item in option_ids},
        "confidence": 1.0,
    }


def _noul_response(request_id: str, question: dict[str, Any], value: bool) -> dict[str, Any]:
    return {
        "format": "laya-noul-response-v2", "schema_version": "2.0.0",
        "request_id": request_id, "question_id": question["question_id"],
        "type": "noul", "noul": float(value),
    }


def _score_response(request_id: str, question: dict[str, Any], level: int) -> dict[str, Any]:
    if not 0 <= level < len(question["criteria"]):
        raise ValueError("future utility level is outside the frozen rubric")
    probabilities = {
        str(index): float(index == level) for index in range(len(question["criteria"]))
    }
    return {
        "format": "laya-score-response-v2", "schema_version": "2.0.0",
        "request_id": request_id, "question_id": question["question_id"],
        "type": "score", "score": float(level), "probabilities": probabilities,
        "confidence": 1.0,
        "legend": {
            str(index): description
            for index, description in enumerate(question["criteria"])
        },
    }


def _questions(expected: dict[str, Any], memories: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Any]]:
    context = bool(expected["context_sufficient"])
    durable = bool(expected["durable"])
    result: list[tuple[dict[str, Any], Any]] = [
        (context_sufficient_question(), context),
    ]
    if not context:
        return result
    result.append((durable_question(), durable))
    if not durable:
        return result
    result.append((memory_class_question(), str(expected["memory_class"])))
    operation = str(expected["operation"])
    if operation == "REVIEW":
        return result
    result.append((operation_question(), operation))
    if operation in TARGET_REQUIRED and len(memories) > 1:
        result.append((target_question(memories), str(expected["target_memory_id"])))
    if operation in MUTATING_OPERATIONS - {"FORGET_EXISTING"}:
        result.append((future_utility_question(), int(expected["future_utility_level"])))
    return result


def _response(request_id: str, question: dict[str, Any], value: Any) -> dict[str, Any]:
    if question["type"] == "choice":
        return _choice_response(request_id, question, str(value))
    if question["type"] == "noul":
        return _noul_response(request_id, question, bool(value))
    return _score_response(request_id, question, int(value))


def _source_inventory(source: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_id"]): dict(row)
        for row in source.execute("SELECT * FROM source_dataset ORDER BY source_id")
    }


def _provenance(source: sqlite3.Connection, candidate_id: str) -> dict[str, Any]:
    row = source.execute(
        """SELECT c.candidate_id,c.language,c.risk_tags_json,co.conversation_id,
                  co.source_id,s.revision,s.license,t.content_digest
           FROM candidate c JOIN conversation co USING(conversation_id)
           JOIN source_dataset s USING(source_id)
           JOIN turn t ON t.turn_id=c.candidate_turn_id
           WHERE c.candidate_id=?""",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"source candidate is missing: {candidate_id}")
    return {
        "source_id": str(row["source_id"]),
        "source_revision": str(row["revision"]),
        "conversation_id": str(row["conversation_id"]),
        "license": str(row["license"]),
        "adjudication_mode": "two_pass_cli_weak_supervision",
        "content_digest": "sha256:" + str(row["content_digest"]).removeprefix("sha256:"),
        "language": str(row["language"]),
        "risk_tags": json.loads(str(row["risk_tags_json"])),
    }


def export_dataset(
    *, work_db: Path, atmem_db: Path, source_db: Path,
    snapshot_manifest_path: Path, output: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    data_dir = output / "data"
    records_dir = output / "records"
    data_dir.mkdir()
    records_dir.mkdir()
    snapshot = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
    inventory = {item["path"]: item for item in snapshot["inventory"]}
    vector_item = inventory["atmem.vectors.sqlite3"]
    work = sqlite3.connect(f"file:{work_db}?mode=ro", uri=True)
    work.row_factory = sqlite3.Row
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    typed_by_split: dict[str, list[dict[str, Any]]] = {
        name: [] for name in ("train", "validation", "calibration", "sealed_test")
    }
    holdback: list[dict[str, Any]] = []
    transition_counts: Counter[str] = Counter()
    selected_counts: Counter[str] = Counter()
    judge_modes: dict[str, Counter[str]] = {
        name: Counter() for name in ("train", "validation", "calibration", "sealed_test")
    }
    action_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    selected_language_counts: Counter[str] = Counter()
    holdback_language_counts: Counter[str] = Counter()
    split_language_counts: dict[str, Counter[str]] = {
        name: Counter() for name in ("train", "validation", "calibration", "sealed_test")
    }
    source_records: list[dict[str, Any]] = []
    privacy_exclusions: list[dict[str, Any]] = []
    try:
        source_records = list(_source_inventory(source).values())
        rows = work.execute(
            """SELECT c.*,g.conversation_id,a.authority,a.expected_json,
                      a.pre_state_digest,a.expected_post_state_digest,a.accepted,
                      r.retrieval_json,r.receipt_json AS retrieval_receipt_json,
                      r.retrieval_digest
               FROM challenge c JOIN scale_group g USING(group_id)
               LEFT JOIN challenge_adjudication a USING(transition_id)
               LEFT JOIN challenge_retrieval r USING(transition_id)
               ORDER BY c.split_family,c.transition_id"""
        ).fetchall()
        for row in rows:
            provenance = _provenance(source, str(row["candidate_id"]))
            selected_language_counts[provenance["language"]] += 1
            if row["split_family"] != "holdback":
                selected_counts[str(row["split_family"])] += 1
            if _SECRET_OR_PII.search(str(row["content"])):
                privacy_exclusions.append({
                    "transition_id": str(row["transition_id"]),
                    "partition": str(row["split_family"]),
                    "source_id": provenance["source_id"],
                    "content_digest": provenance["content_digest"],
                    "reason": "privacy_or_secret_pattern",
                })
                continue
            if row["split_family"] == "holdback":
                holdback_language_counts[provenance["language"]] += 1
                holdback.append({
                    "id": str(row["transition_id"]),
                    "observation": str(row["content"]),
                    "language": provenance["language"],
                    "source": provenance["source_id"],
                    "conversation_id": provenance["conversation_id"],
                    "content_digest": provenance["content_digest"],
                    "snapshot_digest": snapshot["manifest_digest"],
                })
                continue
            if row["expected_json"] is None or int(row["accepted"] or 0) != 1:
                continue
            if row["retrieval_json"] is None or row["retrieval_receipt_json"] is None:
                raise RuntimeError(f"frozen retrieval is missing: {row['transition_id']}")
            language_counts[provenance["language"]] += 1
            split_language_counts[str(row["split_family"])][provenance["language"]] += 1
            judgment_count = int(work.execute(
                "SELECT COUNT(*) FROM challenge_judgment WHERE transition_id=?",
                (row["transition_id"],),
            ).fetchone()[0])
            judge_modes[str(row["split_family"])][
                f"{row['authority']}-two-pass" + ("-plus-adjudication" if judgment_count == 3 else "")
            ] += 1
            expected = json.loads(str(row["expected_json"]))
            memories = _memories(str(row["retrieval_json"]))
            canonical_records = _canonical_records(memory, str(row["scope_id"]))
            if any(_SECRET_OR_PII.search(item["content"]) for item in canonical_records):
                raise RuntimeError(f"canonical-state privacy scan failed: {row['transition_id']}")
            operation = str(expected["operation"])
            action_counts[operation] += 1
            transition_counts[str(row["split_family"])] += 1
            generation = memory.store.record_generation(str(row["scope_id"]))
            observation = {
                "id": str(row["transition_id"]), "content": str(row["content"]),
                "speaker_role": "user", "source_digest": str(row["source_digest"]),
            }
            for question, value in _questions(expected, memories):
                request_id = "dataset_" + _sha([
                    row["transition_id"], question["question_id"],
                    snapshot["manifest_digest"],
                ])[7:39]
                request = evaluation_request(
                    request_id=request_id, scope_id=str(row["scope_id"]),
                    canonical_generation=generation, observation=observation,
                    retrieved_memories=memories, question=question,
                    retriever_revision="atmem-frozen-scoped-retrieval-v2",
                    requested_top_k=8,
                )
                response = _response(request_id, question, value)
                example = {
                    "format": "memory-transition-example-v2",
                    "schema_version": "2.0.0",
                    "transition_id": f"{row['transition_id']}:{question['question_id']}",
                    "trajectory_id": str(row["group_id"]),
                    "partition": str(row["split_family"]),
                    "pre_state": {
                        "snapshot_id": "atmem-stateful-10pct-v2",
                        "snapshot_digest": snapshot["manifest_digest"],
                        "vector_snapshot_id": "atmem-stateful-10pct-vectors-v2",
                        "vector_snapshot_digest": vector_item["sha256"],
                        "canonical_generation": generation,
                        "canonical_state_digest": str(row["pre_state_digest"]),
                        "canonical_records": canonical_records,
                    },
                    "request": request, "expected_response": response,
                    "retrieval_evidence": {
                        "receipt": json.loads(str(row["retrieval_receipt_json"])),
                        "digest": str(row["retrieval_digest"]),
                    },
                    "expected_operation": operation,
                    "expected_target_id": expected.get("target_memory_id"),
                    "required_evidence_memory_ids": list(expected.get("evidence_memory_ids") or ()),
                    "expected_post_state_digest": str(row["expected_post_state_digest"]),
                    "acceptable_abstention": operation == "REVIEW",
                    "provenance": {
                        key: provenance[key] for key in (
                            "source_id", "source_revision", "conversation_id",
                            "license", "adjudication_mode", "content_digest",
                        )
                    },
                    "viewer": {
                        "id": str(row["transition_id"]), "expected": operation,
                        "category": str(expected["memory_class"]),
                        "observation": str(row["content"]),
                        "why": ", ".join(expected.get("reason_codes") or ()),
                        "language": provenance["language"],
                        "source": provenance["source_id"],
                        "question_type": question["type"],
                        "question_id": question["question_id"],
                    },
                }
                # The validator intentionally sees only the portable contract;
                # viewer fields are an export convenience, not model input.
                validate_transition_example({k: v for k, v in example.items() if k != "viewer"})
                typed_by_split[str(row["split_family"])].append(example)
    finally:
        memory.close()
        source.close()
        work.close()

    file_inventory: list[dict[str, Any]] = []
    coverage = {
        split: {
            "selected": selected_counts[split], "accepted": transition_counts[split],
            "fraction": transition_counts[split] / selected_counts[split]
            if selected_counts[split] else 0.0,
        }
        for split in typed_by_split
    }
    failures = [split for split, item in coverage.items() if item["fraction"] < 0.90]
    if failures:
        raise RuntimeError(f"accepted transition coverage is below 90%: {failures}")
    for split, examples in typed_by_split.items():
        public_split = "test" if split == "sealed_test" else split
        jsonl = records_dir / f"decisions-{public_split}.jsonl"
        _jsonl(jsonl, examples)
        parquet_rows = [{**row["viewer"], **{k: v for k, v in row.items() if k != "viewer"}} for row in examples]
        parquet = data_dir / f"{public_split}.parquet"
        pq.write_table(pa.Table.from_pylist(parquet_rows), parquet, compression="zstd")
        file_inventory.extend({
            "path": path.relative_to(output).as_posix(), "size": path.stat().st_size,
            "sha256": _sha_file(path),
        } for path in (jsonl, parquet))
    holdback_path = data_dir / "holdback.parquet"
    pq.write_table(pa.Table.from_pylist(holdback), holdback_path, compression="zstd")
    file_inventory.append({
        "path": holdback_path.relative_to(output).as_posix(),
        "size": holdback_path.stat().st_size, "sha256": _sha_file(holdback_path),
    })
    exclusions_path = records_dir / "privacy-exclusions.jsonl"
    _jsonl(exclusions_path, privacy_exclusions)
    file_inventory.append({
        "path": exclusions_path.relative_to(output).as_posix(),
        "size": exclusions_path.stat().st_size,
        "sha256": _sha_file(exclusions_path),
    })
    manifest = {
        "format": DATASET_FORMAT, "created_at": _now(),
        "experiment_scale_percent": snapshot["experiment_scale_percent"],
        "snapshot_manifest_digest": snapshot["manifest_digest"],
        "transition_counts": dict(transition_counts),
        "transition_coverage": coverage,
        "judge_modes": {key: dict(value) for key, value in judge_modes.items()},
        "typed_example_counts": {key: len(value) for key, value in typed_by_split.items()},
        "holdback_blinded_count": len(holdback),
        "action_counts": dict(action_counts), "language_counts": dict(language_counts),
        "selected_language_counts": dict(selected_language_counts),
        "holdback_language_counts": dict(holdback_language_counts),
        "split_language_counts": {
            key: dict(value) for key, value in split_language_counts.items()
        },
        "language_power": {
            language: {
                "sealed_test": split_language_counts["sealed_test"][language],
                "calibration": split_language_counts["calibration"][language],
                "eligible_for_quality_gate": (
                    split_language_counts["sealed_test"][language] >= 100
                    and split_language_counts["calibration"][language] >= 50
                ),
            }
            for language in sorted(language_counts)
        },
        "sources": source_records, "machine_labels_are_human_ground_truth": False,
        "selection": snapshot["selection"],
        "synthetic_conversation_rows": 0, "locomo_rows": 0,
        "privacy_exclusion_count": len(privacy_exclusions),
        "privacy_exclusion_counts": dict(Counter(
            item["partition"] for item in privacy_exclusions
        )),
        "gates": {
            "privacy_and_secret_scan_clear": True,
            "license_provenance_complete": all(
                item.get("revision") and item.get("license") for item in source_records
            ),
            "scope_split_isolation": snapshot["split_scope_isolation"],
            "minimum_transition_coverage": 0.90,
        },
        "inventory": sorted(file_inventory, key=lambda item: item["path"]),
    }
    manifest["manifest_digest"] = _sha(manifest)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(_dataset_card(manifest, typed_by_split), encoding="utf-8")
    return manifest


def _dataset_card(manifest: dict[str, Any], splits: dict[str, list[dict[str, Any]]]) -> str:
    candidates = []
    seen = set()
    for name in ("train", "validation", "calibration", "sealed_test"):
        for item in splits[name]:
            row = item["viewer"]
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            candidates.append(row)
    preview = []
    for operation in (
        "STORE_NEW", "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE",
        "REVIEW", "DO_NOT_STORE",
    ):
        match = next((row for row in candidates if row["expected"] == operation), None)
        if match is not None:
            preview.append(match)
    for row in candidates:
        if len(preview) == 12:
            break
        if row in preview:
            continue
        if row["category"] not in {item["category"] for item in preview}:
            preview.append(row)
    for row in candidates:
        if len(preview) == 12:
            break
        if row not in preview:
            preview.append(row)
    scale = f"{float(manifest['experiment_scale_percent']):g}"
    table = "\n".join(
        f"| {row['id']} | {row['expected']} | {row['category']} | "
        f"{' '.join(row['observation'].split())[:180].replace('|', '&#124;')} | "
        f"{' '.join(row['why'].split())[:140].replace('|', '&#124;')} |"
        for row in preview
    )
    coverage_table = "\n".join(
        f"| {split} | {item['selected']:,} | {item['accepted']:,} | {100 * item['fraction']:.2f}% |"
        for split, item in manifest["transition_coverage"].items()
    )
    return f"""---
pretty_name: AtMem Stateful Memory Transitions 10%
license: other
task_categories:
- text-classification
- question-answering
configs:
- config_name: transitions
  data_files:
  - split: train
    path: data/train.parquet
  - split: validation
    path: data/validation.parquet
  - split: calibration
    path: data/calibration.parquet
  - split: test
    path: data/test.parquet
- config_name: blinded_holdback
  data_files:
  - split: holdback
    path: data/holdback.parquet
---

# Stateful Memory Transitions — {scale}% scale

Portable, vendor-neutral memory-decision examples from authentic human-origin
conversations. Every supervised row contains an original-language observation,
the bounded same-scope memory state, one strict Choice/Noul/Score question, and
an adjudicated expected response. It does not contain generated conversation
rows, translated replicas, hand-authored replacements, or LoCoMo.

## Data preview

| ID | Expected | Category | Observation | Why |
| --- | --- | --- | --- | --- |
{table}

## Scale and splits

- Stateful transitions: {sum(manifest['transition_counts'].values()):,}
- Typed supervised examples: {sum(manifest['typed_example_counts'].values()):,}
- Blinded holdback observations: {manifest['holdback_blinded_count']:,}
- Privacy/secret exclusions (digest-only audit): {manifest['privacy_exclusion_count']:,}
- Experiment scale: {scale}% of the frozen 50k/20k/5k/5k/20k/30k design
- Snapshot: `{manifest['snapshot_manifest_digest']}`

| Split | Selected transitions | Accepted transitions | Coverage |
| --- | ---: | ---: | ---: |
{coverage_table}

Selection used `{manifest['selection']['protocol']}`. Earlier isolated labels
only stratified authentic-row sampling; they are not targets. Every published
target was re-adjudicated against the frozen scoped state. Two independent
passes must agree on every supervised field; disagreements receive a recorded
third adjudication pass.

The training, validation, calibration and test families are isolated by source
conversation, scope, chronology and duplicate component. Holdback labels are
not published in the supervised configuration.

## Interpretation

These are contextual machine-adjudicated weak-supervision labels, not human
ground truth. The model sees neither language nor source-selection metadata.
Laya classifies bounded questions; a host memory system retains mutation,
authorization and policy authority.

## Sources

- `allenai/WildChat-1M` at the revision in `manifest.json` (ODC-By 1.0).
- `RuiSumida/LUFY` at the revision in `manifest.json` (CC BY 4.0).

The nested `request` and `expected_response` columns are directly usable by any
memory system implementing `laya-evaluation-request-v2`; no AtMem runtime is
required to train or evaluate the classifier contract.
"""


def export_database(*, frozen_dir: Path, work_db: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    names = ("atmem.sqlite3", "atmem.vectors.sqlite3", "snapshot-manifest.json")
    inventory = []
    for name in names:
        source = frozen_dir / name
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = output / name
        shutil.copy2(source, destination)
        inventory.append({"path": name, "size": destination.stat().st_size, "sha256": _sha_file(destination)})
    snapshot = json.loads((frozen_dir / "snapshot-manifest.json").read_text())
    canonical = sqlite3.connect(f"file:{frozen_dir / 'atmem.sqlite3'}?mode=ro", uri=True)
    try:
        unsafe_records = [
            str(row[0]) for row in canonical.execute("SELECT id,content FROM records")
            if _SECRET_OR_PII.search(str(row[1]))
        ]
    finally:
        canonical.close()
    if unsafe_records:
        raise RuntimeError(
            f"canonical database privacy scan failed for {len(unsafe_records)} records"
        )
    manifest = {
        "format": DATABASE_FORMAT, "created_at": _now(),
        "snapshot_manifest_digest": snapshot["manifest_digest"],
        "experiment_scale_percent": snapshot["experiment_scale_percent"],
        "baseline_work_digest": next(
            item["sha256"] for item in snapshot["inventory"]
            if item["path"] == "transition-work.sqlite3"
        ),
        "adjudicated_work_digest": _sha_file(work_db),
        "inventory": inventory,
    }
    manifest["manifest_digest"] = _sha(manifest)
    scale = f"{float(snapshot['experiment_scale_percent']):g}"
    (output / "publication-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "README.md").write_text(f"""---
pretty_name: AtMem Stateful Memory Database 10%
license: other
---

# Stateful Memory Database — {scale}% scale

A loadable, checksum-bound SQLite and multilingual vector-index snapshot built
from redistribution-cleared authentic conversation sources. It is a portable
research fixture: `atmem.sqlite3` is canonical state,
`atmem.vectors.sqlite3` is the derived semantic index, and
`snapshot-manifest.json` binds schema, embedding revision, adjudication receipts
and frozen baseline hashes. Raw adjudication work databases are intentionally
not redistributed because authentic public conversations can contain exposed
credentials; their immutable digests remain bound in the publication manifest.

Verify integrity with `python verify.py`, then query ordinary SQLite tables or
use any compatible host to inspect the scoped state. Scope identifiers are
security boundaries; unrelated scopes must never nominate one another.

```bash
python verify.py
sqlite3 atmem.sqlite3 \
  "SELECT subject_id,status,COUNT(*) FROM records GROUP BY subject_id,status LIMIT 20;"
```

The database repository and transition-dataset repository are independent:
the former is a reproducible state fixture; the latter is the portable typed
model input/target view.
""", encoding="utf-8")
    (output / "verify.py").write_text("""from pathlib import Path
import hashlib, json, sqlite3
root=Path(__file__).parent
m=json.loads((root/'publication-manifest.json').read_text())
for item in m['inventory']:
 p=root/item['path']; h='sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
 assert h==item['sha256'], (item['path'], h)
 if p.suffix=='.sqlite3':
  c=sqlite3.connect(f'file:{p}?mode=ro&immutable=1', uri=True); assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'; c.close()
print('ok', m['manifest_digest'])
""", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-db", type=Path, required=True)
    parser.add_argument("--atmem-db", type=Path, required=True)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--snapshot-manifest", type=Path, required=True)
    parser.add_argument("--dataset-output", type=Path, required=True)
    parser.add_argument("--frozen-dir", type=Path, required=True)
    parser.add_argument("--database-output", type=Path, required=True)
    args = parser.parse_args()
    dataset = export_dataset(
        work_db=args.work_db, atmem_db=args.atmem_db, source_db=args.source_db,
        snapshot_manifest_path=args.snapshot_manifest, output=args.dataset_output,
    )
    database = export_database(
        frozen_dir=args.frozen_dir, work_db=args.work_db,
        output=args.database_output,
    )
    print(json.dumps({"dataset": dataset["manifest_digest"], "database": database["manifest_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
