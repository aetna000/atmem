"""Run with an installed wheel to verify the public Code product surfaces."""

import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request

import pytest


def cli(*args, cwd):
    import atmem
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(atmem.__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, "-m", "atmem.cli", "code", *map(str, args), "--json"],
                            cwd=cwd, env=environment, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def installed_project(tmp_path):
    pytest.importorskip("sqlcipher3")
    pytest.importorskip("pqcrypto")
    from atmem.code.application import CodeApplication
    from atmem.code.contracts import CodeObservation, CodeScope
    from atmem.code.formation import CodeFormation
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    root = tmp_path / "source-project"
    root.mkdir()
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    setup = cli("setup", "--project", root, "--db", database, "--apply", cwd=tmp_path)
    assert setup["enabled"] is False
    project = setup["scope"]["project_id"]
    memory = Memory(database, auto_vectors=False)
    try:
        scope = CodeScope("local", project, "shared", "codex")
        event = CodeObservation("event-1", "session-1", "turn-1", "codex", "user_turn",
                                "Remember that my preferred formatter is Ruff.", "2026-10-14T10:00:00+00:00", "user:turn-1", None, scope)
        assert CodeFormation(memory).form(event)["formed"]
    finally:
        memory.close()
    return root, database, project


def test_installed_cli_encrypted_portable_roundtrip(installed_project, tmp_path):
    root, database, project = installed_project
    found = cli("search", "formatter", "--project", root, "--db", database, cwd=tmp_path)
    assert "Ruff" in found["records"][0]["content"]
    keys = tmp_path / "bundle-keys"
    cli("keygen", keys, cwd=tmp_path)
    bundle = tmp_path / "project.bundle.json"
    cli("export", bundle, "--project", root, "--db", database,
        "--recipient-key", keys / "recipient.public", "--signing-key", keys / "signing.secret",
        "--signing-public-key", keys / "signing.public", cwd=tmp_path)
    assert b"Ruff" not in bundle.read_bytes()
    from atmem.service.household import HouseholdApplication
    target_db = tmp_path / "target.db"
    HouseholdApplication.initialize(target_db, encrypted=True)
    target_root = tmp_path / "destination-project"
    target_root.mkdir()
    arguments = ["import", bundle, "--project", target_root, "--db", target_db,
                 "--recipient-secret-key", keys / "recipient.secret", "--trusted-signing-key", keys / "signing.public"]
    preview = cli(*arguments, cwd=tmp_path)
    assert preview["can_import"]
    imported = cli(*arguments, "--preview-token", preview["preview_token"], cwd=tmp_path)
    assert imported["imported"] and imported["hosts_enabled"] is False
    restored = cli("search", "formatter", "--project", target_root, "--db", target_db, cwd=tmp_path)
    assert restored["records"][0]["id"] == found["records"][0]["id"]
    assert "Ruff" in restored["records"][0]["content"]
    assert b"Ruff" not in database.read_bytes() and b"Ruff" not in target_db.read_bytes()


@pytest.fixture
def code_server(installed_project, tmp_path):
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.control.ui import APP_HTML
    root, database, project = installed_project
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "control-state.json",
                                       control_root=tmp_path / "control", memory_db=database)
    bootstrap = manager.identity_service().bootstrap()
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html=APP_HTML)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def post(path, body, csrf=None):
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        return json.loads(opener.open(Request(base + path, data=json.dumps(body).encode(), headers=headers)).read())
    login = post("/api/auth/login", {"username": "administrator", "password": bootstrap["password"]})
    password = "Code product fixture password 2026"
    post("/api/auth/change-password", {"new_password": password}, login["csrf_token"])
    yield server, base, password, opener, root, database, project
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_installed_http_and_cli_use_identical_settings(code_server, tmp_path):
    from urllib.error import HTTPError
    server, base, password, opener, root, database, project = code_server
    with pytest.raises(HTTPError) as denied:
        build_opener().open(base + "/api/code?action=projects")
    assert denied.value.code == 403
    csrf = json.loads(opener.open(base + "/api/session").read())["csrf_token"]
    body = {"action": "config", "subject_id": "local", "project_id": project, "changes": {"auto_capture": False}}
    request = Request(base + "/api/code", data=json.dumps(body).encode(), headers={"Content-Type":"application/json", "X-CSRF-Token":csrf})
    assert json.loads(opener.open(request).read())["settings"]["auto_capture"] is False
    assert cli("config", "--project", root, "--db", database, cwd=tmp_path)["settings"]["auto_capture"] is False
    with pytest.raises(HTTPError) as get_mutation:
        opener.open(base + "/api/code?action=clear&subject_id=local&project_id=" + project)
    assert get_mutation.value.code == 403


def test_dashboard_coding_memory_browser_journey(code_server, tmp_path):
    if os.environ.get("ATMEM_CODE_BROWSER_TEST") != "1":
        pytest.skip("Run explicitly with the isolated browser test environment")
    from playwright.sync_api import sync_playwright, expect
    server, base, password, opener, root, database, project = code_server
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        page.locator("#loginUsername").fill("administrator")
        page.locator("#loginPassword").fill(password)
        page.locator("#loginForm button[type=submit]").click()
        page.locator("#navMemory").click()
        page.locator("#codeRefresh").click()
        expect(page.locator("#codeProject")).to_have_value(project)
        page.locator("#codeQuery").fill("formatter")
        page.locator("#codeSearch").click()
        expect(page.locator("#codeResults")).to_contain_text("Ruff")
        page.get_by_text("Automatic memory settings", exact=True).click()
        page.locator("#codeAutoCapture").uncheck()
        page.locator("#codeSettings button[type=submit]").click()
        expect(page.locator("#codeStatus")).to_have_text("Settings saved")
        assert cli("config", "--project", root, "--db", database, cwd=tmp_path)["settings"]["auto_capture"] is False
        page.locator("#codeClearPreview").click()
        expect(page.locator("#codeClearApply")).to_be_enabled()
        page.locator("#codeClearApply").click()
        expect(page.locator("#codeResults")).to_contain_text("No memories match")
        artifact = os.environ.get("ATMEM_CODE_BROWSER_ARTIFACT")
        if artifact:
            page.screenshot(path=artifact, full_page=True)
        assert errors == [], errors
        browser.close()
