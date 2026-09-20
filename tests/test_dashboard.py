from __future__ import annotations

from importlib.resources import files

from atmem.control.web import ControlDashboardHandler


def test_dashboard_tab_identity_and_companion_link_contract() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    css = files("atmem.control").joinpath("assets/app.css").read_text(encoding="utf-8")
    assert "<title>AtMem.ai | Insight</title>" in html
    assert 'rel="icon" type="image/svg+xml"' in html
    assert 'id="atflowsDashboardLink" hidden' in html
    assert 'get("/api/companions")' in script
    assert 'url.hostname!=="127.0.0.1"' in script
    assert ".logo .brandmark{display:block;width:20px;height:20px" in css


def test_m0_findings_are_keyboard_buttons_with_evidence_pivots() -> None:
    source = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert "Evidence-linked findings" in source
    assert "Run evidence sections" in source
    assert 'activateEvidenceTab("timeline")' in source
    assert 'body.dataset.runId===runId' in source
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
    assert "Session health at a glance" in html
    assert 'id="sessionDetailBack"' in html
    assert 'id="sessionHealthChart"' in html
    assert "Run failure rate" in script
    assert "Tool-error rate" in script
    assert "Evidence-gap rate" in script
    assert "What does AtMem know that could help?" in html
    assert "Memory archive" in html
    assert 'aria-label="Memory archive sections"' in html
    assert "Audit trail" in html
    assert "Who did what with memory" in html
    assert 'id="auditRows"' in html
    assert 'class="auditadvanced"' in html
    assert 'class="auditexports"' in html
    assert 'appendChild($("memorySearchCard"))' in script
    assert 'appendChild($("blackboxArchiveCard"))' in script
    assert 'appendChild($("auditExplorer"))' in script
    assert 'if(hash==="evidence")hash="audit"' in script
    assert 'id="navIncidents"' not in html
    assert "auditHumanStatement" in script
    assert "Technical proof, IDs and canonical payload" in script
    assert 'if(!sessionView||matchMedia("(max-width: 1050px)").matches)' in script
    assert 'pane.scrollIntoView({block:"start"})' in script


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
    assert 'id="evidenceCollectorToken"' not in html
    assert 'id="evidenceRoleSummary"' in html
    assert 'setEvidenceMode(evidenceProtection.data_enabled?"metadata":"full")' in script
    assert 'setEvidenceMode(evidenceProtection.recorder_enabled?"off":"full")' in script


def test_portable_home_is_one_compact_authenticated_setting() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert html.count('id="homeCard"') == 1
    assert 'id="homeVerify"' in html
    assert 'id="homeAdopt"' in html
    assert 'id="homeMigration"' in html
    assert 'get("/api/home")' in script
    assert 'authPost("/api/home/verify"' in script
    assert 'authPost("/api/home/adopt"' in script
    assert 'value.mode==="restore_read_only"' in script


def test_blackbox_opens_exact_protected_evidence_without_persisting_credentials() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    assert "Viewer sees hashes and metadata" in html
    assert "Viewer metadata access active" in script
    assert "Exact text and media remain encrypted" in script
    assert "Administrator also manages users" in html
    assert 'evidenceGet("/v1/evidence/runs/"+encodeURIComponent(runId))' in script
    assert '"Authorization":"Bearer "+evidenceAccessToken' not in script
    assert 'get("/api/auth/status")' in script
    assert "exactRequestText(protectedRun)" in script
    assert "requestSummaryContent(requestText,protectedRun,report)" in script
    assert '"Complete input: "+(requestText?"text + ":"")' in script
    assert 'row.event_type==="turn.attachment"' in script
    assert "exactResponseText(protectedRun)" in script
    assert "renderExactEvidence(evidence)" in script
    assert 'mediaParts.length?"Captured evidence":"Captured data"' in script
    assert "Black-box capture does not by itself add this artifact to recallable memory." in script
    assert 'document.createElement(part.type)' in script
    assert 'media.controls=true' in script
    assert '"Download "+part.type' in script
    assert 'accountRole==="evidence_collector"||accountRole==="administrator"' in script
    assert 'accountRole==="viewer"' not in script
    assert "localStorage.setItem(\"evidence" not in script
    assert "sessionStorage.setItem(\"evidence" not in script
    assert "Encrypted request retained. Authenticate above" in script


def test_archive_layout_responds_to_pane_width_not_only_viewport() -> None:
    css = files("atmem.control").joinpath("assets/app.css").read_text(encoding="utf-8")
    assert "#blackboxArchiveCard{container-type:inline-size;min-width:0;align-self:start}" in css
    assert "@container (max-width:850px)" in css
    assert "@container (max-width:380px)" in css
    assert ".flight>.flightidentity{grid-column:1/-1}" in css
    assert ".flightfilters>.field:first-child{grid-column:1/-1}" in css


def test_dashboard_has_local_sign_in_user_management_and_stable_evidence_layout() -> None:
    html = files("atmem.control").joinpath("assets/app.html").read_text(encoding="utf-8")
    script = files("atmem.control").joinpath("assets/app.js").read_text(encoding="utf-8")
    css = files("atmem.control").joinpath("assets/app.css").read_text(encoding="utf-8")
    for element_id in (
        "authGate", "loginForm", "passwordForm", "identityChip", "usersCard",
        "userCreateForm", "usersList", "oneTimeCredential",
    ):
        assert f'id="{element_id}"' in html
    assert 'authPost("/api/auth/login"' in script
    assert 'authPost("/api/auth/change-password"' in script
    assert 'authPost("/api/users/create"' in script
    assert 'authPost("/api/users/update"' in script
    assert 'authPost("/api/users/reset-password"' in script
    assert 'sessionView=active&&active.id==="viewStatus"' in script
    assert 'if(sessionView)active.classList.add("auditor-open"' in script
    assert 'classList.add("auditor-open",source==="archive"?"detail-archive":"detail-recent")' in script
    assert 'if(active&&active.id==="viewStatus"){workspace.appendChild(pane)' not in script
    assert ".auth-required" in css
    assert ".roleladder" in css
    assert "[hidden]{display:none!important}" in css
    assert "localStorage.setItem(\"atmem_session" not in script
    assert "sessionStorage.setItem(\"atmem_session" not in script
    assert "atmem users recover-administrator" in html
    assert "consumeBootstrapFragment()" in script
    assert 'history.replaceState(null,"",location.pathname+location.search+"#status")' in script
    assert 'params.get("password")' in script
    assert 'technicalJump.onclick=function(){activateEvidenceTab("timeline")' in script
    assert 'nav.onkeydown=function(event)' in script
    assert 'panels[pair[0]].setAttribute("aria-labelledby",buttonId)' in script
    record_technical = script.split("async function inspectRecordTechnical", 1)[1].split("function humanField", 1)[0]
    assert "if(live)" not in record_technical
    assert "blackboxStories[runId]" not in record_technical


def test_dashboard_security_policy_allows_encrypted_multimodal_playback() -> None:
    import inspect

    source = inspect.getsource(ControlDashboardHandler._security_headers)
    assert "img-src 'self' data:" in source
    assert "media-src 'self' data:" in source
    assert "object-src 'none'" in source
