from __future__ import annotations

from importlib.resources import files


def test_m0_findings_are_keyboard_buttons_with_evidence_pivots() -> None:
    source = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert "Evidence-linked findings" in source
    assert "Open exact event" in source
    assert 'open.type="button"' in source
    assert "focusFlightEvidence(reference.sequence)" in source
    assert "External outcome:" in source
    assert "recovered error is history" in source


def test_dashboard_groups_sessions_memory_and_audit_by_user_question() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert 'id="navStatus"' in html
    assert 'id="navMemory"' in html
    assert 'id="navAudit"' in html
    assert 'id="blackboxWorkspace"' in html
    assert "Agent sessions" in html
    assert "What does AtMem know that could help?" in html
    assert "Memory archive" in html
    assert 'aria-label="Memory archive sections"' in html
    assert "Audit trail" in html
    assert 'appendChild($("memorySearchCard"))' in script
    assert 'appendChild($("blackboxArchiveCard"))' in script
    assert 'appendChild($("auditExplorer"))' in script
    assert 'if(hash==="evidence")hash="audit"' in script
    assert 'id="navIncidents"' not in html


def test_evidence_protection_is_one_compact_setting_with_focused_actions() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert html.count('id="evidenceProtection"') == 1
    assert "Evidence protection" in html
    assert "Data off keeps encrypted metadata only" in html
    assert 'id="evidenceDataToggle"' in html
    assert 'id="evidenceRecorderToggle"' in html
    assert 'id="evidenceRotateKey"' in html
    assert 'id="evidenceLockToggle"' in html
    assert 'id="evidenceCollectorToken"' in html
    assert 'setEvidenceMode(evidenceProtection.data_enabled?"metadata":"full")' in script
    assert 'setEvidenceMode(evidenceProtection.recorder_enabled?"off":"full")' in script
