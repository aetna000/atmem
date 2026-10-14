import json
from pathlib import Path

import pytest

from research.laya_memory_evidence.decision_contract import (
    DISPOSITION_TO_AUTHORITY_PATHS,
    authority_path_allowed,
    validate_understanding_proposal,
)


CORPUS = Path("research/laya_formation/runs/openclaw-100-20261012/corpus.json")


def test_historical_operational_100_dispositions_have_explicit_authority_paths():
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert len(rows) == 100
    observed = {row["expected_disposition"] for row in rows}
    assert observed <= set(DISPOSITION_TO_AUTHORITY_PATHS)
    assert all(DISPOSITION_TO_AUTHORITY_PATHS[item] for item in observed)


@pytest.mark.parametrize(("disposition", "path"), [
    ("STORE", "ADD"),
    ("UPDATE", "SUPERSEDE"),
    ("DUPLICATE", "NOOP"),
    ("DO_NOT_STORE", "REJECT"),
    ("FORGET", "GOVERNED_FORGET"),
    ("REVIEW", "WITHHOLD_FOR_REVIEW"),
])
def test_authoritative_mapping_is_explicit(disposition, path):
    assert authority_path_allowed(disposition, path)


def test_duplicate_requires_same_scope_target():
    with pytest.raises(ValueError, match="same-scope"):
        validate_understanding_proposal({
            "disposition": "DUPLICATE",
            "meaning": {"relation_to_prior": "repeats"},
            "duplicate_of_turn_ids": [],
        })


def test_do_not_store_cannot_create_understanding():
    with pytest.raises(ValueError, match="cannot create"):
        validate_understanding_proposal({
            "disposition": "DO_NOT_STORE",
            "meaning": {"relation_to_prior": "not_applicable"},
        })
