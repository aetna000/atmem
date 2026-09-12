import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../../../atmem/control/assets/app.js", import.meta.url), "utf8");
const helpers = source.split("\n").filter(line => /^function flight(?:ToolIssues|IssueAction)\(/.test(line)).join("\n");
const context = vm.createContext({});
vm.runInContext(helpers, context);
const event = { sequence: 578, tool_call_id: "call-1", event_type: "tool.requested", payload: { tool_name: "exec" } };
const [gap] = context.flightToolIssues({ tools: { missing_completions: ["call-1"] }, timeline: [event] });
assert.equal(gap.event.sequence, 578);
assert.match(gap.detail, /does not by itself prove the tool failed/);
assert.match(context.flightIssueAction(gap), /before retrying/);
assert.match(context.flightIssueAction(gap), /cannot restore missing historical evidence/);
for (const reason of [undefined, "Fetch failed (403): [redacted-url]"]) {
  const [error] = context.flightToolIssues({ tools: { errors: [{ tool_call_id: "fetch", tool_name: "web_fetch", error_reason: reason }] } });
  assert.ok(error.detail.includes(reason ?? "No error reason was captured."));
  assert.match(context.flightIssueAction(error), /Confirm any side effects/);
}
console.log("blackbox diagnostics: captured reasons, legacy fallback and recovery guidance passed");

const presentation = source.split("\n").filter(line => /^function (activityState|runSummary|currentRun)\(/.test(line)).join("\n");
vm.runInContext(presentation, context);
const completed = { run_id: "foreground", verdict: "incomplete_evidence", lifecycle: { success: true }, attention_points: [{ code: "tool_lifecycle_mismatch" }], evidence_summary: { conflicting_calls: 3 } };
assert.equal(context.activityState(completed).tone, "warn");
assert.equal(context.activityState(completed).label, "Completed · evidence note");
assert.match(context.runSummary(completed), /3 tool calls with conflicting/);
context.blackboxIndex = { runs: [{ run_id: "background", run_kind: "background_skill_review" }, completed] };
assert.equal(context.currentRun().run_id, "foreground");
assert.equal(context.activityState({ verdict: "failed", lifecycle: { failed: true } }).tone, "bad");
const conflict = context.flightToolIssues({tools:{conflicting_completions:["call-1"]},timeline:[
  {...event,event_type:"tool.completed",sequence:2}, {...event,event_type:"tool.completed",sequence:3}
]});
assert.equal(conflict.length,1);
assert.equal(conflict[0].events.length,2);
assert.equal(conflict[0].tone,"gap");
const background = context.flightToolIssues({run_kind:"background_skill_review",verdict:"incomplete_evidence",coverage:{terminal_event_observed:false},timeline:[event]});
assert.match(background[0].detail,/separate from the foreground/);
console.log("blackbox presentation: completed outcomes, background separation and grouped conflicts passed");

assert.equal(context.runSummary({lifecycle:{success:true},coverage:{}}), "Host reported completion");
const successfulDuplicates = context.flightToolIssues({tools:{conflicting_completions:['call-1']},timeline:[2,3].map(sequence=>({...event,event_type:'tool.completed',sequence,payload:{tool_name:'progress_card',outcome:'completed'}}))});
assert.match(successfulDuplicates[0].title,/both report success/);
assert.match(successfulDuplicates[0].detail,/do not establish equivalence/);
const completedErrors = {verdict:'completed_with_tool_errors',lifecycle:{success:true},attention_points:[{code:'tool_errors'}],evidence_summary:{tool_errors:2}};
assert.equal(context.activityState(completedErrors).icon,'✓');
assert.equal(context.activityState(completedErrors).label,'Completed · tool errors recorded');
assert.match(context.runSummary(completedErrors),/Run completed · 2 tool calls returned errors/);
assert.equal(context.activityState({...completedErrors,lifecycle:{failed:true}}).tone,'bad');
const securityOnly = context.flightToolIssues({tools:{errors:[{tool_call_id:'fetch',error_reason:'SECURITY NOTICE: untrusted content'}]}})[0];
assert.match(securityOnly.detail,/underlying reason was not captured/);
assert.doesNotMatch(securityOnly.detail,/Host error \(redacted\): SECURITY NOTICE/);
const times = source.split('\n').filter(line => /^function displayTime\(/.test(line)).join('\n');
vm.runInContext(times, context);
const originalTZ = process.env.TZ;
try {
  process.env.TZ = 'Australia/Sydney';
  assert.match(context.displayTime('2026-09-09T08:42:49.496063+00:00'), /06:42:49\.496/);
  assert.match(context.displayTime('2026-01-09T08:42:49.123456+00:00'), /07:42:49\.123/);
  process.env.TZ = 'UTC';
  assert.match(context.displayTime('2026-09-09T08:42:49.496063+00:00'), /08:42:49\.496/);
  assert.equal(context.displayTime(null), 'not recorded');
} finally { if (originalTZ === undefined) delete process.env.TZ; else process.env.TZ = originalTZ; }
console.log('completion/step separation and UTC/local millisecond/DST presentation passed');
