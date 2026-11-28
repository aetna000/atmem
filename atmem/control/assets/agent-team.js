// Kept inside the dashboard closure to share its session and CSRF handling.
let teamRows = [], teamLoading = null, teamMode = "examples", teamEpoch = 0, teamAccount = null;
const teamCaseNames = {direct:"Direct fact", corrected:"Confirmed correction", busy:"Similar routing codes",
  expired:"Expired fact", conflict:"Conflicting sources", missing:"Missing evidence"};
const teamRoles = {lookup:"Memory lookup", expanded_lookup:"Expanded lookup", reviewer:"Source reviewer",
  reader:"Answer reader", decision:"Decision"};
const teamOutcomes = {answered:"Answered", abstained:"Abstained", failed:"Call failed", unavailable:"Model unavailable"};
const teamPolicyNames = {adaptive:"Evidence-aware", fixed:"Always review", single:"Single reader"};

function clearTeamTrace() {
  $("teamTrace").hidden = true;
  ["teamAnswer","teamReason","teamOutcome","teamMetrics","teamGraph","teamStepTitle","teamStepTiming",
    "teamStepReason","teamStepFacts","teamReceipt","teamEvidence","teamMetadata","teamRunLabel","teamComparison"].forEach(id => $(id).replaceChildren());
  $("teamPayload").open = false;
  $("teamComparison").hidden = true;
}
function syncTeamIdentity() {
  const account = localAuth.authenticated && !localAuth.account.password_change_required ? localAuth.account.username : null;
  if (teamAccount === account) return;
  teamAccount = account;
  teamEpoch++;
  $("teamQuestion").value = "";
  $("teamSubmit").disabled = false;
  setTeamMode("examples");
}
function teamPair(box, name, value) {
  const item = element("div");
  item.append(element("dt", "", name), element("dd", "", value));
  box.appendChild(item);
}
function teamStepDetail(item, index) {
  Array.from($("teamGraph").children).forEach((btn,i) => btn.setAttribute("aria-pressed",String(i === index)));
  $("teamStepTitle").textContent = teamRoles[item.role];
  $("teamStepTiming").textContent = item.elapsed_ms == null ? "" : item.elapsed_ms + " ms";
  $("teamStepReason").textContent = item.error || item.reason;
  const facts = $("teamStepFacts");
  facts.replaceChildren();
  teamPair(facts,"Status",item.status);
  if (item.candidates != null) teamPair(facts,"Candidate window",item.candidates + " / " + item.limit);
  if (item.context_bytes != null) teamPair(facts,"Evidence size",item.context_bytes + " bytes");
  if (item.input_tokens != null) teamPair(facts,"Input / output tokens",item.input_tokens + " / " + item.output_tokens);
  if (item.missing && item.missing.length) teamPair(facts,"Missing evidence",item.missing.join(", "));
  if (item.source_ids && item.source_ids.length) teamPair(facts,"Sources",item.source_ids.join(", "));
  if (item.quote) teamPair(facts,"Returned quote",item.quote);
  $("teamReceipt").hidden = !item.receipt_id;
  $("teamReceipt").textContent = item.receipt_id ? "Delivery receipt · " + item.receipt_id : "";
  $("teamPayload").open = false;
  $("teamPayload").hidden = !item.evidence;
  $("teamEvidenceLabel").textContent = item.status === "failed" ? "Evidence submitted for this attempt" : "Evidence delivered to this agent";
  $("teamEvidence").textContent = item.evidence || "";
}
function teamCompare(caseId) {
  const box = $("teamComparison");
  box.replaceChildren();
  box.hidden = !caseId;
  if (!caseId) return;
  const table = element("table"), head = element("thead"), body = element("tbody"), tr = element("tr");
  table.appendChild(element("caption","","Measured policies on this case"));
  ["Policy","Outcome","Lookups","Model calls","Input tokens"].forEach(name => tr.appendChild(element("th","",name)));
  head.appendChild(tr);
  ["single","fixed","adaptive"].forEach(policy => {
    const record = teamRows.find(row => row.case_id === caseId && row.run.policy === policy);
    if (!record) return;
    const row = element("tr"), run = record.run, name = element("th","",teamPolicyNames[policy]);
    name.scope = "row";
    row.appendChild(name);
    [record.grade.correct ? "Correct" : "Incorrect",run.lookups,run.model_calls,run.usage_complete ? run.input_tokens : "Unknown"].forEach(v => row.appendChild(element("td","",v)));
    body.appendChild(row);
  });
  table.append(head,body);
  box.appendChild(table);
}
function showTeamTrace(run, record) {
  clearTeamTrace();
  $("teamTrace").hidden = false;
  $("teamOutcome").textContent = teamOutcomes[run.outcome] + (record ? (record.grade.correct ? " · correct on this case" : " · incorrect on this case") : "");
  $("teamAnswer").textContent = run.answer || run.question;
  $("teamReason").textContent = run.reason;
  $("teamRunLabel").textContent = teamPolicyNames[run.policy] + " · " + run.model;
  teamPair($("teamMetrics"), "Model calls", run.model_calls + " / " + run.max_calls);
  teamPair($("teamMetrics"), "Input tokens", run.usage_complete ? run.input_tokens : "Unknown");
  teamPair($("teamMetrics"), "Output tokens", run.usage_complete ? run.output_tokens : "Unknown");
  const items = run.steps.concat([{role:"decision", reason:run.reason, status:run.outcome, source_ids:run.source_ids}]);
  items.forEach((item,index) => {
    const btn = element("button","team-node");
    btn.type = "button";
    const modelStep = item.role === "reviewer" || item.role === "reader";
    const iconId = {lookup:"database",expanded_lookup:"search",reviewer:"shield-check",reader:"node",decision:"flag"}[item.role];
    const meta = element("span","team-node-meta");
    const icon = document.createElementNS("http://www.w3.org/2000/svg","svg");
    const use = document.createElementNS("http://www.w3.org/2000/svg","use");
    use.setAttribute("href","#i-" + iconId);
    icon.setAttribute("class","icon");
    icon.setAttribute("aria-hidden","true");
    icon.appendChild(use);
    meta.append(icon,document.createTextNode(modelStep ? "Local model" : item.role === "decision" ? "Outcome" : "AtMem"));
    const secondary = item.input_tokens != null ? item.input_tokens + " input tokens" :
      item.candidates != null ? item.candidates + (item.candidates === 1 ? " candidate" : " candidates") : (teamOutcomes[run.outcome] || item.status);
    btn.append(meta,element("b","",teamRoles[item.role]),element("small","",secondary));
    btn.onclick = () => teamStepDetail(item,index);
    $("teamGraph").appendChild(btn);
  });
  const reader = items.findIndex(item => item.role === "reviewer");
  const selected = reader >= 0 ? reader : Math.max(0, items.length - 2);
  teamStepDetail(items[selected],selected);
  $("teamMetadata").textContent = run.scope.workspace_id + " · " + run.started_at + " · " + run.elapsed_ms + " ms total";
  teamCompare(record && record.case_id);
}
function showTeamExample() {
  if (teamMode !== "examples" || !teamRows.length) return;
  const record = teamRows.find(row => row.case_id === $("teamCase").value && row.run.policy === $("teamPolicy").value);
  if (!record) return;
  $("teamNotice").textContent = "Recorded local benchmark · " + record.run.question;
  showTeamTrace(record.run,record);
}
async function loadTeamExamples() {
  if (teamRows.length) { showTeamExample(); return; }
  if (teamLoading) return teamLoading;
  teamLoading = (async () => {
    try {
      const data = await get("/api/agent-team/examples");
      teamRows = data.rows;
      $("teamCase").replaceChildren();
      [...new Set(teamRows.map(row => row.case_id))].forEach(id => $("teamCase").appendChild(new Option(teamCaseNames[id] || id,id)));
      $("teamCase").value = "corrected";
      showTeamExample();
    } catch (error) {
      if (teamMode === "examples") $("teamNotice").textContent = "Could not load recorded examples. " + error.message;
    } finally {teamLoading = null;}
  })();
  return teamLoading;
}
function setTeamMode(mode) {
  teamEpoch++;
  teamMode = mode;
  clearTeamTrace();
  const examples = mode === "examples";
  $("teamExamples").setAttribute("aria-pressed",String(examples));
  $("teamLive").setAttribute("aria-pressed",String(!examples));
  $("teamCaseLabel").hidden = !examples;
  ["teamQuestionLabel","teamBudgetLabel","teamSubmit"].forEach(id => $(id).hidden = examples);
  $("teamSubmit").disabled = false;
  $("teamQuestion").required = !examples;
  $("teamPolicy").value = examples ? "fixed" : "adaptive";
  $("teamNotice").textContent = examples ? "Loading recorded benchmark…" :
    "Uses active workspace memory and local Ollama (qwen2.5:1.5b). Live traces are visible in this tab.";
  if (examples) loadTeamExamples();
}
$("teamExamples").onclick = () => setTeamMode("examples");
$("teamLive").onclick = () => setTeamMode("live");
$("teamCase").onchange = showTeamExample;
$("teamPolicy").onchange = showTeamExample;
$("teamForm").onsubmit = async event => {
  event.preventDefault();
  if (teamMode !== "live" || $("teamSubmit").disabled) return;
  const epoch = ++teamEpoch;
  const body = {question:$("teamQuestion").value.trim(), policy:$("teamPolicy").value, max_calls:Number($("teamBudget").value)};
  clearTeamTrace();
  $("teamSubmit").disabled = true;
  $("teamNotice").textContent = "Running the local team…";
  try {
    const run = await post("/api/agent-team/run",body);
    if (teamEpoch !== epoch) return;
    $("teamNotice").textContent = "Live workspace · " + run.question;
    showTeamTrace(run,null);
  } catch (error) {
    if (teamEpoch === epoch) $("teamNotice").textContent = error.message;
  } finally {
    if (teamEpoch === epoch) $("teamSubmit").disabled = false;
  }
};
