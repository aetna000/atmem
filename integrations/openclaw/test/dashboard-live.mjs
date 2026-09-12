// Optional browser gate: ATMEM_PLAYWRIGHT_MODULE points to an isolated Playwright installation.
// Fixtures intercept read-only run APIs in the browser; no host runs or stored evidence are changed.
import assert from "node:assert/strict";
const { chromium } = await import(process.env.ATMEM_PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "dark" });
const errors = [];
page.on("pageerror", error => errors.push(error.message));
let releaseStatus;
const statusGate = new Promise(resolve => { releaseStatus = resolve; });
await page.route("**/api/status", async route => { await statusGate; return route.continue(); });
let phase = "running", revisionReads = 0, runReads = 0, disconnected = false;
const time = new Date().toISOString();
function fixture() {
  const complete = phase !== "running";
  const timeline = [
    { sequence: 1, event_type: "turn.input", payload: {} },
    { sequence: 2, event_type: "tool.requested", tool_call_id: "fixture-call", payload: { tool_name: "progress_card" } },
    { sequence: 3, event_type: "tool.completed", tool_call_id: "fixture-call", payload: { tool_name: "progress_card", outcome: "completed", result_sha256: "a".repeat(64) } },
    { sequence: 4, event_type: "tool.completed", tool_call_id: "fixture-call", payload: { tool_name: "progress_card", outcome: "completed", result_sha256: "b".repeat(64) } },
    { sequence: 5, event_type: "model.output", payload: {} },
    ...(complete ? [{ sequence: 6, event_type: "turn.ended", payload: { success: true } }] : []),
  ].map(event => ({ ...event, recorded_at: time, run_id: "fixture-run", turn_id: "fixture-turn", agent_id: "main" }));
  return {
    run_id: "fixture-run", run_kind: "agent_run", agent_id: "main", session_id: "fixture-session",
    started_at: time, ended_at: time, events: timeline.length, timeline,
    verdict: complete ? "incomplete_evidence" : "in_progress", timeline_chain_valid: true,
    lifecycle: { success: complete, failed: false },
    coverage: { terminal_event_observed: complete, model_output_observed: true, response_digest_bound: true },
    coverage_matrix: { overall_status: "partial", components: { tools: "missing" } },
    evidence_summary: { conflicting_calls: 1 },
    tools: { requested: 1, completed: 1, conflicting_completions: ["fixture-call"] },
    correlation: { turn_ids: ["fixture-turn"] },
    attention_points: complete ? [{ code: "tool_lifecycle_mismatch", severity: "medium", title: "Run completed · tool evidence needs review", detail: "Conflicting progress observations." }] : [],
  };
}
function servedFixture() {
  const report = fixture();
  if (phase === "errors") {
    report.verdict = "completed_with_tool_errors";
    report.evidence_summary = { tool_errors: 1 };
    report.tools = { requested: 1, completed: 1, errors: [{tool_call_id:"fixture-call",tool_name:"web_fetch",error_reason:"Web fetch failed (403)"}] };
    report.attention_points = [{code:"tool_errors",severity:"medium",title:"A tool returned an error"}];
    report.timeline = report.timeline.filter(e => e.sequence !== 3).map(e => e.sequence === 4 ? {...e,payload:{tool_name:"web_fetch",outcome:"error"}} : e);
    report.events = report.timeline.length;
  }
  return report;
}
await page.route("**/api/blackbox/*", async route => {
  const path = new URL(route.request().url()).pathname;
  if (path.endsWith("/revision")) {
    revisionReads++;
    if (disconnected) return route.abort();
    return route.fulfill({ json: { sequence: phase === "errors" ? 7 : phase === "complete" ? 6 : 5 } });
  }
  if (path.endsWith("/runs")) {
    runReads++;
    const background = { ...servedFixture(), run_id: "background-fixture", run_kind: "background_skill_review", lifecycle: { success: false }, verdict: "incomplete_evidence" };
    return route.fulfill({ json: { runs: [background, servedFixture()], total_runs: 2, chain: { valid: true } } });
  }
  if (path.endsWith("/flight")) return route.fulfill({ json: servedFixture() });
  if (path.endsWith("/story")) return route.fulfill({ json: { request_text: "Prepare a shortlist", response_text: "Shortlist ready" } });
  return route.continue();
});
try {
  await page.goto(process.env.ATMEM_DASHBOARD_URL || "http://127.0.0.1:8799/");
  await page.locator(".activityrow").first().waitFor();
  assert.equal(await page.locator("#statusBanner").evaluate(e => e.classList.contains("bad")), false, "pending status is not an outage");
  releaseStatus();
  await page.locator("#statusHeadline").filter({ hasText: "Agent run in progress" }).waitFor();
  assert.equal(await page.locator(".activityrow").count(), 1, "background runs must be explicitly discoverable, not replace foreground status");
  await page.locator(".activityrow").first().click();
  await page.locator(".diagnosisrow").first().waitFor();
  await page.locator(".diagnosisrow button.secondary").first().click();
  await page.locator(".event.focused").waitFor();
  phase = "complete";
  await page.locator("#statusHeadline").filter({ hasText: "Completed · evidence notes" }).waitFor({ timeout: 15000 });
  await page.locator("#auditorBody > .historicalnote").filter({ hasText: "Completed · evidence notes" }).waitFor();
  assert.equal(await page.locator('.event[data-event-sequence="3"]').evaluate(e => e.open), true, "open event survives automatic update");
  assert.equal(await page.locator(".event.issue-gap").count(), 2, "both conflicting observations are highlighted");
  assert.equal(await page.locator(".runidentifiers").evaluate(e => e.open), false);
  const stableReads = runReads;
  const previousRevisionReads = revisionReads;
  await page.waitForFunction(() => document.querySelector("#liveStatus").textContent.includes("Auto-updating"));
  // Wait for another revision request without a fixed sleep.
  await new Promise((resolve, reject) => { const deadline = setTimeout(() => { clearInterval(timer); reject(new Error("revision polling stopped")); }, 10000); const timer = setInterval(() => { if (revisionReads > previousRevisionReads) { clearInterval(timer); clearTimeout(deadline); resolve(); } }, 50); });
  assert.equal(runReads, stableReads, "unchanged evidence must not reload the run index");
  disconnected = true;
  await page.locator("#liveStatus").filter({ hasText: "Updates paused" }).waitFor({ timeout: 12000 });
  disconnected = false;
  await page.locator("#liveStatus").filter({ hasText: "Auto-updating" }).waitFor({ timeout: 12000 });
  await page.locator("#auditorClose").click();
  await page.locator("#activityBackground").click();
  assert.equal(await page.locator(".activityrow").count(), 2);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const tab of ["navStatus", "navDecisions", "navEvidence", "navSettings"]) {
    await page.locator(`#${tab}`).click();
    await page.locator(`#${tab}[aria-selected="true"]`).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${tab}: no horizontal page overflow`);
  }
  await page.locator("#navStatus").click();
  await page.locator('#navStatus[aria-selected="true"]').waitFor();
  await page.locator("#viewStatus.active").waitFor({state:"visible"});
  await page.locator("#activityTimeline").scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo(0,0));
  assert.ok(await page.locator("#statusBanner").evaluate(e => e.getBoundingClientRect().height < 260), "mobile status remains compact");
  await page.screenshot({ path: "/tmp/atmem-ui-mobile.png", animations: "disabled" });
  phase = "errors";
  await page.locator("#statusHeadline").filter({hasText:"Completed · tool errors recorded"}).waitFor({timeout:15000});
  assert.equal(await page.locator("#statusBanner").evaluate(e=>e.classList.contains("good")),true);
  assert.match(await page.locator(".activityclock").first().textContent(), /:\d{2}\.\d{3}/);
  await page.locator(".activityrow").last().click();
  await page.locator(".diagnosisrow").filter({hasText:"Web fetch failed (403)"}).waitFor();
  await page.locator(".diagnosisrow button.secondary").first().click();
  await page.locator(".event.issue-error").waitFor();
  assert.match(await page.locator(".event.issue-error").textContent(), /Recorded at \(UTC\):/);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "precise timestamps and failed-step detail fit mobile");
  assert.deepEqual(errors, []);
  console.log("dashboard browser: live transition, preserved details, stable polling, reconnect, conflicts, background toggle and four mobile routes passed");
} finally { await browser.close(); }
