from pathlib import Path
import pytest
from atmem.invariants.attestation import Attestation,assert_changes_attested,load_attestation,validate_attestations
def test_attestation_loader_and_missing_surface(tmp_path):
    spec=tmp_path/"spec.md"; spec.write_text("## Invariant Attestation\nINV-001 via `authority.test`.\n"); assert load_attestation(spec).invariant_ids==("INV-001",)
    with pytest.raises(ValueError): assert_changes_attested(["atmem/store/sqlite.py"],[load_attestation(spec)])
def test_conflicting_assertions_fail():
    with pytest.raises(ValueError): validate_attestations([Attestation("a",("INV-001",),("x",)),Attestation("b",("INV-001",),("x",))])
