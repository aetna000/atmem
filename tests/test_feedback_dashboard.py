from copy import deepcopy
import json
from http.cookiejar import CookieJar
import threading
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

import pytest

from atmem.control.feedback import FeedbackDashboard
from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer
from atmem.evidence.models import EvidenceRole
from atmem.feedback.store import FeedbackError
from test_feedback_actions import actions_fixture


def test_facade_rechecks_identity_scope_and_role_before_credential_binding(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    identity = {"account": {"username": f.user["principal_id"], "role": "investigator", "scope": f.scope.evidence_scope().to_dict()}}
    dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:f.session)
    assert dashboard.status(identity)["scope"] == f.scope.to_dict()
    for field, value in (("username", "other"), ("role", "viewer"), ("password_change_required", True)):
        bad = deepcopy(identity)
        bad["account"][field] = value
        with pytest.raises(FeedbackError, match="denied"):
            dashboard.status(bad)
    foreign = deepcopy(identity)
    foreign["account"]["scope"]["subject_id"] = "bob"
    with pytest.raises(FeedbackError, match="denied"):
        dashboard.status(foreign)
    with pytest.raises(FeedbackError, match="denied"):
        dashboard.action(identity, {"operation": "transition", "state": "active"})


def test_owner_facade_review_activation_and_rollback_use_real_authority_and_fresh_gates(tmp_path):
    from test_feedback_review import review_fixture
    from feedback_lifecycle_fixtures import seed_trusted_test_receipt, VERSIONS
    f, memory, review, rule = review_fixture(tmp_path, include_owner=True)
    try:
        f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.owner["principal_id"],
            operations=("read", "propose"), expires_at=1_700_010_000)
        session = f.feedback.bind(f.owner["token"], agent_id="writer", workspace_id="project")
        identity = {"account":{"username":f.owner["principal_id"], "role":"administrator", "scope":f.scope.evidence_scope().to_dict()}}
        dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:session, runtime_versions=VERSIONS)
        review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal")
        assert dashboard.action(identity, {"operation":"review", "kind":"rule", "artifact_id":"rule",
            "candidate_sha256":rule.content_digest, "decision":"approve", "reason":"human review of exact synthetic evidence"})["state"] == "reviewed"
        options = {"operation":"transition", "kind":"rule", "artifact_id":"rule", "candidate_sha256":rule.content_digest}
        dashboard.action(identity, {**options, "state":"shadow", "expected_generation":0})
        with pytest.raises(FeedbackError, match="qualification_inconclusive"):
            dashboard.action(identity, {**options, "state":"active", "expected_generation":1})
        # Test-only trusted-store authority, never produced by the diagnostic
        # qualifier. Tests consumers of an accepted receipt, not efficacy.
        key = seed_trusted_test_receipt(f, rule)
        assert dashboard.action(identity, {**options, "state":"active", "expected_generation":1,
            "qualification_id":key})["generation"] == 2
        dashboard.action(identity, {**options, "state":"suspended", "expected_generation":2})
        result = dashboard.action(identity, {"operation":"rollback", "kind":"rule", "artifact_id":"rule",
            "target_generation":2, "expected_generation":3})
        assert result["generation"] == 4 and result["rollback_of_generation"] == 2
        memory.forget_record("alice", rule.sources[0].source_id)
        dashboard.action(identity, {**options, "state":"suspended", "expected_generation":4})
        with pytest.raises(FeedbackError, match="stale_source"):
            dashboard.action(identity, {"operation":"rollback", "kind":"rule", "artifact_id":"rule",
                "target_generation":2, "expected_generation":5})
    finally:
        memory.close()


@pytest.fixture
def dashboard_server(tmp_path):
    f, outcome = actions_fixture(tmp_path/"feedback")
    f.feedback.schedule(f.owner["token"], f.scope, schedule_id="quality", tasks=(
        {"outcome_id":"outcome", "episode_id":"episode", "answerable":True},))
    f.feedback.report_outcome(f.session, outcome, idempotency_key="reported")
    credential = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="administrator",
                                  role=EvidenceRole.ADMINISTRATOR, scope=f.scope.evidence_scope())
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id="administrator", operations=("read",), expires_at=1_700_010_000)
    session = f.feedback.bind(credential["token"], agent_id="writer", workspace_id="project")
    dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:session)
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path/"manager/state.json",
        control_root=tmp_path/"manager/control", memory_db=tmp_path/"manager/memory.db", subject_id="alice")
    from atmem.control.ui import build_app_html
    server = ControlDashboardServer(("127.0.0.1",0),manager,html=build_app_html(),feedback_dashboard=dashboard)
    bootstrap = manager.identity_service().bootstrap()
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield server, bootstrap, f, session
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_real_http_requires_login_csrf_and_matches_service_counts(dashboard_server):
    server, bootstrap, f, session = dashboard_server
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def post(path, body, csrf=None):
        headers={"Content-Type":"application/json"}
        if csrf:headers["X-CSRF-Token"]=csrf
        return json.loads(opener.open(Request(base+path, method="POST", data=json.dumps(body).encode(), headers=headers),timeout=10).read())
    with pytest.raises(HTTPError) as unsigned:
        opener.open(base+"/api/feedback/status",timeout=10)
    assert unsigned.value.code == 403
    login = post("/api/auth/login",{"username":"administrator","password":bootstrap["password"]})
    post("/api/auth/change-password",{"new_password":"synthetic local test password"},login["csrf_token"])
    status = json.loads(opener.open(base+"/api/feedback/status",timeout=10).read())
    assert status["scope"] == f.scope.to_dict()
    report = json.loads(opener.open(base+"/api/feedback/quality?schedule_id=quality",timeout=10).read())
    assert report == f.feedback.quality(session,schedule_id="quality")
    assert report["verified_full_task_success"]["value"] == 0
    assert report["wrong_answer_rate"]["value"] is None
    with pytest.raises(HTTPError) as csrf:
        post("/api/feedback/action",{"operation":"transition"})
    assert csrf.value.code == 403
    with pytest.raises(HTTPError):
        opener.open(base+"/api/feedback/quality?schedule_id=quality&subject_id=bob",timeout=10)


def test_real_http_activation_and_rollback_open_canonical_memory_in_request_thread(dashboard_server, tmp_path):
    import sqlite3
    from atmem import Memory
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f, memory, rule, _ = reviewed_shadow(tmp_path/"threaded-service")
    server, bootstrap, _, _ = dashboard_server
    credential = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="administrator",
        role=EvidenceRole.ADMINISTRATOR, scope=f.scope.evidence_scope())
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id="administrator", operations=("read",), expires_at=1_700_010_000)
    session = f.feedback.bind(credential["token"], agent_id="writer", workspace_id="project")
    key = seed_trusted_test_receipt(f, rule)  # Explicit synthetic consumer authority, not efficacy.
    # A genuine SQLite canonical snapshot remains only in test-process RAM.
    # Every HTTP request opens and closes its own real Memory connection. The
    # test never passes a main-thread SQLite connection to an HTTP worker.
    snapshot = sqlite3.connect(":memory:", check_same_thread=False)
    snapshot_lock = threading.Lock()
    memory.store._conn.backup(snapshot)
    opened = []
    def factory(identity):
        value = Memory(":memory:", auto_vectors=False)
        with snapshot_lock:
            snapshot.backup(value.store._conn)
        opened.append(threading.get_ident())
        return value
    server.feedback_dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:session,
        runtime_versions=VERSIONS, memory_factory=factory)
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def post(path, body, csrf):
        return json.loads(opener.open(Request(base+path, method="POST", data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json", "X-CSRF-Token":csrf}), timeout=20).read())
    try:
        login = post("/api/auth/login", {"username":"administrator", "password":bootstrap["password"]}, "")
        post("/api/auth/change-password", {"new_password":"threaded synthetic password"}, login["csrf_token"])
        args = {"operation":"transition", "kind":"rule", "artifact_id":"rule", "candidate_sha256":rule.content_digest}
        active = post("/api/feedback/action", {**args, "state":"active", "expected_generation":1,
            "qualification_id":key}, server.csrf_token)
        assert active["generation"] == 2
        post("/api/feedback/action", {**args, "state":"suspended", "expected_generation":2}, server.csrf_token)
        rollback = {"operation":"rollback", "kind":"rule", "artifact_id":"rule", "target_generation":2, "expected_generation":3}
        assert post("/api/feedback/action", rollback, server.csrf_token)["generation"] == 4
        assert opened and all(value != threading.get_ident() for value in opened)
        memory.forget_record("alice", rule.sources[0].source_id)
        with snapshot_lock:
            memory.store._conn.backup(snapshot)
        post("/api/feedback/action", {**args, "state":"suspended", "expected_generation":4}, server.csrf_token)
        with pytest.raises(HTTPError) as denied:
            post("/api/feedback/action", {**rollback, "expected_generation":5}, server.csrf_token)
        assert denied.value.code == 409 and json.loads(denied.value.read())["reason"] == "stale_source"
    finally:
        snapshot.close()
        memory.close()


def test_real_browser_keyboard_quality_and_exact_call_evidence(dashboard_server, tmp_path):
    import os
    from pathlib import Path
    if os.environ.get("ATMEM_FEEDBACK_BROWSER") != "1":
        pytest.skip("explicit local browser journey; no browser download in base tests")
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.is_file():
        pytest.skip("requires installed Chrome; do not download a browser implicitly")
    server, bootstrap, _, _ = dashboard_server
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=str(chrome), headless=True)
        try:
            page = browser.new_page(viewport={"width":1400,"height":1100})
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator("#loginUsername").fill("administrator")
            page.locator("#loginPassword").fill(bootstrap["password"])
            page.locator("#loginForm button[type=submit]").click()
            page.locator("#newPassword").fill("synthetic browser test password")
            page.locator("#repeatPassword").fill("synthetic browser test password")
            page.locator("#passwordForm button[type=submit]").click()
            playwright.expect(page.locator("#authGate")).to_be_hidden()
            page.locator("#navFeedback").focus()
            playwright.expect(page.locator("#navFeedback")).to_be_focused()
            page.keyboard.press("Enter")
            playwright.expect(page.locator("#feedbackStatus")).to_contain_text("alice / writer / project")
            page.locator("#feedbackSchedule").select_option("quality")
            page.locator("#feedbackQualityForm button").focus()
            page.keyboard.press("Enter")
            playwright.expect(page.locator("#feedbackQuality")).to_contain_text("insufficient evidence")
            task = page.locator("#feedbackQuality > details").filter(has=page.locator("summary", has_text="outcome ·"))
            task.locator("summary").click()
            playwright.expect(task.locator("pre")).to_contain_text('"body": "five days"')
            playwright.expect(task.locator("pre")).to_contain_text('"verified_success": false')
            page.screenshot(path=str(tmp_path/"feedback-browser.png"), full_page=True)
        finally:
            browser.close()


def test_browser_qualification_evidence_cancel_and_revoked_access(dashboard_server, tmp_path):
    import os
    from pathlib import Path
    if os.environ.get("ATMEM_FEEDBACK_BROWSER") != "1":
        pytest.skip("explicit real browser journey")
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.is_file():
        pytest.skip("requires existing Chrome, never an implicit download")
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f, memory, rule, _ = reviewed_shadow(tmp_path/"qualified-service")
    server, bootstrap, _, _ = dashboard_server
    credential = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="administrator",
                                  role=EvidenceRole.ADMINISTRATOR, scope=f.scope.evidence_scope())
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id="administrator",
                           operations=("read",), expires_at=1_700_010_000)
    session = f.feedback.bind(credential["token"], agent_id="writer", workspace_id="project")
    key = seed_trusted_test_receipt(f, rule)  # Consumer test, NOT efficacy qualification.
    server.feedback_dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:session, runtime_versions=VERSIONS)
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=str(chrome), headless=True)
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.locator("#loginUsername").fill("administrator")
                page.locator("#loginPassword").fill(bootstrap["password"])
                page.locator("#loginForm button[type=submit]").click()
                page.locator("#newPassword").fill("synthetic browser qualification password")
                page.locator("#repeatPassword").fill("synthetic browser qualification password")
                page.locator("#passwordForm button[type=submit]").click()
                playwright.expect(page.locator("#authGate")).to_be_hidden()
                page.locator("#navFeedback").click()
                selection = page.get_by_label("Qualification receipt for rule")
                playwright.expect(selection).to_be_enabled()
                activate = page.get_by_role("button", name="Activate qualified revision")
                playwright.expect(activate).to_be_disabled()
                selection.select_option(key)
                playwright.expect(activate).to_be_enabled()
                page.get_by_text("Qualification evidence", exact=True).click()
                playwright.expect(page.locator("#feedbackProposals")).to_contain_text("TEST_FIXTURE_NOT_EFFICACY")
                page.once("dialog", lambda dialog:dialog.dismiss())
                activate.click()
                with f.feedback.store.transaction(f.scope) as tx:
                    assert tx.get("rule_lifecycle", "rule")["state"] == "shadow"
                f.evidence.revoke(f.evidence.authenticate(f.owner["token"]), principal_id="administrator")
                page.once("dialog", lambda dialog:dialog.accept())
                with page.expect_response(lambda response:response.url.endswith("/api/feedback/action")) as request:
                    activate.click()
                assert request.value.status == 403 and request.value.json()["reason"] == "denied"
                with f.feedback.store.transaction(f.scope) as tx:
                    assert tx.get("rule_lifecycle", "rule")["state"] == "shadow"
            finally:
                browser.close()
    finally:
        memory.close()


def install_export_fixture(server, tmp_path):
    from dataclasses import replace
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    from test_feedback_verification import verifier_fixture, verify
    f, original, verifier, reader, _ = verifier_fixture(tmp_path)
    observation = replace(original.observations[1], arguments={"body":"ten days"})
    outcome = replace(original, outcome_id="export-ui", required=(original.required[1],), observations=(observation,))
    f.simulated_write(outcome, observation)
    f.feedback.report_outcome(f.session, outcome, idempotency_key="export-ui")
    verify(verifier, reader, outcome, key="verified-export-ui")
    credential = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="administrator",
                                  role=EvidenceRole.ADMINISTRATOR, scope=f.scope.evidence_scope())
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id="administrator", operations=("read",), expires_at=1_700_010_000)
    session = f.feedback.bind(credential["token"], agent_id="writer", workspace_id="project")
    signing = generate_signing_keypair()
    calls = []
    def signer(identity):
        calls.append(identity["account"]["username"])
        return signing
    server.feedback_dashboard = FeedbackDashboard(f.feedback, session_factory=lambda identity:session, export_signer=signer)
    public, secret = generate_recipient_keypair()
    return f, public, secret, signing, calls


def test_real_http_export_consent_preview_encryption_withdraw_and_revocation(dashboard_server, tmp_path):
    import base64
    from atmem.evidence.crypto import decrypt_export
    pytest.importorskip("pqcrypto")
    server, bootstrap, _, _ = dashboard_server
    f, public, secret, signing, calls = install_export_fixture(server, tmp_path/"export")
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def post(body, path="/api/feedback/action", csrf=None):
        headers = {"Content-Type":"application/json"}
        if csrf: headers["X-CSRF-Token"] = csrf
        return json.loads(opener.open(Request(base+path, method="POST", data=json.dumps(body).encode(), headers=headers), timeout=20).read())
    login = post({"username":"administrator", "password":bootstrap["password"]}, "/api/auth/login")
    csrf = login["csrf_token"]
    post({"new_password":"synthetic export password"}, "/api/auth/change-password", csrf)
    csrf = server.csrf_token  # Feedback uses the existing dashboard request token.
    args = {"operation":"export_consent", "consent_id":"consent", "purpose":"synthetic example only",
            "recipient_public_key":base64.b64encode(public).decode(), "outcome_ids":["export-ui"],
            "expires_at":1_700_000_060, "split":"development"}
    with pytest.raises(HTTPError) as denied:
        post(args)
    assert denied.value.code == 403
    post(args, csrf=csrf)
    preview = post({"operation":"export_preview", "consent_id":"consent"}, csrf=csrf)
    assert len(preview["examples"]) == 1 and not calls
    confirm = {"operation":"export_confirm", "consent_id":"consent", "recipient_public_key":args["recipient_public_key"],
               "preview_sha256":preview["preview_sha256"], "confirm_sha256":preview["preview_sha256"]}
    with pytest.raises(HTTPError):
        post({**confirm, "signing_secret_key":"browser-controlled-key"}, csrf=csrf)
    assert not calls
    result = post(confirm, csrf=csrf)
    assert json.loads(decrypt_export(result["encrypted_bundle"], secret)) == preview
    assert calls == ["administrator"]
    assert not any(key in result for key in ("signing_secret_key", "recipient_secret_key"))
    post({"operation":"export_withdraw", "consent_id":"consent"}, csrf=csrf)
    with pytest.raises(HTTPError):
        post(confirm, csrf=csrf)
    before = len(calls)
    f.evidence.revoke(f.evidence.authenticate(f.owner["token"]), principal_id="administrator")
    with pytest.raises(HTTPError) as denied:
        post(confirm, csrf=csrf)
    assert denied.value.code == 403 and len(calls) == before


def test_browser_export_explicit_review_download_and_logout_cleanup(dashboard_server, tmp_path):
    import base64
    import os
    from pathlib import Path
    from atmem.evidence.crypto import decrypt_export
    if os.environ.get("ATMEM_FEEDBACK_BROWSER") != "1":
        pytest.skip("explicit actual browser journey")
    pytest.importorskip("pqcrypto")
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.is_file():
        pytest.skip("requires installed Chrome; never download implicitly")
    server, bootstrap, _, _ = dashboard_server
    _, public, secret, _, calls = install_export_fixture(server, tmp_path/"export-browser")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=str(chrome), headless=True)
        try:
            page = browser.new_page(timezone_id="UTC")
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator("#loginUsername").fill("administrator")
            page.locator("#loginPassword").fill(bootstrap["password"])
            page.locator("#loginForm button[type=submit]").click()
            page.locator("#newPassword").fill("synthetic browser export password")
            page.locator("#repeatPassword").fill("synthetic browser export password")
            page.locator("#passwordForm button[type=submit]").click()
            playwright.expect(page.locator("#authGate")).to_be_hidden()
            page.locator("#navFeedback").click()
            playwright.expect(page.locator("#feedbackExport")).to_be_visible()
            page.locator("#feedbackConsentId").fill("consent")
            page.locator("#feedbackExportPurpose").fill("synthetic example only")
            page.locator("#feedbackRecipientKey").fill(base64.b64encode(public).decode())
            page.locator("#feedbackOutcomeIds").fill("export-ui")
            page.locator("#feedbackExportExpiry").fill("2023-11-14T22:14")
            page.once("dialog", lambda dialog:dialog.accept())
            page.get_by_role("button", name="Grant consent and preview").click()
            playwright.expect(page.locator("#feedbackExportStatus")).to_contain_text("1 eligible examples")
            confirm = page.locator("#feedbackExportConfirm")
            playwright.expect(confirm).to_be_disabled()
            assert not calls
            page.locator("#feedbackExportReviewed").check()
            playwright.expect(confirm).to_be_enabled()
            page.once("dialog", lambda dialog:dialog.dismiss())
            confirm.click()
            assert not calls
            page.once("dialog", lambda dialog:dialog.accept())
            with page.expect_download() as download:
                confirm.click()
            bundle = json.loads(Path(download.value.path()).read_text())
            plaintext = json.loads(decrypt_export(bundle["encrypted_bundle"], secret))
            assert plaintext["examples"][0]["outcome"]["outcome_id"] == "export-ui"
            assert calls == ["administrator"]
            page.screenshot(path=str(tmp_path/"feedback-export-browser.png"), full_page=True)
            page.once("dialog", lambda dialog:dialog.accept())
            page.locator("#logoutButton").click()
            playwright.expect(page.locator("#feedbackExport")).to_be_hidden()
            playwright.expect(page.locator("#feedbackExportPreview")).to_be_empty()
            assert page.locator("#feedbackRecipientKey").input_value() == ""
        finally:
            browser.close()
