from pathlib import Path
import runpy

import pytest


helpers = runpy.run_path(str(Path(__file__).parents[1] / "tools/check_spec_tasks.py"))
parse_tasks = helpers["parse_tasks"]
inventory = helpers["inventory"]


def test_suffix_is_identity_and_rollup_is_not_extra_implementation():
    rows = parse_tasks("- [x] [T006] Done\n- [ ] [T006a] Inserted\n- [ ] [T007] [ROLLUP: T008] Group", "fixture")
    assert [row["id"] for row in rows] == ["T006", "T006a", "T007"]
    assert rows[0]["completed"]
    assert rows[2]["rollup"]


def test_complete_id_duplicate_is_rejected():
    with pytest.raises(ValueError, match="duplicate task ID T006a"):
        parse_tasks("- [ ] [T006a] First\n- [x] [T006a] Duplicate", "fixture")


def test_unbracketed_task_is_rejected():
    with pytest.raises(ValueError, match="invalid task row"):
        parse_tasks("- [ ] T006 Invalid", "fixture")


def test_feature_scoping_and_actionable_counts(tmp_path):
    for name in ("001-example", "002-example"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "tasks.md").write_text("- [ ] [T006a] Work\n- [ ] [T007] [ROLLUP: T006a] Group\n- [x] [T008] Done", encoding="utf-8")
    result = inventory(tmp_path)
    assert result["task_count"] == 6
    assert result["unchecked"] == 4
    assert result["unchecked_rollups"] == 2
    assert result["actionable_unchecked"] == 2
