"""Contract boundary tests, not evidence of coding-task improvement."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from atmem.code.contracts import CodeScope
from atmem.knowledge.contracts import (
    SourceAnchor, SourceSnapshot, ExecutionReceipt, ExperienceProposal,
    StructuralObject, StructuralRelation, ApplicabilityReceipt, CapabilityReceipt,
    source_path,
)

SCOPE = CodeScope("user", "project", "shared", "codex")
DIGEST = "a" * 64
ANCHOR = SourceAnchor("src/main.py", DIGEST, 1, 2)


def examples():
    return [
        ANCHOR,
        SourceSnapshot(SCOPE, "worktree", "2247b35ea1c47c727d7a06e51fa280e12a863ff6", ((ANCHOR.path, DIGEST),), DIGEST),
        ExecutionReceipt("receipt", SCOPE, "producer", "attempt", DIGEST, DIGEST, ("pytest",), 0, DIGEST, "evidence"),
        ExperienceProposal("proposal", SCOPE, DIGEST, "Fix parser", "Observed parser assertion failure", "observed_failure", (ANCHOR,), ("receipt",)),
        StructuralObject("symbol", SCOPE, DIGEST, "symbol", "main", (ANCHOR,), "syntax"),
        StructuralRelation("symbol", None, "calls", "external", "unresolved"),
        ApplicabilityReceipt("proposal", DIGEST, "withheld", ("ANCHOR_CHANGED",)),
        CapabilityReceipt(DIGEST, DIGEST, SCOPE, (("structure", "unverified"),), DIGEST),
    ]


@pytest.mark.parametrize("item", examples())
def test_roundtrip_closed_versioned(item):
    assert type(item).from_dict(item.to_dict()) == item
    row = item.to_dict()
    row["invented"] = True
    with pytest.raises(ValueError):
        type(item).from_dict(row)
    row = item.to_dict()
    row["format"] += "-unknown"
    with pytest.raises(ValueError):
        type(item).from_dict(row)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "./src/main.py", "src//main.py", "src\\main.py", "C:drive", "", ".", "src/../main.py"])
def test_paths_cannot_escape_or_alias(path):
    with pytest.raises(ValueError):
        source_path(path)


@pytest.mark.parametrize("control", [*(chr(code) for code in range(0x20)), "\x7f"])
def test_paths_reject_c0_controls_and_del(control):
    with pytest.raises(ValueError):
        source_path(f"src/file{control}.py")


@pytest.mark.parametrize("path", ["源代码/主程序.py", "مصدر/برنامج.py", "資料/ファイル.py"])
def test_paths_allow_unicode_filenames(path):
    assert source_path(path) == path


@pytest.mark.parametrize("changes", [{"start_line": True}, {"end_line": 0}, {"content_sha256": "x"}, {"start_line": 3}])
def test_anchor_bounds(changes):
    with pytest.raises(ValueError):
        replace(ANCHOR, **changes)


def test_snapshot_manifest_is_immutable_sorted_and_unique():
    item = examples()[1]
    assert item.snapshot_id == SourceSnapshot.from_dict(item.to_dict()).snapshot_id
    assert replace(item, revision="b" * 40).snapshot_id != item.snapshot_id
    for files in [(), (("b.py", DIGEST), ("a.py", DIGEST)), (("a.py", DIGEST), ("a.py", DIGEST))]:
        with pytest.raises(ValueError):
            replace(item, files=files)


def test_outcomes_and_execution_receipts_are_not_self_authenticating():
    receipt = examples()[2]
    with pytest.raises(ValueError):
        replace(receipt, exit_code=True)
    assert receipt.digest != replace(receipt, exit_code=1).digest
    proposal = examples()[3]
    for receipts in [(), ("receipt", "receipt"), ([],)]:
        with pytest.raises(ValueError):
            replace(proposal, receipt_ids=receipts)
    with pytest.raises(ValueError):
        replace(proposal, outcome="verified_fix")


def test_unresolved_relation_cannot_claim_resolver_assurance():
    with pytest.raises(ValueError):
        replace(examples()[5], assurance="resolver")


def test_capability_status_is_not_a_boolean_parity_claim():
    with pytest.raises(ValueError):
        replace(examples()[7], capabilities=(("structure", True),))


def test_imported_algorithms_keep_python_310_grammar_and_notices():
    root = Path(__file__).resolve().parents[1]
    for name in ("code_retriever.py", "code_graph_diagram.py"):
        source = (root / "atmem/knowledge/_vendor" / name).read_text()
        ast.parse(source, feature_version=(3, 10))
        assert "SPDX-License-Identifier: Apache-2.0" in source
        assert "modified by AtMem" in source
