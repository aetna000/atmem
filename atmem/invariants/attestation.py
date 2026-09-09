"""Spec attestation loading and invariant-bearing surface checks."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True,slots=True)
class Attestation:
    spec: str; invariant_ids: tuple[str,...]; assertions: tuple[str,...]

SURFACES={"atmem/store/":("INV-001","INV-007","INV-011"),"atmem/retrieve/":("INV-002","INV-003","INV-010"),"atmem/control/":("INV-004","INV-005","INV-008","INV-009"),"atmem/graph/":("INV-001","INV-007"),"atmem/lifecycle/":("INV-003","INV-007"),"atmem/adapters/":("INV-004","INV-005","INV-008")}

def load_attestation(spec_path: str|Path) -> Attestation:
    path=Path(spec_path); text=path.read_text(encoding="utf-8")
    match=re.search(r"^## Invariant Attestation\s*$([\s\S]*?)(?=^## |\Z)",text,re.M)
    if not match: raise ValueError(f"{path} has no Invariant Attestation")
    ids=tuple(sorted(set(re.findall(r"INV-\d{3}",match.group(1)))))
    assertions=tuple(sorted(set(re.findall(r"`([a-z][a-z0-9_.-]+)`",match.group(1)))))
    if not ids or not assertions: raise ValueError(f"{path} attestation requires invariant IDs and assertions")
    return Attestation(path.parent.name,ids,assertions)

def validate_attestations(values: list[Attestation]) -> None:
    seen={}
    for value in values:
        for invariant in value.invariant_ids:
            current=seen.setdefault(invariant,set()); overlap=current.intersection(value.assertions)
            if overlap: raise ValueError(f"conflicting attestation for {invariant}: {sorted(overlap)}")
            current.update(value.assertions)

def required_for_changes(paths: list[str]) -> set[str]:
    return {invariant for path in paths for prefix,ids in SURFACES.items() if path.startswith(prefix) for invariant in ids}

def assert_changes_attested(paths: list[str], attestations: list[Attestation]) -> None:
    required=required_for_changes(paths); declared={item for a in attestations for item in a.invariant_ids}
    missing=required-declared
    if missing: raise ValueError(f"unattested invariant-bearing change: {sorted(missing)}")
