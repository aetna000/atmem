"""Verify the signed-in project history, source inspector and comparison in Chromium."""

import os
from pathlib import Path
import secrets
import shutil

from playwright.sync_api import sync_playwright


def verify_dashboard(project, run_id, screenshot):
    identity = project.manager.identity_service()
    first = identity.bootstrap()
    initial = identity.login("administrator", first["password"])
    login = identity.change_password(
        initial["session_token"], first["password"], "Qp!" + secrets.token_urlsafe(24)
    )
    chrome = os.environ.get("CHROME_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
    if not chrome and Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").is_file():
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if shutil.which("node"):
        os.environ.setdefault("PLAYWRIGHT_NODEJS_PATH", shutil.which("node"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=chrome)
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 1000}, device_scale_factor=1)
            page.context.add_cookies(
                [
                    {
                        "name": "atmem_session",
                        "value": login["session_token"],
                        "url": project.endpoint,
                        "httpOnly": True,
                        "sameSite": "Strict",
                    }
                ]
            )
            page.goto(project.endpoint + "/#agentTeam")
            page.locator("#teamExamples").click()
            page.locator("#teamCase").select_option("host-corrected")
            page.locator("#teamResults").get_by_text("Original and rerun", exact=True).wait_for()
            assert page.locator("#teamRerun").is_hidden()
            page.locator("#teamProject").click()
            page.locator("#teamFilter").fill("test_route")
            page.locator("#teamHistorySearch").get_by_role("button").click()
            buttons = page.locator("#teamRunList button")
            page.wait_for_function("document.querySelectorAll('#teamRunList button').length === 2")
            buttons.first.click()
            page.locator("#teamResults").get_by_text("Original and rerun", exact=True).wait_for()
            assert "failed" in page.locator("#teamResults").inner_text()
            assert "passed" in page.locator("#teamResults").inner_text()
            page.locator("#teamOutcomeList").get_by_role("button", name="Return quote").click()
            assert "routing-v2" in page.locator("#teamStepFacts").inner_text()
            assert "hermes" in page.locator("#teamStepFacts").inner_text()
            page.locator("#teamStepFacts").get_by_role(
                "button", name="Inspect original excerpt"
            ).first.click()
            page.locator("#teamStepFacts").get_by_text(
                "My Atlas routing code is AX-745.", exact=True
            ).wait_for()
            page.set_viewport_size({"width": 1360, "height": 2100})
            page.locator("#agentTeam").screenshot(
                path=str(screenshot), style="body > header, .memorychat {visibility:hidden !important}"
            )
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#teamOutcomeList").get_by_role("button", name="Open original execution").click()
            page.locator("#teamOutcomeList").get_by_text("failed", exact=True).wait_for()
            assert page.locator("#teamStepFacts").inner_text()
            widths = page.locator("#agentTeam").evaluate("(el) => [el.scrollWidth,el.clientWidth]")
            assert widths[0] <= widths[1] + 2, widths
        finally:
            browser.close()
