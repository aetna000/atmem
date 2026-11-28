// Kept inside the dashboard closure to share its session and CSRF handling.
let teamRows = [], teamLoading = null, teamMode = "examples", teamEpoch = 0, teamAccount = null;
const teamCaseNames = {direct:"Direct fact", corrected:"Confirmed correction", busy:"Similar routing codes",
  expired:"Expired fact", conflict:"Conflicting sources", missing:"Missing evidence"};
const teamRoles = {lookup:"Memory lookup", expanded_lookup:"Expanded lookup", reviewer:"Source reviewer",
  reader:"Answer reader", decision:"Decision", offer:"Offer references", receive:"Verify and deliver", complete:"Return quote", verify:"Recheck revision"};
const teamOutcomes = {offered:"Offered", delivered:"Delivered", withheld:"Withheld", answered:"Answered", abstained:"Abstained", failed:"Call failed", unavailable:"Model unavailable"};
const teamPolicyNames = {portable:"Cross-host handoff", adaptive:"Evidence-aware", fixed:"Always review", single:"Single reader"};

let teamDemo = null;
let teamRun = null, teamStep = null, teamCursor = null, teamIndex = [];
function clearTeamTrace() {
  teamRun = teamStep = null;
  $("teamResults").hidden = true;
  $("teamOutcomeList").replaceChildren();
  $("teamAttach").reset();
  $("teamAttachPanel").open = false;
  $("teamTrace").hidden = true;
  ["teamAnswer","teamReason","teamOutcome","teamMetrics","teamGraph","teamStepTitle","teamStepTiming",
    "teamStepReason","teamStepFacts","teamReceipt","teamEvidence","teamMetadata","teamRunLabel","teamComparison"].forEach(id => $(id).replaceChildren());
  $("teamPayload").open = false;
  $("teamComparison").hidden = true;
}
function syncTeamIdentity() {
  const account = localAuth.authenticated && !localAuth.account.password_change_required ? JSON.stringify([localAuth.account.username,localAuth.account.role,localAuth.account.scope,localAuth.account.revision]) : null;
  if (teamAccount === account) return;
  teamAccount = account;
  teamEpoch++;
  $("teamQuestion").value = "";
  $("teamFilter").value = "";
  $("teamRunList").replaceChildren();
  teamIndex = []; teamCursor = null;
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
  teamStep = item.step_id || null;
  $("teamAttachPanel").hidden = teamMode !== "project" || !teamStep || !localAuth.account || !["administrator","evidence_collector"].includes(localAuth.account.role);
  teamPair(facts,"Status",item.status);
  if (item.model) teamPair(facts,"Model",item.model);
  if (item.host) teamPair(facts,"Host / agent",item.host + " / " + item.agent_id);
  if (item.parent_step_id) teamPair(facts,"Parent step",item.parent_step_id);
  if (item.generation != null) teamPair(facts,"Memory generation",item.generation);
  if (item.evidence_sha256 || item.context_sha256) teamPair(facts,item.evidence_sha256 ? "Passage digest" : "Prepared context digest",item.evidence_sha256 || item.context_sha256);
  (item.provenance || []).forEach((source,sourceIndex) => {
    teamPair(facts,"Source span",source.source_id + " · character offsets [" + source.start_offset + ", " + source.end_offset + ")");
    teamPair(facts,"Record",source.record_id);
    teamPair(facts,"Source excerpt digest",source.excerpt_sha256);
    const sample = teamMode === "examples" && teamDemo && teamDemo.excerpts && teamDemo.excerpts[source.excerpt_sha256];
    if (teamMode === "project" || sample) {
      const holder = element("div"), proof = element("dd");
      const button = projectButton("Inspect original excerpt",async () => {
        const id = teamRun.run_id, epoch = teamEpoch;
        try {
          const value = sample || await post("/api/agent-team/history",{action:"source",run_id:id,step_id:item.step_id,source_index:sourceIndex});
          if (epoch !== teamEpoch || teamStep !== item.step_id) return;
          proof.textContent = value.status === "verified" ? value.excerpt : "Original source unavailable.";
        } catch (error) {if (epoch === teamEpoch && teamStep === item.step_id) proof.textContent = error.message;}
      });
      holder.append(element("dt","","Original text"),button,proof); facts.appendChild(holder);
    }
  });
  if (item.candidates != null) teamPair(facts,"Candidate window",item.candidates + " / " + item.limit);
  if (item.context_bytes != null) teamPair(facts,"Evidence size",item.context_bytes + " bytes");
  if (item.input_tokens != null) teamPair(facts,"Input / output tokens",item.input_tokens + " / " + item.output_tokens);
  if (item.missing && item.missing.length) teamPair(facts,"Missing evidence",item.missing.join(", "));
  if (item.source_ids && item.source_ids.length) teamPair(facts,"Sources",item.source_ids.join(", "));
  if (item.quote) teamPair(facts,"Returned quote",item.quote);
  $("teamReceipt").hidden = !item.receipt_id;
  $("teamReceipt").textContent = item.receipt_id ? "Delivery receipt · " + item.receipt_id : "";
  $("teamPayload").open = false;
  const payload = item.evidence || (item.passages || []).map(p => p.text).join("\n");
  $("teamPayload").hidden = !payload && !item.receipt_id;
  $("teamEvidenceLabel").textContent = item.status === "failed" ? "Evidence submitted for this attempt" : "Evidence delivered to this agent";
  $("teamEvidence").textContent = payload;
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
  teamRun = run;
  $("teamTrace").hidden = false;
  $("teamOutcome").textContent = teamOutcomes[run.outcome] + (record ? (record.grade.correct ? " · correct on this case" : " · incorrect on this case") : "");
  $("teamAnswer").textContent = run.answer || run.question;
  $("teamReason").textContent = run.reason;
  $("teamRunLabel").textContent = teamPolicyNames[run.policy] + " · " + run.model;
  teamPair($("teamMetrics"), "Model calls", run.model_calls == null ? "Unreported" : run.model_calls + (run.max_calls == null ? "" : " / " + run.max_calls));
  teamPair($("teamMetrics"), "Input tokens", run.usage_complete ? run.input_tokens : "Unknown");
  teamPair($("teamMetrics"), "Output tokens", run.usage_complete ? run.output_tokens : "Unknown");
  const items = run.policy === "portable" ? run.steps : run.steps.concat([{role:"decision", reason:run.reason, status:run.outcome, source_ids:run.source_ids}]);
  items.forEach((item,index) => {
    const btn = element("button","team-node");
    btn.type = "button";
    const modelStep = item.role === "reviewer" || item.role === "reader";
    const iconId = {lookup:"database",expanded_lookup:"search",reviewer:"shield-check",reader:"node",decision:"flag",offer:"node",receive:"shield-check",complete:"flag",verify:"search"}[item.role];
    const meta = element("span","team-node-meta");
    const icon = document.createElementNS("http://www.w3.org/2000/svg","svg");
    const use = document.createElementNS("http://www.w3.org/2000/svg","use");
    use.setAttribute("href","#i-" + iconId);
    icon.setAttribute("class","icon");
    icon.setAttribute("aria-hidden","true");
    icon.appendChild(use);
    meta.append(icon,document.createTextNode((modelStep && (!item.host || item.host === "atmem-sdk")) ? "Local model" : item.host || (item.role === "decision" ? "Outcome" : "AtMem")));
    const secondary = item.input_tokens != null ? item.input_tokens + " input tokens" :
      item.candidates != null ? item.candidates + (item.candidates === 1 ? " candidate" : " candidates") : (item.status === "sufficient" ? "Sufficient evidence" : teamOutcomes[item.status] || item.status);
    btn.append(meta,element("b","",teamRoles[item.role]),element("small","",secondary));
    btn.onclick = () => teamStepDetail(item,index);
    $("teamGraph").appendChild(btn);
  });
  const reader = items.findIndex(item => item.role === "reviewer");
  const selected = run.policy === "portable" ? items.length - 1 : reader >= 0 ? reader : Math.max(0, items.length - 2);
  teamStepDetail(items[selected],selected);
  $("teamMetadata").textContent = run.scope.workspace_id + " · " + run.started_at + " · " + run.elapsed_ms + " ms total";
  teamCompare(record && record.case_id);
  if (teamMode === "project" || (teamMode === "examples" && run.policy === "portable")) showProjectResults(run,items);
}
function showTeamExample() {
  if (teamMode !== "examples" || !teamRows.length) return;
  const demoName = $("teamCase").value;
  const hostDemo = teamDemo && (demoName === "host-corrected" || demoName === "host-original");
  $("teamPolicy").closest("label").hidden = !!hostDemo;
  if (hostDemo) {
    const run = teamDemo[demoName === "host-corrected" ? "corrected" : "original"];
    $("teamNotice").textContent = "Recorded synthetic workspace · " + run.question;
    showTeamTrace(run,null);
    $("teamComparison").hidden = false;
    $("teamComparison").replaceChildren(projectTable("Frozen evaluation · 10 tasks",["Policy","Correct","Stale","Model calls","Input tokens"],
      teamDemo.policies.map(p => [teamPolicyNames[p.policy],p.correct + " / 10",p.stale,p.model_calls,p.input_tokens])));
    return;
  }
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
      teamRows = data.rows; teamDemo = data.project_example;
      $("teamCase").replaceChildren();
      [...new Set(teamRows.map(row => row.case_id))].forEach(id => $("teamCase").appendChild(new Option(teamCaseNames[id] || id,id)));
      if (teamDemo) {
        $("teamCase").prepend(new Option("OpenClaw → Hermes · original","host-original"));
        $("teamCase").prepend(new Option("OpenClaw → Hermes · corrected replay","host-corrected"));
        $("teamCase").value = "host-corrected";
      } else $("teamCase").value = "corrected";
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
  $("teamLive").setAttribute("aria-pressed",String(mode === "live"));
  $("teamProject").setAttribute("aria-pressed",String(mode === "project"));
  $("teamForm").hidden = mode === "project";
  $("teamHistory").hidden = mode !== "project";
  $("teamCaseLabel").hidden = !examples;
  $("teamPolicy").closest("label").hidden = false;
  ["teamQuestionLabel","teamBudgetLabel","teamSubmit"].forEach(id => $(id).hidden = examples);
  $("teamSubmit").disabled = false;
  $("teamQuestion").required = !examples;
  $("teamPolicy").value = examples ? "fixed" : "single";
  $("teamNotice").textContent = examples ? "Loading recorded benchmark…" :
    "Uses active workspace memory and local Ollama (qwen2.5:1.5b). Full evidence capture saves the run to project history.";
  if (examples) loadTeamExamples();
  if (mode === "project") loadProjectRuns();
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
    $("teamNotice").textContent = (run.archived ? "Saved to project runs · " : "This tab only · ") + run.question;
    showTeamTrace(run,null);
  } catch (error) {
    if (teamEpoch === epoch) $("teamNotice").textContent = error.message;
  } finally {
    if (teamEpoch === epoch) $("teamSubmit").disabled = false;
  }
};

function projectTable(caption, headings, rows) {
  const table = element("table"), head = element("thead"), tr = element("tr"), body = element("tbody");
  table.appendChild(element("caption","",caption));
  headings.forEach(label => tr.appendChild(element("th","",label)));
  head.appendChild(tr);
  rows.forEach(cells => {
    const row = element("tr");
    cells.forEach(value => {
      const cell = element("td");
      if (value instanceof Node) cell.appendChild(value);
      else cell.textContent = value == null ? "Unreported" : String(value);
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
  table.append(head,body);
  return table;
}
function projectButton(label,action) {
  const button = element("button","secondary",label);
  button.type = "button"; button.onclick = action;
  return button;
}
async function loadProjectRuns(more=false) {
  const epoch = ++teamEpoch;
  clearTeamTrace();
  if (!more) {teamIndex = []; teamCursor = null; $("teamRunList").replaceChildren();}
  $("teamMore").hidden = true;
  $("teamNotice").textContent = "Loading project runs…";
  try {
    const data = await post("/api/agent-team/history",{action:"list",outcome_ref:$("teamFilter").value.trim(),before:more ? teamCursor : ""});
    if (epoch !== teamEpoch) return;
    teamIndex = teamIndex.concat(data.runs);
    teamCursor = data.next_cursor;
    $("teamMore").hidden = !teamCursor;
    $("teamRunList").replaceChildren(projectTable("Project executions",["Question","Route","Result","Engineering outcome"],
      teamIndex.map(run => [projectButton(run.question,() => openProjectRun(run.run_id)),teamPolicyNames[run.policy],
        teamOutcomes[run.outcome],run.outcomes.map(item => item.reference + " · " + item.status).join(", ") || "—"])));
    $("teamNotice").textContent = teamIndex.length ? "Select a run to inspect its evidence." : "No matching project runs.";
  } catch (error) {if (epoch === teamEpoch) $("teamNotice").textContent = error.message;}
}
async function openProjectRun(id) {
  const epoch = ++teamEpoch;
  clearTeamTrace();
  try {
    const run = await post("/api/agent-team/history",{action:"get",run_id:id});
    if (epoch !== teamEpoch) return;
    $("teamNotice").textContent = run.question;
    showTeamTrace(run,null);
  } catch (error) {if (epoch === teamEpoch) $("teamNotice").textContent = error.message;}
}
function showProjectResults(run,items) {
  $("teamResults").hidden = false;
  $("teamRerun").hidden = teamMode !== "project";
  const box = $("teamOutcomeList");
  const results = run.outcomes || [];
  box.replaceChildren();
  if (results.length) {
    box.appendChild(projectTable("Outcomes linked to this execution",["Reference","Status","Evidence","Linked step"],results.map(result => {
      const i = items.findIndex(item => item.step_id === result.step_id);
      const ref = result.url ? element("a","",result.reference) : result.reference;
      if (result.url) {ref.href = result.url; ref.rel = "noreferrer"; ref.target = "_blank";}
      const proof = element("span","",result.verification === "imported_junit" ? "JUnit · " + result.classname + "." + result.test_name : "Reported by " + result.recorded_by);
      if (result.report_sha256) proof.appendChild(element("small","team-digest",result.report_sha256));
      return [ref,result.status,proof,i < 0 ? "Unavailable" : projectButton(teamRoles[items[i].role],() => teamStepDetail(items[i],i))];
    })));
  } else box.appendChild(element("p","sub","No engineering outcomes attached."));
  if (!run.rerun_of) return;
  box.appendChild(projectButton("Open original execution",() => {
    if (teamMode === "examples") {$("teamCase").value = "host-original"; showTeamExample();}
    else openProjectRun(run.rerun_of);
  }));
  if (run.comparison) {
    const labels = {outcome:"Decision",answer:"Returned value",input_tokens:"Input tokens",output_tokens:"Output tokens",
      cost_microusd:"Reported model cost (µUSD)",estimated_reader_cost_microusd:"Reader tariff estimate (µUSD)",
      reported_reader_cost_microusd:"Reported reader cost (µUSD)",reader_cost_delta_microusd:"Reported minus estimate (µUSD)",elapsed_ms:"Elapsed wall time (ms)"};
    const rows = run.comparison.filter(m => !m.metric.includes("reader_cost") || m.before != null || m.after != null)
      .map(m => [labels[m.metric],m.before,m.after]);
    const refs = new Set([...(run.previous_outcomes || []),...results].map(r => r.reference));
    refs.forEach(ref => rows.push([ref,...[run.previous_outcomes || [],results].map(group => group.filter(r => r.reference === ref).map(r => r.status).join(", ") || "—")]));
    box.appendChild(projectTable("Original and rerun",["Measure","Original","Rerun"],rows));
  }
}
$("teamProject").onclick = () => setTeamMode("project");
$("teamHistorySearch").onsubmit = event => {event.preventDefault(); loadProjectRuns();};
$("teamMore").onclick = () => loadProjectRuns(true);
$("teamRerun").onclick = async () => {
  if (!teamRun) return;
  const epoch = ++teamEpoch, parent = teamRun.run_id;
  $("teamRerun").disabled = true;
  try {
    const run = await post("/api/agent-team/run",{rerun_of:parent,policy:"single",max_calls:1});
    if (epoch !== teamEpoch) return;
    if (run.archived) {await loadProjectRuns(); if (teamMode === "project") await openProjectRun(run.run_id);}
    else {$("teamNotice").textContent = "Rerun finished with capture disabled."; showTeamTrace(run,null); $("teamResults").hidden = true;}
  } catch (error) {if (epoch === teamEpoch) $("teamNotice").textContent = error.message;}
  finally {$("teamRerun").disabled = false;}
};
$("teamAttach").onsubmit = async event => {
  event.preventDefault();
  if (!teamRun || !teamStep) return;
  const epoch = ++teamEpoch, id = teamRun.run_id;
  const result = {kind:$("teamKind").value,reference:$("teamReference").value.trim(),step_id:teamStep,
    status:$("teamState").value.trim(),url:$("teamURL").value.trim()};
  try {
    const file = $("teamFile").files[0];
    if (file) {
      if (file.size > 256000) throw Error("JUnit report exceeds 256,000 bytes.");
      result.junit = await file.text();
      result.classname = $("teamClass").value.trim(); result.test_name = $("teamTestName").value.trim();
    }
    if (epoch !== teamEpoch) return;
    const run = await post("/api/agent-team/history",{action:"attach",run_id:id,outcome:result});
    if (epoch !== teamEpoch) return;
    await loadProjectRuns(); if (teamMode === "project") await openProjectRun(run.run_id);
  } catch (error) {if (epoch === teamEpoch) $("teamNotice").textContent = error.message;}
};
