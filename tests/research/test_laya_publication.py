from __future__ import annotations

from pathlib import Path

import pytest

from research.laya_formation.publication.lint_dataset_card import lint


def test_dataset_card_passes_claim_lint() -> None:
    lint(Path("research/laya_formation/publication/DATASET_CARD.md").read_text())


def test_dataset_card_lint_rejects_placeholders_and_claims() -> None:
    text = Path("research/laya_formation/publication/DATASET_CARD.md").read_text()
    with pytest.raises(ValueError, match="forbidden"):
        lint(text + "\nTODO: proves production quality\n")
