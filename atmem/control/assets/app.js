(function(){
"use strict";
var state=null,reviewQueue={records:[]},productInfo={},blackboxIndex={runs:[]},blackboxArchiveRows=[],blackboxStories={},flightRange="7d",bridgeRefreshStatus={available:false},activityVisible=10,activitySearchTimer=null,csrf="",progressTimer=null,progressStarted=0;
var auditCursors=[null],auditPageIndex=0,auditLast=null,auditFacetsLoaded=false;
var $=function(id){return document.getElementById(id)};
function text(id,value){$(id).textContent=value==null?"—":String(value)}
function number(value){return Number(value||0).toLocaleString()}
function showError(error){text("error",error&&error.message?error.message:error);$("error").classList.add("show")}
function clearError(){$("error").classList.remove("show")}
function showProgress(title,detail){
 text("progressTitle",title);text("progressDetail",detail);progressStarted=Date.now();
 text("progressTime","0s");$("progress").classList.add("show");$("hero").classList.add("loading");
 $("switchBtn").disabled=true;$("refreshBtn").disabled=true;
 if(progressTimer)clearInterval(progressTimer);
 progressTimer=setInterval(function(){text("progressTime",Math.floor((Date.now()-progressStarted)/1000)+"s")},1000)
}
function hideProgress(){
 if(progressTimer)clearInterval(progressTimer);progressTimer=null;$("progress").classList.remove("show");
 $("hero").classList.remove("loading");$("refreshBtn").disabled=false;
 var readiness=state&&state.readiness?state.readiness:{};
 $("switchBtn").disabled=(active()||recovery())?false:!readiness.ready_for_active
}
async function working(title,detail,operation){
 clearError();showProgress(title,detail);
 try{return await operation()}finally{hideProgress()}
}
async function get(path){var r=await fetch(path,{headers:{"Accept":"application/json"}});var v=await r.json();if(!r.ok)throw new Error(v.error||"Request failed");return v}
async function post(path,body){var r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:JSON.stringify(body||{})});var v=await r.json();if(!r.ok)throw new Error(v.error||"Request failed");return v}
function element(name,className,value){var node=document.createElement(name);if(className)node.className=className;if(value!=null)node.textContent=value;return node}
function zeroSequence(compact){var zeros=element("span","zeros"+(compact?" compact":""));zeros.setAttribute("aria-hidden","true");for(var i=0;i<4;i++)zeros.appendChild(element("span","","0"));return zeros}
function loadingNode(label,className){var node=element("div",(className?className+" ":"")+"zeroloading");node.setAttribute("role","status");node.append(zeroSequence(true),element("span","",label));return node}
function tableLoading(label){var row=element("tr"),cell=element("td","empty");cell.colSpan=7;cell.appendChild(loadingNode(label));row.appendChild(cell);return row}
function preferredTheme(){try{var saved=localStorage.getItem("atmem-theme");if(saved==="light"||saved==="dark")return saved}catch(_){}return window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
function applyTheme(theme,persist){document.documentElement.dataset.theme=theme;var button=$("themeToggle"),next=theme==="dark"?"Light":"Dark";text("themeToggle",next+" mode");button.setAttribute("aria-label","Switch to "+next.toLowerCase()+" mode");button.setAttribute("aria-pressed",theme==="light"?"true":"false");if(persist){try{localStorage.setItem("atmem-theme",theme)}catch(_){}}}
function renderAgentTopology(){var topology=(state&&state.agent_topology)||{},agents=Array.isArray(topology.agents)?topology.agents:[],workspaces=Array.isArray(topology.workspaces)?topology.workspaces:[],box=$("agentMap"),verified=topology.verified===true,isOpenClaw=state&&state.host==="openclaw";var byId={};workspaces.forEach(function(row){byId[row.workspace_id]=row});text("agentCount",agents.length);text("workspaceCount",workspaces.length);$("agentCoverageStatus").classList.toggle("bad",!verified);text("agentCoverageIcon",verified?"✓":"!");text("agentCoverageHeadline",verified?"All registered agents are covered":topology.status==="unavailable"?"Agent coverage could not be checked":isOpenClaw?"Agent topology needs a bridge refresh":"Agent topology needs correction");text("agentCoverageDetail",topology.reason||"No agent topology evidence is available.");box.replaceChildren();if(!agents.length){box.appendChild(element("div","activityempty",isOpenClaw?"No persistent OpenClaw agents were detected.":"No persistent agents are registered."));return}agents.forEach(function(agent){var scope=byId[agent.workspace_id]||{},members=scope.agent_ids||[],mode=scope.parent_workspace_id?"Nested isolated memory":members.length>1?"Shared workspace memory":"Isolated workspace memory",row=element("button","agentrow"),identity=element("span"),scopeBox=element("span","agentscope"),workspace=element("span"),status=element("small","",verified?"✓ Working":"! Not verified");row.type="button";row.title="Filter recent actions for "+(agent.name||agent.agent_id);identity.append(element("b","",agent.name||agent.agent_id||"Unnamed agent"),element("small","","Agent ID: "+(agent.agent_id||"not recorded")+(agent.is_default?" · default":"")));scopeBox.append(element("b","",mode),element("small","","Memory subject: "+(agent.subject_id||scope.subject_id||"not recorded")+(members.length>1?" · shared with "+members.filter(function(id){return id!==agent.agent_id}).join(", "):"")));workspace.append(element("b","",String(agent.workspace||"Workspace unavailable").split("/").filter(Boolean).slice(-2).join("/")),element("small","","Workspace: "+(agent.workspace||"not recorded")));row.append(identity,scopeBox,workspace,status);row.onclick=function(){$("activityQuery").value=agent.agent_id||"";applyActivityFilters().catch(showError);$("blackboxCard").scrollIntoView({behavior:"smooth",block:"start"})};box.appendChild(row)})}
function renderProductVersions(){var verification=(state&&state.verification)||{},npmVersion=bridgeRefreshStatus.runtime_version||bridgeRefreshStatus.installed_version||productInfo.atmem_npm_version,isOpenClaw=state&&state.host==="openclaw";text("versionOpenClaw",verification.host_version||"not detected");text("versionPip",productInfo.atmem_pip_version||"not detected");text("versionNpm",npmVersion||"not detected");$("versionOpenClawChip").style.display=isOpenClaw?"inline-flex":"none";$("versionNpmChip").style.display=isOpenClaw?"inline-flex":"none"}
function providerState(){return (state&&state.provider_state)||"unavailable"}
function active(){return providerState()==="active"}
function recovery(){return providerState()==="restore_required"}
function shortDigest(value){return value?String(value).slice(0,16)+"…":"not recorded"}
function displayTime(value){if(!value)return "not recorded";var date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString([], {dateStyle:"medium",timeStyle:"short"})}
function evidence(label,value,mono){var box=element("div","evidence"),name=element("span","",label),body=element("b",mono?"mono":"",value||"not recorded");box.append(name,body);return box}
function chainStep(label,ok,detail){var box=element("div","chainstep "+(ok?"ok":"missing"));box.append(element("b","",label),element("span","",detail));return box}
function blackboxEventDetail(event){var p=event.payload||{},parts=[];if(p.tool_name)parts.push(p.tool_name);if(p.model)parts.push([p.provider,p.model].filter(Boolean).join(" / "));if(p.outcome)parts.push(p.outcome);if(event.tool_call_id)parts.push(event.tool_call_id);return parts.join(" · ")||"digest-bound host event"}
function storyStep(position,title,content){var box=element("div","storystep"),numberBox=element("span","storynumber",position),copy=element("div");copy.append(element("h3","",title));if(typeof content==="string")copy.append(element("p","storytext",content));else if(content)copy.append(content);box.append(numberBox,copy);return box}
function flightEventTitle(type){return ({"turn.input":"Request received","context.disposition":"Memory added to the request","model.input":"Request sent to the model","model.output":"Model replied","turn.ended":"Session finished","tool.requested":"Tool requested","tool.completed":"Tool finished"})[type]||String(type||"Evidence event").replaceAll("."," ")}
function focusFlightEvidence(value){var technical=document.querySelector("#auditorBody .technical");if(technical)technical.open=true;var events=Array.from(document.querySelectorAll("#auditorBody .event[data-evidence]")),match=events.find(function(item){return item.dataset.evidence.indexOf(String(value))>=0});events.forEach(function(item){item.classList.remove("focused")});if(match){match.classList.add("focused");if(match.tagName==="DETAILS")match.open=true;match.scrollIntoView({behavior:"smooth",block:"center"})}}
function evidenceChip(label,value){var button=element("button","evidencechip",label+": "+value);button.type="button";button.title="Open the event containing "+value;button.onclick=function(){focusFlightEvidence(value)};return button}
function currentRun(){return (blackboxIndex.runs||[])[0]||null}
function activityState(row){var active=(row.attention_points||[]),reviewed=!active.length&&(row.acknowledged_attention_points||[]).length;if(reviewed)return{tone:"",icon:"✓",label:"Reviewed"};if(row.verdict==="failed"||row.verdict==="completed_with_tool_errors"||active.some(function(p){return p.severity==="critical"||p.code==="flight_failed"||p.code==="tool_errors"}))return{tone:"bad",icon:"!",label:"Failed"};if(active.length||row.verdict==="incomplete_evidence")return{tone:"warn",icon:"!",label:"Review"};return{tone:"",icon:"✓",label:"Completed"}}
function oneLine(value,fallback){var line=String(value||"").split(/\r?\n/)[0].trim();return line||fallback}
function activityTimeMatch(row){var range=$("activityWhen").value;if(range==="all")return true;var at=new Date(row.ended_at||row.started_at||0),now=new Date(),today=new Date(now.getFullYear(),now.getMonth(),now.getDate()),tomorrow=new Date(today);tomorrow.setDate(tomorrow.getDate()+1);if(range==="today")return at>=today&&at<tomorrow;if(range==="yesterday"){var yesterday=new Date(today);yesterday.setDate(yesterday.getDate()-1);return at>=yesterday&&at<today}var days=range==="30d"?30:7;return at>=new Date(now.getTime()-days*86400000)}
function activityTopicMatch(story){var topic=$("activityTopic").value;if(topic==="all")return true;var text=flightStoryText(story),tools=(story.tools||[]).join(" ").toLowerCase();if(topic==="agents")return /\b(agent|agents|subagent|openclaw)\b/.test(text);if(topic==="memory")return /\b(memory|remember|recall|context)\b/.test(text)||/memory/.test(tools);if(topic==="web")return (story.websites||[]).length>0||/\b(web|browser|fetch|http)/.test(text+" "+tools);if(topic==="email")return /\b(email|mail|gmail|outlook)\b/.test(text+" "+tools);if(topic==="tools")return (story.tools||[]).length>0;return !(story.tools||[]).length}
function activityFilteredRows(){var query=$("activityQuery").value.trim().toLowerCase();return (blackboxIndex.runs||[]).filter(function(row){if(!activityTimeMatch(row))return false;var story=blackboxStories[row.run_id]||{};return activityTopicMatch(story)&&(!query||flightMetadata(row).includes(query)||flightStoryText(story).includes(query))})}
async function ensureActivityStories(rows){for(var offset=0;offset<rows.length;offset+=12){await Promise.all(rows.slice(offset,offset+12).filter(function(row){return !blackboxStories[row.run_id]}).map(async function(row){try{blackboxStories[row.run_id]=await get("/api/blackbox/story?run_id="+encodeURIComponent(row.run_id))}catch(_){blackboxStories[row.run_id]={}}}))}}
function renderActivityTimeline(){var box=$("activityTimeline");if(!box)return;var all=activityFilteredRows(),rows=all.slice(0,activityVisible),more=$("activityLoadMore");box.replaceChildren();if(!rows.length)box.appendChild(element("div","activityempty","No matching actions."));rows.forEach(function(row){var story=blackboxStories[row.run_id]||{},state=activityState(row),point=(row.attention_points||[])[0],button=element("button","activityrow "+state.tone),node=element("span","activitynode",state.icon),copy=element("span","activitycopy"),title=oneLine(story.request_text,"Agent action"),result=point?point.detail:story.blocked_by||oneLine(story.response_text,state.label),time=element("span","activitytime",displayTime(row.ended_at||row.started_at));button.type="button";button.setAttribute("aria-label",state.label+": "+title);copy.append(element("b","",title),element("span","",result));button.append(node,copy,time);button.onclick=function(){inspectBlackbox(row.run_id)};box.appendChild(button)});var loaded=(blackboxIndex.runs||[]).length,total=Number(blackboxIndex.total_runs||loaded),hasMoreVisible=activityVisible<all.length,hasMoreHistory=loaded<total;more.style.display=hasMoreVisible||hasMoreHistory?"inline-block":"none";text("activityCount",rows.length+" shown"+(all.length!==rows.length?" · "+all.length+" match":""))}
async function applyActivityFilters(){var box=$("activityTimeline"),base=(blackboxIndex.runs||[]).filter(activityTimeMatch);box.replaceChildren(loadingNode("Searching history…","activityempty"));await ensureActivityStories(base);activityVisible=10;renderActivityTimeline()}
async function loadMoreActivity(){var all=activityFilteredRows(),loaded=(blackboxIndex.runs||[]).length,total=Number(blackboxIndex.total_runs||loaded);if(activityVisible>=all.length&&loaded<total){var page=await get("/api/blackbox/runs?limit=500&offset="+loaded);blackboxIndex.runs=(blackboxIndex.runs||[]).concat(page.runs||[]);blackboxIndex.total_runs=page.total_runs||total;blackboxArchiveRows=(blackboxIndex.runs||[]).slice();all=activityFilteredRows()}activityVisible+=10;await ensureActivityStories(all.slice(0,activityVisible));renderActivityTimeline()}
async function acknowledgeAttention(runId,attentionCode){
 try{await working("Acknowledging this finding","Recording your review decision and removing this exact finding from the active queue.",async function(){await post("/api/blackbox/acknowledge",{run_id:runId,confirm_run_id:runId,attention_code:attentionCode});await loadBlackbox();await inspectBlackbox(runId)})}
 catch(error){showError(error)}
}
function renderBlackbox(){
 var rows=blackboxArchiveRows,chain=blackboxIndex.chain||{},box=$("blackboxFlights");box.replaceChildren();
 renderActivityTimeline();
 var latest=currentRun(),currentPoints=latest?(latest.attention_points||[]):[],legacyUpgrade=currentPoints.some(function(p){return p.code==="legacy_evidence_contract"}),bridgeButton=$("bridgeRefresh");bridgeButton.style.display=legacyUpgrade?"inline-block":"none";bridgeButton.disabled=!bridgeRefreshStatus.available;text("bridgeRefresh",bridgeRefreshStatus.available?"Upgrade bridge & run test":"New bridge release required");bridgeButton.title=bridgeRefreshStatus.reason||"";
 $("blackboxIntegrity").className="integritychip"+(chain.valid===false?" bad":"");text("blackboxIntegrity",chain.valid===false?"✕ Audit history verification failed":"✓ Audit history verified");text("blackboxCount",number(rows.length)+" matching flight"+(rows.length===1?"":"s")+" · "+number(blackboxIndex.total_runs)+" recorded in total");
 if(!rows.length){box.appendChild(element("div","empty","No agent sessions match this search and date range. Change the dates or select All recorded."))}
 else{rows.forEach(function(row){var item=element("div","flight"),identity=element("div"),run=element("b","mono",row.run_id),session=element("div","small mono",(row.agent_id?"agent "+row.agent_id+" · ":"")+(row.session_id||"no session ID"));identity.append(run,session);
  var verdict=element("div","flightstat");verdict.append(element("b","",String(row.verdict||"unknown").replaceAll("_"," ")),element("small","","verdict"));var model=element("div","flightstat");model.append(element("b","",[row.provider,row.model].filter(Boolean).join(" / ")||"not observed"),element("small","","provider / model"));var context=element("div","flightstat");context.append(element("b","",String(row.context_disposition||"missing").replaceAll("_"," ")),element("small","","memory context"));var time=element("div","flightstat");time.append(element("b","",displayTime(row.ended_at)),element("small","","last observed"));var inspect=element("button","secondary","Inspect evidence");inspect.type="button";inspect.onclick=function(){inspectBlackbox(row.run_id)};item.append(identity,verdict,model,context,time,inspect);box.appendChild(item)})}
 renderAgentTopology();updateStatusBanner();renderProductVersions()
}
function updateStatusBanner(){
 var banner=$("statusBanner");if(!banner)return;
 var reviewCount=(reviewQueue.records||[]).length;
 var latest=currentRun(),latestPoints=latest?(latest.attention_points||[]):[],acknowledgedPoints=latest?(latest.acknowledged_attention_points||[]):[],attentionTotal=latestPoints.length;
 var chain=blackboxIndex.chain||{},chainValid=chain.valid!==false;
 var verification=(state&&state.verification)||{},verificationChecked=!!verification.report_sha256,verificationBad=verificationChecked&&verification.valid===false;
 var issues=reviewCount+attentionTotal+(chainValid?0:1)+(verificationBad?1:0);
 var headline=acknowledgedPoints.length?"Nothing pending — latest finding acknowledged":"Nothing needs your attention",detail=acknowledgedPoints.length?"Your review decision was recorded. The original finding and technical evidence remain in flight history.":"Approvals are clear, the latest agent activity is healthy, and the audit chain is verified."+(verification.ended_at?" Last checked "+displayTime(verification.ended_at)+".":""),action=$("statusAction");action.style.display="none";action.onclick=null;
 var pstate=providerState();
 if(pstate==="restore_required"){issues+=1;headline="Restore required before anything else";detail=((state&&state.takeover)||{}).recovery_message||"An interrupted switch left the integration in a recovery state. Restore the native memory before using or activating AtMem.";text("statusAction","Open restore");action.style.display="inline-block";action.onclick=function(){showView("decisions")}}
 else if(pstate==="unavailable"){issues+=1;headline="AtMem state is unavailable";detail=(state&&state.warning)||"The control state file is missing or invalid; the integration is fail-closed."}
 else if(reviewCount){headline=reviewCount+" memor"+(reviewCount===1?"y needs":"ies need")+" your decision";detail="These memories are quarantined and cannot reach the agent until you approve them. Open each one, then approve or permanently reject it.";text("statusAction","Review memories");action.style.display="inline-block";action.onclick=function(){showView("decisions")}}
 else if(attentionTotal){var point=latestPoints[0];headline=point.title;detail=point.detail||point.action;text("statusAction","Review");action.style.display="inline-block";action.onclick=function(){inspectBlackbox(latest.run_id)}}
 else if(!chainValid){headline="Audit history cannot be verified";detail="The evidence chain failed integrity verification. Do not rely on flight history until the broken chain is investigated.";text("statusAction","Open Audit Explorer");action.style.display="inline-block";action.onclick=function(){showView("auditExplorer")}}
 else if(verificationBad){headline="AtMem safety verification failed";detail="The latest control-plane safety check failed. Open the Evidence view and inspect the failed verification before switching or restoring memory.";text("statusAction","Open evidence");action.style.display="inline-block";action.onclick=function(){showView("evidence")}}
 banner.className="statusbanner"+(issues?" bad":" good");
 text("statusIcon",issues?"⚠":"✓");
 text("statusHeadline",headline);text("statusDetail",detail);
 renderDecisionsBadge()
}
function pendingDecisions(){
 var reviews=(reviewQueue.records||[]).length,restore=recovery()?1:0;
 return {reviews:reviews,restore:restore,total:reviews+restore}
}
function renderDecisionsBadge(){
 var badge=$("decisionsBadge"),count=pendingDecisions().total;
 if(count){badge.hidden=false;badge.textContent=String(count)}else{badge.hidden=true}
}
function localDateValue(date){var y=date.getFullYear(),m=String(date.getMonth()+1).padStart(2,"0"),d=String(date.getDate()).padStart(2,"0");return y+"-"+m+"-"+d}
function setFlightRange(range,runSearch){flightRange=range;var now=new Date(),start=new Date(now.getFullYear(),now.getMonth(),now.getDate()),end=new Date(start);if(range==="today"){end.setDate(end.getDate()+1)}else if(range==="yesterday"){end=new Date(start);start.setDate(start.getDate()-1)}else if(range==="7d"){end.setDate(end.getDate()+1);start.setDate(start.getDate()-6)}else{start=null;end=null}$("flightSince").value=start?localDateValue(start):"";if(end){var inclusive=new Date(end);inclusive.setDate(inclusive.getDate()-1);$("flightUntil").value=localDateValue(inclusive)}else $("flightUntil").value="";document.querySelectorAll("[data-flight-range]").forEach(function(button){button.classList.toggle("active",button.dataset.flightRange===range)});if(runSearch)filterBlackboxArchive()}
function flightDateBounds(){var since=$("flightSince").value?new Date($("flightSince").value+"T00:00:00"):null,until=$("flightUntil").value?new Date($("flightUntil").value+"T00:00:00"):null;if(until)until.setDate(until.getDate()+1);return{since:since,until:until}}
function flightMetadata(row){return [row.run_id,row.agent_id,row.subject_id,row.session_id,row.provider,row.model,row.verdict,row.coverage_status,row.context_disposition].filter(Boolean).join(" ").toLowerCase()}
function flightStoryText(story){return [story.request_text,story.response_text,story.provider,story.model,(story.tools||[]).join(" "),(story.websites||[]).join(" "),story.blocked_by,story.compromise_assessment,story.outcome_evidence].filter(Boolean).join(" ").toLowerCase()}
async function filterBlackboxArchive(){var box=$("blackboxFlights"),bounds=flightDateBounds(),status=$("flightStatus").value,query=$("flightQuery").value.trim().toLowerCase(),rows=(blackboxIndex.runs||[]).filter(function(row){var at=new Date(row.ended_at||row.started_at||0);if(bounds.since&&at<bounds.since)return false;if(bounds.until&&at>=bounds.until)return false;if(status==="healthy"&&(row.attention_points||[]).length)return false;if(status==="attention"&&!(row.attention_points||[]).length)return false;if(status==="failed"&&row.verdict==="completed_successfully")return false;return true});if(query){box.replaceChildren(loadingNode("Searching request, response, tools, websites and audit metadata…","empty"));var pending=rows.filter(function(row){return flightMetadata(row).indexOf(query)<0&&!blackboxStories[row.run_id]});for(var offset=0;offset<pending.length;offset+=8){await Promise.all(pending.slice(offset,offset+8).map(async function(row){try{blackboxStories[row.run_id]=await get("/api/blackbox/story?run_id="+encodeURIComponent(row.run_id))}catch(_){blackboxStories[row.run_id]={}}}))}rows=rows.filter(function(row){return flightMetadata(row).indexOf(query)>=0||flightStoryText(blackboxStories[row.run_id]||{}).indexOf(query)>=0})}blackboxArchiveRows=rows;renderBlackbox()}
async function loadBlackbox(){try{blackboxIndex=await get("/api/blackbox/runs?limit=500");await Promise.all((blackboxIndex.runs||[]).slice(0,10).map(async function(row){try{blackboxStories[row.run_id]=await get("/api/blackbox/story?run_id="+encodeURIComponent(row.run_id))}catch(_){blackboxStories[row.run_id]={}}}));try{bridgeRefreshStatus=await get("/api/bridge/status")}catch(_){bridgeRefreshStatus={available:false,reason:"Bridge status is unavailable."}}renderProductVersions();if(!$("flightSince").value&&!$("flightUntil").value)setFlightRange("7d",false);await filterBlackboxArchive()}catch(error){showError(error)}}
async function inspectBlackbox(runId){
 clearError();document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");$("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Session evidence");text("auditorTitle","What this agent run did");$("auditorId").replaceChildren(evidenceChip("run",runId));$("auditorBody").replaceChildren(loadingNode("Building the session story…","empty"));
 try{var values=await Promise.all([get("/api/blackbox/flight?run_id="+encodeURIComponent(runId)),get("/api/blackbox/story?run_id="+encodeURIComponent(runId)).catch(function(){return{}})]),report=values[0],story=values[1]||{},body=$("auditorBody"),latest=currentRun();body.replaceChildren();var matrix=report.coverage_matrix||{},overall=matrix.overall_status||"unknown",ok=overall==="covered",operatorReview=report.operator_review||{},reportPoints=operatorReview.active_attention_points||report.attention_points||[],acknowledgedPoints=operatorReview.acknowledged_attention_points||[],historical=!!(latest&&latest.run_id!==runId),tools=report.tools||{},coverage=report.coverage||{},components=matrix.components||{},context=report.context||{};
  var decision=element("section","historicalnote"),decisionTitle,decisionCopy;
  if(historical){decisionTitle="Past activity — not a current alert";decisionCopy=reportPoints.length?"This flight recorded: "+reportPoints[0].title+". A later flight is healthy, so no action is required now. This record remains only for audit history.":"This is an older audit record. It does not affect the current healthy status."}
  else if(reportPoints.length){decision.className="historicalnote attentionitem high";decisionTitle=reportPoints[0].title;decisionCopy=reportPoints[0].detail}
  else if(acknowledgedPoints.length){var acknowledged=acknowledgedPoints[0].acknowledgement||{};decisionTitle="Reviewed — no action pending";decisionCopy="Acknowledged "+displayTime(acknowledged.created_at)+" by "+(acknowledged.actor||"an operator")+". The original finding remains in audit history."}
  else{decisionTitle="Healthy — no action needed";decisionCopy="This is the latest activity. It completed normally and the required audit evidence is present."}
  decision.append(element("b","",decisionTitle),element("p","",decisionCopy));body.appendChild(decision);
  var storyCard=element("section","card"),storyFlow=element("div","storyflow"),requestText=story.request_text||"Request text was not retained by this runtime adapter.",responseText=story.response_text||"No final response text was retained.",receivedLabel=state&&state.host==="openclaw"?"OpenClaw received this request":"The agent runtime received this request";storyCard.append(element("h2","","What happened"),element("p","sub",report.agent_id?"Persistent agent: "+report.agent_id:"Persistent agent identity was not recorded for this flight."));storyFlow.appendChild(storyStep("1",receivedLabel,requestText));
  var memoryBox=element("div");if((story.memories||[]).length){(story.memories||[]).forEach(function(memory){var button=element("button","memoryline",memory.content||"Memory text unavailable"),id=element("small","mono",memory.record_id);button.type="button";button.appendChild(id);button.onclick=function(){inspectRecord(memory.record_id,function(){inspectBlackbox(runId)})};memoryBox.appendChild(button)})}else memoryBox.appendChild(element("p","storytext",Number(story.memory_count||0)?"Memory IDs were recorded, but their text is no longer available in the configured memory source.":"No memory was added to this request."));storyFlow.appendChild(storyStep("2","AtMem added this memory before the model ran",memoryBox));
  storyFlow.appendChild(storyStep("3","Model",[story.provider,story.model].filter(Boolean).join(" / ")||"Not recorded"));storyFlow.appendChild(storyStep("4","Response",responseText));storyFlow.appendChild(storyStep("5","Outcome",story.blocked_by||((story.tools||[]).length?"Tools: "+story.tools.join(", "):story.success?"Completed successfully.":"No completed result was recorded.")));storyCard.appendChild(storyFlow);body.appendChild(storyCard);
  var impact=element("section","card"),impactFlow=element("div","storyflow"),usage=story.usage||{},externalBox=element("div");if(!(story.websites||[]).length&&!(story.tools||[]).length)externalBox.appendChild(element("p","storytext","No website was contacted and no external tool was called."));(story.websites||[]).forEach(function(url){var link=element("a","memoryline",url);link.href=url;link.target="_blank";link.rel="noopener noreferrer";externalBox.appendChild(link)});(story.tools||[]).forEach(function(name){var button=element("button","memoryline","Tool: "+name);button.type="button";button.onclick=function(){focusFlightEvidence(name)};externalBox.appendChild(button)});var usageText=usage.total_tokens!=null?number(usage.total_tokens)+" tokens ("+number(usage.input_tokens)+" input, "+number(usage.output_tokens)+" output).":"Token usage was not recorded.";usageText+=" "+(usage.recorded_cost_usd!=null?"Recorded model cost: $"+Number(usage.recorded_cost_usd).toFixed(4)+" USD.":"Monetary cost was not recorded, so the dashboard cannot honestly show a dollar amount.");impact.append(element("h2","","Impact, cost and risk"),element("p","sub","What left the machine, what could have changed, and what was or was not proven."));impactFlow.appendChild(storyStep("6","External systems and websites",externalBox));impactFlow.appendChild(storyStep("7","Tokens and cost",usageText));impactFlow.appendChild(storyStep("8","Data exposure and risk",(story.risks||[]).length?(story.risks||[]).join("\n"):"No additional risk was identified from the retained evidence."));impactFlow.appendChild(storyStep("9","What blocked or failed",story.blocked_by||"Nothing blocked this flight and no failure was recorded."));impactFlow.appendChild(storyStep("10","Compromise and outcome proof",(story.compromise_assessment||"No compromise assessment is available.")+"\n"+(story.outcome_evidence||"No independent outcome evidence is available.")));impact.appendChild(impactFlow);body.appendChild(impact);
  if(!historical&&reportPoints.length){var actionCard=element("section","card"),actions=element("div","reviewactions"),inspect=element("button","secondary","Technical details"),ack=element("button","primary","Acknowledge"),point=reportPoints[0],toolEvidence=[].concat(tools.missing_completions||[],tools.orphan_completions||[],tools.conflicting_requests||[],tools.conflicting_completions||[])[0];actionCard.append(element("h2","","Next action"),element("p","sub",point.action));inspect.type="button";inspect.onclick=function(){focusFlightEvidence(toolEvidence||point.code)};ack.type="button";ack.onclick=function(){acknowledgeAttention(runId,point.code)};actions.append(inspect,ack);actionCard.appendChild(actions);body.appendChild(actionCard)}
  if(acknowledgedPoints.length){var reviewedCard=element("section","card"),reviewedList=element("div","attentionlist");reviewedCard.append(element("h2","","Acknowledged findings"),element("p","sub","These no longer require action. Their original evidence has not been changed or deleted."));acknowledgedPoints.forEach(function(point){var acknowledgement=point.acknowledgement||{},item=element("div","attentionitem"),copy=element("div","attentioncopy");copy.append(element("b","",point.title),element("p","",point.detail),element("p","small","Acknowledged "+displayTime(acknowledgement.created_at)+" by "+(acknowledgement.actor||"operator")));item.appendChild(copy);reviewedList.appendChild(item)});reviewedCard.appendChild(reviewedList);body.appendChild(reviewedCard)}
  var technical=element("details","technical"),technicalSummary=element("summary","","Show technical evidence, IDs and hashes");technical.appendChild(technicalSummary);
  var technicalOverview=element("section","card"),technicalGrid=element("div","evidencegrid");technicalOverview.append(element("h2","","Coverage checks"));technicalGrid.append(evidence("Overall coverage",overall.toUpperCase(),false),evidence("Integrity",components.integrity||"missing",false),evidence("Lifecycle",components.lifecycle||"missing",false),evidence("Context",components.context||"missing",false),evidence("Model",components.model||"missing",false),evidence("Tools",components.tools||"missing",false),evidence("Response",components.response||"missing",false),evidence("Events",String(report.events||0),true),evidence("Tool closure",String(tools.completed||0)+" / "+String(tools.requested||0),true),evidence("Response bound",coverage.response_digest_bound?"yes":"no",false));technicalOverview.appendChild(technicalGrid);technical.appendChild(technicalOverview);
  var correlation=report.correlation||{},correlationCard=element("section","card"),correlationGrid=element("div","evidencegrid");correlationCard.append(element("h2","","Linked evidence IDs"),element("p","sub","Select an ID to jump to the exact event that contains it."));[["Agent ID",[report.agent_id]],["Memory subject",[report.subject_id]],["Run ID",[report.run_id]],["Session IDs",correlation.session_ids],["Turn IDs",correlation.turn_ids],["Retrieval IDs",correlation.retrieval_ids],["Context event IDs",correlation.context_event_ids],["Context receipt IDs",correlation.context_receipt_ids],["Outcome IDs",correlation.outcome_ids]].forEach(function(pair){var box=element("div","evidence"),label=element("span","",pair[0]),chips=element("div","evidencechips");(pair[1]||[]).filter(Boolean).forEach(function(value){chips.appendChild(evidenceChip("open",value))});if(!chips.childNodes.length)chips.appendChild(element("b","","not recorded"));box.append(label,chips);correlationGrid.appendChild(box)});correlationCard.appendChild(correlationGrid);technical.appendChild(correlationCard);
  var timelineCard=element("section","card"),timeline=element("div","timeline");timelineCard.append(element("h2","","Evidence timeline"),element("p","sub","Open any step to see its exact IDs, hashes and retained payload."));(report.timeline||[]).forEach(function(event){var item=element("details","event");item.dataset.evidence=JSON.stringify(event);var summary=element("summary","",flightEventTitle(event.event_type)+" — "+displayTime(event.recorded_at)),chips=element("div","evidencechips");[["run",event.run_id],["turn",event.turn_id],["retrieval",event.retrieval_id],["context",event.context_event_id],["receipt",event.context_receipt_id],["outcome",event.outcome_id],["entry hash",event.entry_sha256]].forEach(function(pair){if(pair[1])chips.appendChild(evidenceChip(pair[0],pair[1]))});item.append(summary,element("p","",blackboxEventDetail(event)),chips,element("pre","eventpayload mono",JSON.stringify(event.payload||{},null,2)));timeline.appendChild(item)});timelineCard.appendChild(timeline);technical.appendChild(timelineCard);
  var boundary=element("section","card");boundary.append(element("h2","","What this proves"),element("p","",report.claim_boundary||""));technical.appendChild(boundary);var downloads=element("section","card"),links=element("div","downloads");downloads.append(element("h2","","Export evidence"));[["JSON report","json"],["Text report","text"]].forEach(function(pair){var a=element("a","secondary",pair[0]);a.href="/api/blackbox/export?run_id="+encodeURIComponent(runId)+"&format="+pair[1];links.appendChild(a)});downloads.appendChild(links);technical.appendChild(downloads);body.appendChild(technical)
 }catch(error){$("auditorBody").replaceChildren(element("div","notice show",error.message||String(error)))}
}
function isoInput(value){if(!value)return "";var d=new Date(value);return Number.isNaN(d.getTime())?"":new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
function auditFilters(){
 return {query:$("auditQuery").value.trim(),event_type:$("auditType").value,actor:$("auditActor").value,
  session_id:$("auditSession").value.trim(),record_id:$("auditRecord").value.trim(),
  since:$("auditSince").value?new Date($("auditSince").value).toISOString():"",
  until:$("auditUntil").value?new Date($("auditUntil").value).toISOString():"",direction:$("auditDirection").value}
}
function auditQueryString(filters,extra){var p=new URLSearchParams();Object.keys(filters).forEach(function(k){if(filters[k])p.set(k,filters[k])});Object.keys(extra||{}).forEach(function(k){if(extra[k]!=null&&extra[k]!=="")p.set(k,extra[k])});return p.toString()}
function pivotAudit(field,value){if(!value)return;if(field==="record")$("auditRecord").value=value;if(field==="session")$("auditSession").value=value;if(field==="actor")$("auditActor").value=value;if(field==="type")$("auditType").value=value;auditSearch(true)}
function auditFacetOptions(facets){
 if(!facets)return;var type=$("auditType"),actor=$("auditActor"),selectedType=type.value,selectedActor=actor.value;
 type.replaceChildren(new Option("All event types",""));(facets.event_types||[]).forEach(function(row){type.appendChild(new Option(row.value+" ("+number(row.count)+")",row.value))});type.value=selectedType;
 actor.replaceChildren(new Option("All actors",""));(facets.actors||[]).forEach(function(row){actor.appendChild(new Option(row.value+" ("+number(row.count)+")",row.value))});actor.value=selectedActor;auditFacetsLoaded=true
}
function renderHistogram(rows){var box=$("auditHistogram");box.replaceChildren();if(!rows||!rows.length){box.appendChild(element("div","empty","No events in this time range."));return}var max=Math.max.apply(null,rows.map(function(r){return Number(r.count||0)}));rows.forEach(function(row){var bar=element("button","histbar");bar.type="button";bar.style.height=Math.max(4,Math.round(Number(row.count||0)/max*78))+"px";bar.title=row.bucket+" · "+number(row.count)+" events";bar.setAttribute("aria-label",bar.title);bar.onclick=function(){var start=new Date(row.bucket+(row.bucket.length===13?":00:00Z":"T00:00:00Z")),end=new Date(start.getTime()+(row.bucket.length===13?3600000:86400000)-1);$("auditSince").value=isoInput(start);$("auditUntil").value=isoInput(end);auditSearch(true)};box.appendChild(bar)})}
function auditSummary(row){var p=row.payload||{};if(row.event_type==="memory.recall")return number(p.returned_ids&&p.returned_ids.length)+" returned / "+number(p.candidate_count)+" candidates";if(row.event_type==="memory.context_injected")return number(p.record_ids&&p.record_ids.length)+" memories injected";if(row.event_type==="agent.response_after_memory")return "response "+shortDigest(p.response_sha256);if(p.operation)return String(p.operation);return Object.keys(p).slice(0,3).join(", ")||"Open evidence"}
function inspectAuditEvent(row){
 document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");$("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Evidence event");text("auditorTitle",row.event_type);text("auditorId",row.event_id);
 var body=$("auditorBody");body.replaceChildren();var integrity=element("p","integrity","✓ Event is bound to the verified chain");body.appendChild(integrity);
 var overview=element("section","card"),grid=element("div","evidencegrid");overview.append(element("h2","","Event details"),element("p","sub","Pivot from any linked identifier to narrow the global investigation."));grid.append(evidence("Sequence",String(row.sequence),true),evidence("Time",displayTime(row.created_at),false),evidence("Actor",row.actor,false),evidence("Event ID",row.event_id,true),evidence("Previous hash",row.prev_hash,true),evidence("Event hash",row.event_hash,true));overview.appendChild(grid);body.appendChild(overview);
 var pivots=element("section","card"),links=element("div","downloads"),payloadValue=row.payload||{};pivots.append(element("h2","","Follow linked evidence"));[["record",row.record_id,"Record"],["session",row.session_id,"Session"],["actor",row.actor,"Actor"],["type",row.event_type,"Event type"]].forEach(function(v){if(!v[1])return;var b=element("button","secondary",v[2]+": "+v[1]);b.onclick=function(){closeAuditor();pivotAudit(v[0],v[1])};links.appendChild(b)});
 var linkedRecords=[];["record_id","record_ids","returned_ids","injected_record_ids","purged_record_ids","supersedes"].forEach(function(key){var value=payloadValue[key];(Array.isArray(value)?value:[value]).filter(Boolean).forEach(function(id){if(String(id).indexOf("rec_")===0&&linkedRecords.indexOf(String(id))<0)linkedRecords.push(String(id))})});linkedRecords.forEach(function(id){var b=element("button","secondary","Memory: "+id);b.onclick=function(){inspectRecord(id)};links.appendChild(b)});
 ["retrieval_id","run_id","outcome_id","transaction_id","operation_id","artifact_id","observation_id"].forEach(function(key){if(!payloadValue[key])return;var id=String(payloadValue[key]),b=element("button","secondary",key.replace("_id","")+": "+id);b.onclick=function(){closeAuditor();$("auditQuery").value=id;auditSearch(true)};links.appendChild(b)});if(row.record_id){var inspect=element("button","primary","Open record history");inspect.onclick=function(){inspectRecord(row.record_id)};links.appendChild(inspect)}pivots.appendChild(links);body.appendChild(pivots);
 var payload=element("section","card");payload.append(element("h2","","Canonical payload"),element("p","sub","The exact structured evidence covered by the event hash."),element("pre","eventpayload mono",JSON.stringify(row.payload||{},null,2)));body.appendChild(payload)
}
function renderAudit(report){
 auditLast=report;auditFacetOptions(report.facets);renderHistogram(report.histogram);var rows=$("auditRows");rows.replaceChildren();
 if(!(report.events||[]).length){var tr=element("tr"),td=element("td","empty","No audit events match these filters.");td.colSpan=7;tr.appendChild(td);rows.appendChild(tr)}
 (report.events||[]).forEach(function(row){var tr=element("tr"),time=element("td","",displayTime(row.created_at)),event=element("td"),eventBtn=element("button","eventbutton",row.event_type),summary=element("div","small",auditSummary(row));eventBtn.onclick=function(){inspectAuditEvent(row)};event.append(eventBtn,summary);
  var actor=element("td"),actorBtn=element("button","pivot",row.actor);actorBtn.onclick=function(){pivotAudit("actor",row.actor)};actor.appendChild(actorBtn);
  var record=element("td");if(row.record_id){var recordBtn=element("button","pivot mono",row.record_id);recordBtn.onclick=function(){inspectRecord(row.record_id)};record.appendChild(recordBtn)}else record.textContent="—";
  var session=element("td");if(row.session_id){var sessionBtn=element("button","pivot mono",row.session_id);sessionBtn.onclick=function(){pivotAudit("session",row.session_id)};session.appendChild(sessionBtn)}else session.textContent="—";if(row.turn_id)session.appendChild(element("div","small mono",row.turn_id));
  tr.append(time,event,actor,record,session,element("td","mono",row.event_id),element("td","integrity","verified"));rows.appendChild(tr)
 });
 $("auditIntegrity").className="integritychip"+(report.audit_chain_valid?"":" bad");text("auditIntegrity",report.audit_chain_valid?"✓ Chain verified":"✕ Verification failed");text("auditCount",number(report.matched_total)+" matching · "+number((report.events||[]).length)+" on this page");text("auditDigest",shortDigest(report.result_digest));text("auditPage","Page "+(auditPageIndex+1));$("auditBack").disabled=auditPageIndex===0;$("auditNext").disabled=!report.has_more;
 document.querySelectorAll(".auditexport").forEach(function(a){a.href="/api/memory/audit-export?"+auditQueryString(auditFilters(),{format:a.dataset.format})})
}
async function loadAudit(includeFacets){
 clearError();$("auditRows").replaceChildren(tableLoading("Loading audit evidence…"));try{var extra={limit:$("auditLimit").value,include_facets:includeFacets?1:0},cursor=auditCursors[auditPageIndex];if(cursor!=null)extra.cursor=cursor;var report=await get("/api/memory/audit?"+auditQueryString(auditFilters(),extra));renderAudit(report)}catch(error){showError(error)}
}
function auditSearch(reset){if(reset){auditCursors=[null];auditPageIndex=0}loadAudit(!auditFacetsLoaded||reset)}
function savedViews(){try{return JSON.parse(localStorage.getItem("atmem-audit-views")||"[]")}catch(_){return []}}
function renderSavedViews(){var select=$("auditSaved");select.replaceChildren(new Option("Saved views…",""));savedViews().forEach(function(view,index){select.appendChild(new Option(view.name,String(index)))})}
function applyAuditFilters(f){$("auditQuery").value=f.query||"";$("auditType").value=f.event_type||"";$("auditActor").value=f.actor||"";$("auditSession").value=f.session_id||"";$("auditRecord").value=f.record_id||"";$("auditSince").value=isoInput(f.since);$("auditUntil").value=isoInput(f.until);$("auditDirection").value=f.direction||"desc"}
function closeAuditor(){$("auditorBackdrop").classList.remove("show");$("auditorBackdrop").setAttribute("aria-hidden","true");document.body.style.overflow=""}
function recordSessionName(sessionId){var value=String(sessionId||"");if(value.indexOf(":investigator")>=0)return "AtMem dashboard search";if(value.indexOf("atmem-bridge-self-test")>=0)return "OpenClaw bridge self-test";if(value.indexOf("dashboard")>=0)return "Dashboard memory check";return value?"Agent session":"Session name was not recorded"}
function recordEvidenceChip(label,value){var button=element("button","evidencechip",label+": "+value);button.type="button";button.title="Find this value in the complete audit history";button.onclick=function(){closeAuditor();showView("evidence");$("auditQuery").value=String(value);auditSearch(true);$("auditQuery").scrollIntoView({behavior:"smooth",block:"center"})};return button}
async function inspectRecord(recordId,backAction){
 clearError();document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");
 $("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Memory record history");text("auditorTitle","Memory record");text("auditorId",recordId);$("auditorBody").replaceChildren(loadingNode("Verifying the complete record history…","empty"));
 try{
  var report=await get("/api/memory/record?record_id="+encodeURIComponent(recordId)),record=report.record||{},p=report.provenance||{},life=report.lifecycle||{},deliveries=report.deliveries||[],timeline=report.timeline||[],body=$("auditorBody");body.replaceChildren();
  if(backAction){var back=element("button","secondary backlink","← Back to flight");back.type="button";back.onclick=backAction;body.appendChild(back)}
  var integrity=element("p","integrity"+(report.audit_chain_valid?"":" bad"),report.audit_chain_valid?"✓ Audit chain verified":"✕ Audit chain verification failed");body.appendChild(integrity);
  var memoryCard=element("section","card");memoryCard.append(element("h2","","Stored memory"),element("p","recordcontent",record.content||"The memory content was purged; retained audit evidence is shown below."));body.appendChild(memoryCard);
  var considered=deliveries.length,returned=deliveries.filter(function(d){return d.returned}).length,injected=deliveries.filter(function(d){return d.context_injected_at}).length,bound=deliveries.filter(function(d){return d.response_sha256}).length;
  var investigatorReturns=deliveries.filter(function(d){return String(d.session_id||"").indexOf(":investigator")>=0&&d.returned}).length,nonInvestigatorReturns=returned-investigatorReturns,usageCard=element("section","card"),usageSummary=injected?"This memory was proven to reach the model in "+injected+" recorded "+(injected===1?"run":"runs")+".":nonInvestigatorReturns?"An agent memory search returned this memory, but the retained evidence does not prove it reached the model.":investigatorReturns?"This memory appeared in a read-only dashboard search. No agent or model was involved.":considered?"This memory was considered by search, but was not used.":"This memory has not appeared in a recorded memory search.";usageCard.append(element("h2","","How this memory was used"),element("p","sub",usageSummary));
  if(!deliveries.length)usageCard.appendChild(element("div","empty","No recorded agent run searched for this memory."));
  deliveries.forEach(function(d){var used=!!d.context_injected_at,wasReturned=!!d.returned,isInvestigator=String(d.session_id||"").indexOf(":investigator")>=0,title=isInvestigator?(wasReturned?"Shown in dashboard search — no model involved":"Considered by dashboard search — not shown"):used?"Used in a model request":wasReturned?"Returned by agent memory search; injection not proven":"Considered but not used",explanation=isInvestigator?(wasReturned?"The AtMem dashboard displayed this memory as a search result. This was a read-only investigation: it did not run an agent, call a model, or inject the memory into model context.":"The AtMem dashboard evaluated this memory as a possible search result but did not display it. No agent or model was involved."):used?"AtMem selected this memory and added it to the context sent to the model.":wasReturned?"AtMem returned this memory from an agent memory search, but there is no retained context event proving it was sent to the model.":"AtMem evaluated this memory as a possible match, but did not return it or add it to the model context.";if(used&&d.response_sha256)explanation+=" A model response was recorded afterward.";var item=element("details","delivery"+(used?" used":wasReturned?" returned":"")),summary=element("summary","",title+" — "+displayTime(d.recalled_at)),inside=element("div","deliverybody"),chips=element("div","evidencechips");inside.append(element("p","",explanation),element("p","small",recordSessionName(d.session_id)));[["retrieval",d.retrieval_id],["session",d.session_id],["context event",d.context_event_id],["response event",d.response_event_id],["response fingerprint",d.response_sha256]].forEach(function(pair){if(pair[1])chips.appendChild(recordEvidenceChip(pair[0],pair[1]))});inside.append(chips,element("p","small","Technical search position: rank "+(d.rank==null?"not recorded":d.rank)+"; similarity score "+(d.score==null?"not recorded":d.score)+". These values explain retrieval ordering; they do not mean the memory reached the model."));item.append(summary,inside);usageCard.appendChild(item)});body.appendChild(usageCard);
  var technical=element("details","technical");technical.appendChild(element("summary","","Show technical record evidence, IDs and hashes"));
  var chain=element("div","chain");var delivered=deliveries.some(function(d){return !!d.context_injected_at}),responded=deliveries.some(function(d){return !!d.response_sha256});
  chain.append(chainStep("Source",!!p.source_message_sha256,shortDigest(p.source_message_sha256)),chainStep("Interpret",!!p.interpreting_model,p.interpreting_model||"native import"),chainStep("Admit",!!life.created_at,displayTime(life.created_at)),chainStep("Recall",deliveries.length>0,deliveries.length+" attempt"+(deliveries.length===1?"":"s")),chainStep("Inject",delivered,delivered?"context receipt":"not recorded"),chainStep("Reply",responded,responded?"fingerprint recorded":"not recorded"));
  var chainCard=element("section","card");chainCard.append(element("h2","","Evidence chain"),element("p","sub","Source → interpretation → admission → recall → context injection → agent response"),chain);technical.appendChild(chainCard);
  var prov=element("section","card"),provGrid=element("div","evidencegrid");prov.append(element("h2","","Source and interpretation"),element("p","sub","Digests prove identity without exposing the original message."));
  provGrid.append(evidence("Source-message SHA-256",p.source_message_sha256,true),evidence("Interpreting model",p.interpreting_model||(state&&state.host==="openclaw"?"Native OpenClaw import":"Authenticated host capture"),false),evidence("Source binding",p.source_binding||p.interpretation_assurance,false),evidence("Native source",p.native_path||"Not a native-file import",true),evidence("Episode",p.episode_id,true),evidence("Memory plane",p.plane,false));prov.appendChild(provGrid);technical.appendChild(prov);
  var lifecycle=element("section","card"),lifeGrid=element("div","evidencegrid");lifecycle.append(element("h2","","Record lifecycle"),element("p","sub","Canonical state changes preserved in chronological audit evidence."));lifeGrid.append(evidence("Status",report.status,false),evidence("Created",displayTime(life.created_at),false),evidence("Superseded",life.superseded_at?displayTime(life.superseded_at):"Not superseded",false),evidence("Deleted",life.deleted_at?displayTime(life.deleted_at):"Not deleted",false));lifecycle.appendChild(lifeGrid);technical.appendChild(lifecycle);
  var deliveryCard=element("section","card"),deliveryStats=element("div","evidencegrid");deliveryCard.append(element("h2","","Retrieval totals"),element("p","sub","Technical counts across every recorded search involving this memory."));deliveryStats.append(evidence("Considered",String(considered),true),evidence("Returned",String(returned),true),evidence("Injected",String(injected),true),evidence("Response-bound",String(bound),true));deliveryCard.appendChild(deliveryStats);technical.appendChild(deliveryCard);
  var timeCard=element("section","card"),timeBox=element("div","timeline");timeCard.append(element("h2","","Complete chronological history"),element("p","sub",timeline.length+" linked evidence event"+(timeline.length===1?"":"s")+"."));
  timeline.forEach(function(e){var item=element("div","event");item.append(element("b","",e.title||e.type),element("p","",e.detail||""),element("div","small mono",displayTime(e.at)+" · "+(e.actor||"unknown actor")+" · "+(e.event_id||"no evidence ID")+(e.session_id?" · "+e.session_id:"")));timeBox.appendChild(item)});if(!timeline.length)timeBox.appendChild(element("div","empty","No linked events were retained."));timeCard.appendChild(timeBox);technical.appendChild(timeCard);
  var downloads=element("section","card"),links=element("div","downloads");downloads.append(element("h2","","Export evidence"),element("p","sub","Download a portable investigation report. A deletion receipt appears only after a verified purge."));
  [["JSON report","json"],["Text report","text"]].forEach(function(pair){var a=element("a","secondary",pair[0]);a.href="/api/memory/record-report?record_id="+encodeURIComponent(recordId)+"&format="+pair[1];links.appendChild(a)});
  if(report.deletion_receipt){var receipt=element("a","secondary","Deletion receipt");receipt.href="/api/memory/deletion-receipt?record_id="+encodeURIComponent(recordId);links.appendChild(receipt)}downloads.appendChild(links);technical.appendChild(downloads);body.appendChild(technical)
 }catch(error){$("auditorBody").replaceChildren(element("div","notice show",error.message||String(error)))}
}
function renderSources(mirror){
 var box=$("sources");box.replaceChildren();var rows=Array.isArray(mirror.sources)?mirror.sources:[];
 if(!rows.length){text("sourceSummary",state&&state.host==="openclaw"?"No verified native-memory source files were found.":"Generic capture is event-driven; registered workspaces and the canonical database are the source of truth.");box.appendChild(element("div","empty",state&&state.host==="openclaw"?"No mirrored source files were found.":"Memories arrive from authenticated runtime events, not private host files."));return}
 rows.forEach(function(row){
  var item=element("div","source"),head=element("div","sourcehead"),name=element("b","",row.relative_path||"unknown");
  var bytes=element("span","small mono",number(row.bytes)+" bytes"),plane=element("span","plane",row.plane||"memory");
  head.append(name,bytes,plane);item.append(head);
  item.appendChild(element("div","digest mono","SHA-256  "+(row.sha256||"not recorded")));
  box.appendChild(item)
 });
 text("sourceSummary",rows.length+" verified source file"+(rows.length===1?"":"s")+" from "+(mirror.workspace||"the OpenClaw workspace")+".")
}
function renderReviews(){
 var box=$("reviews"),rows=Array.isArray(reviewQueue.records)?reviewQueue.records:[];box.replaceChildren();text("reviewCount",rows.length);
 if(typeof updateStatusBanner==="function")updateStatusBanner();
 if(!rows.length){box.appendChild(element("div","empty","Nothing is waiting for approval."));return}
 rows.forEach(function(row){
  var item=element("div","reviewitem"),content=element("p","reviewcontent",row.content||"Content unavailable"),meta=element("div","reviewmeta");
  meta.append(element("span","pill",row.media&&row.media.modality?row.media.modality:(row.scope||"observation")),element("span","small",displayTime(row.created_at)));
  var inspect=element("button","recordlink mono",row.record_id);inspect.type="button";inspect.onclick=function(){inspectRecord(row.record_id)};meta.appendChild(inspect);
  if(row.media&&row.media.extractor){var extractor=row.media.extractor;meta.append(element("span","small",[extractor.provider,extractor.model,extractor.version].filter(Boolean).join(" / ")||"extractor recorded"))}
  var isImage=Boolean(row.media&&row.media.modality==="image"),actions=element("div","reviewactions"),approve=element("button","primary approve",isImage?"Approve description as memory":"Approve as memory"),reject=element("button","reject","Reject and purge");
  approve.type="button";reject.type="button";approve.onclick=function(){reviewRecord(row,"approve")};reject.onclick=function(){reviewRecord(row,"reject")};
  item.appendChild(meta);
  if(isImage){
   var compare=element("div","reviewcompare"),source=element("section","reviewpane"),remembered=element("section","reviewpane"),image=element("img","reviewimage"),status=element("p","previewstatus","Verifying the exact source image…");
   source.append(element("h3","","Source image being reviewed"));image.alt="Source image bound to this observation";image.src=row.media.preview_url||"";approve.disabled=true;
   image.onload=function(){status.textContent="Source bytes verified against SHA-256 "+String(row.media.media_sha256||"").slice(0,16)+"…";status.className="previewstatus";approve.disabled=false};
   image.onerror=function(){image.remove();status.textContent="The exact source image is unavailable or no longer matches its recorded digest. Approval is disabled.";status.className="previewstatus bad";approve.disabled=true};
   source.append(image,status);remembered.append(element("h3","","What AtMem will remember"),content,element("p","reviewboundary","Future agents receive this text description, not the image pixels. The original image remains controlled by the runtime adapter."));
   compare.append(source,remembered);item.appendChild(compare)
  }else item.appendChild(content);
  actions.append(approve,reject);item.appendChild(actions);box.appendChild(item)
 })
}
async function reviewRecord(row,decision){
 var approving=decision==="approve",verb=approving?"approve":"reject and permanently purge";
 var subject=row.media&&row.media.modality==="image"?"this exact text description as recallable memory":"this exact memory";
 if(!confirm("Do you want to "+verb+" "+subject+"?\n\n"+(row.content||"")))return;
 try{await working(approving?"Approving memory":"Rejecting memory",approving?"Activating the exact reviewed record and writing an audit event.":"Purging the exact reviewed record and verifying derived-index cleanup.",async function(){await post("/api/memory/review",{record_id:row.record_id,confirm_record_id:row.record_id,decision:decision});await reload()})}
 catch(error){showError(error)}
}
async function refreshReviews(silent){
 try{reviewQueue=await get("/api/memory/reviews");renderReviews()}catch(error){if(!silent)showError(error)}
}
function addCheck(label,ok,detail){
 var row=element("div","check"+(ok?"":" pending")),icon=element("i","",ok?"✓":"!"),body=element("div","",label);
 if(detail)body.appendChild(element("span","", " — "+detail));row.append(icon,body);$("checks").appendChild(row)
}
function render(){
 if(!state)return;var mirror=state.mirror||{},takeover=state.takeover||{},isActive=active(),needsRecovery=recovery(),readiness=state.readiness||{},isOpenClaw=state.host==="openclaw",hostName=isOpenClaw?"OpenClaw":(state.host||"Generic runtime");
 text("adapterLabel",isOpenClaw?"OpenClaw adapter":"Generic runtime adapter");
 var pstate=providerState();
 var stateLabels={active:"AtMem active",ready:"Ready to activate",shadow:"Shadow mode",off:"Capture off",restore_required:"Restore required",unavailable:"State unavailable"};
 $("stateChip").className="state"+(isActive?" active":"");
 text("stateChip",stateLabels[pstate]||"Shadow mode");
 text("eyebrow",isActive?"Current memory provider":needsRecovery?"Interrupted switch detected":pstate==="off"?"Capture stopped":pstate==="unavailable"?"State unavailable":"Safe observation only");
 text("title",isActive?"AtMem memory is active for "+hostName:needsRecovery?"Restore "+hostName+" before activating":pstate==="off"?"AtMem capture is off for "+hostName:pstate==="unavailable"?"AtMem state is unavailable":"AtMem is observing "+hostName+" in shadow mode");
 text("summary",isActive
  ?"AtMem now serves bounded, governed memory. Flight evidence and review decisions continue to be recorded."
  :needsRecovery
  ?(takeover.recovery_message||"AtMem preserved the switch evidence and must verify restoration before another activation.")
  :pstate==="off"
  ?"AtMem is not capturing or influencing "+hostName+" right now. Native memory remains authoritative."
  :pstate==="unavailable"
  ?(state.warning||"The control state file is missing or invalid; the integration is fail-closed.")
  :(isOpenClaw?"AtMem mirrors and verifies existing memory without changing what OpenClaw uses.":"AtMem records candidate memory and flight evidence without adding anything to model context."));
 text("sourceCount",isOpenClaw?number(mirror.source_count):number(((state.agent_topology||{}).workspaces||[]).length));text("sourceCountLabel",isOpenClaw?"mirrored files":"workspace scopes");text("recordCount",number(mirror.record_count));text("sourceBytes",isOpenClaw?number(mirror.source_bytes):number(mirror.candidate_count));text("sourceBytesLabel",isOpenClaw?"source bytes preserved":"memories to review");text("sourceTitle",isOpenClaw?"Exactly what is mirrored":"How memory enters AtMem");
 text("verified",mirror.audit_verified?"PASSED":"CHECK");
 text("switchBtn",isActive||needsRecovery?(isOpenClaw?"Restore OpenClaw":"Return to shadow"):"Activate AtMem");
 $("switchBtn").classList.toggle("danger",isActive||needsRecovery);$("switchBtn").setAttribute("aria-label",isActive||needsRecovery?(isOpenClaw?"Restore OpenClaw memory provider":"Return AtMem to shadow mode"):"Activate AtMem memory provider");
 $("refreshBtn").style.display=isActive||needsRecovery?"none":"inline-block";
 $("switchBtn").disabled=isActive||needsRecovery?false:!readiness.ready_for_active;
 text("switchTitle",isActive||needsRecovery?(isOpenClaw?"Restore OpenClaw":"Return to shadow mode"):"Ready to activate?");
 text("switchCopy",isActive||needsRecovery
  ?(isOpenClaw?"Restore the verified native files and make OpenClaw memory authoritative again.":"Stop memory injection while continuing capture, review, and flight evidence.")
  :(isOpenClaw?"One switch freezes the current native state, verifies the integration, and restores it automatically if anything fails.":"Activation authorizes the runtime adapter to inject only the exact context AtMem returns with inject=true."));
 text("identity",(state.host||"openclaw")+" · "+(state.subject_id||"local-user")+" · "+(state.migration_id||""));
 var drill=state.restore_drill||{};
 var verification=state.verification||{};
 text("verifyStatus",verification.report_sha256
  ?(verification.valid?"Last verification passed":"Last verification failed")+" · "+displayTime(verification.ended_at)+"\nEvidence "+shortDigest(verification.evidence_sha256)+" · report "+shortDigest(verification.report_sha256)
  :"No control verification recorded.");
 $("verifyStatus").style.whiteSpace="pre-line";
 text("drillStatus",drill.valid
  ?"File restoration tested "+displayTime(drill.ended_at)+"\nSaved configuration readable\nLive rollback not performed"
  :"No restore drill recorded. This test does not change live files or configuration.");
 $("drillStatus").style.whiteSpace="pre-line";
 $("drillBtn").style.display=isOpenClaw&&(isActive||needsRecovery)?"inline-block":"none";
 $("bridgeRefresh").style.display=isOpenClaw?"inline-block":"none";
 renderSources(mirror);renderReviews();$("checks").replaceChildren();
 if(isActive&&isOpenClaw){
  addCheck("Native memory snapshot",!!takeover.native_snapshot_verified,"verified");
  addCheck("OpenClaw gateway",!!takeover.gateway_verified,"running");
  addCheck("Memory tools",!!takeover.compatibility_tools_verified,"memory_search and memory_get");
  addCheck("Capture hooks",!!takeover.capture_hooks_verified,"verified");
 }else if(isActive){
  addCheck("Context policy",true,"the adapter may use only context returned with inject=true");
  addCheck("Memory audit",!!mirror.audit_verified,mirror.audit_error||"verified");
  addCheck("Agent scopes",!!((state.agent_topology||{}).verified),"registered topology");
  addCheck("Safe return",true,"return to shadow stops future injection");
 }else if(needsRecovery){
  addCheck("Interrupted switch",false,"status: "+(takeover.status||"unknown"));
  addCheck("Recovery action",false,"Restore OpenClaw verifies the preserved files");
 }else if(pstate==="off"||pstate==="unavailable"){
  addCheck("Capture stopped",false,pstate==="unavailable"?(state.warning||"state is missing or invalid"):"no capture or injection is running");
  addCheck("Native memory authoritative",true,hostName+" continues to use its own memory");
 }else{
  addCheck(isOpenClaw?"Mirror synchronized":"Shadow capture ready",!!mirror.synced,isOpenClaw?number(mirror.source_count)+" sources":"event-driven");
  addCheck(isOpenClaw?"Mirror audit":"Memory audit",!!mirror.audit_verified,mirror.audit_error||"verified");
  addCheck("Searchable records",number(mirror.record_count)>0,number(mirror.record_count)+" ready");
  addCheck("Safe activation",!!readiness.ready_for_active,(readiness.reasons||[])[0]||"ready");
 }
 updateStatusBanner();renderProductVersions()
}
async function reload(){var values=await Promise.all([get("/api/status"),get("/api/memory/reviews")]);state=values[0];reviewQueue=values[1];render()}
async function search(){
 var query=$("query").value.trim();if(!query)return;clearError();$("results").replaceChildren(loadingNode("Searching memory…","empty"));
 try{
  var value=await get("/api/memory/search?query="+encodeURIComponent(query)),rows=value.records||[],box=$("results");box.replaceChildren();
  if(!rows.length){box.appendChild(element("div","empty","No matching memory found."));return}
  rows.forEach(function(row){
   var p=row.openclaw_provenance||{},item=element("div","result"),body=element("p","",row.match_excerpt||row.content||"");
   var meta=element("div","meta");meta.append(element("span","pill",p.plane||row.scope||"memory"));
   if(row.id){var recordButton=element("button","recordlink mono",row.id);recordButton.type="button";recordButton.onclick=function(){inspectRecord(row.id)};meta.append(recordButton)}
   else meta.append(element("span","mono",p.relative_path||""));
   if(p.relative_path)meta.append(element("span","mono",p.relative_path));
   if(p.line_start)meta.append(element("span","mono","lines "+p.line_start+"–"+(p.line_end||p.line_start)));
   item.append(body,meta);box.appendChild(item)
  })
 }catch(error){showError(error)}
}
async function refresh(){
 try{await working(state&&state.host==="openclaw"?"Refreshing the memory mirror":"Checking shadow memory",state&&state.host==="openclaw"?"Reading native files, rebuilding the search index, and verifying its audit evidence.":"Verifying event-driven shadow state and its evidence chain.",async function(){await post("/api/memory/sync",{});await reload()})}
 catch(error){showError(error)}
}
async function restoreDrill(){
 try{await working("Testing file restoration","Staging the frozen files and checking saved configuration without changing the live OpenClaw installation.",async function(){await post("/api/restore-drill",{});await reload()})}
 catch(error){showError(error)}
}
async function verifyNow(){
 try{await working("Verifying AtMem",state&&state.host==="openclaw"?"Measuring configuration, mirror integrity, restore readiness, versions, and gateway health without repairing or restarting anything.":"Verifying control state, canonical memory, agent topology, flight evidence, and shadow/active policy.",async function(){await post("/api/verify",{});await reload()})}
 catch(error){showError(error)}
}
async function refreshBridgeAndTest(){
 if(!state)return;var expected=state.host||"openclaw";
 var entered=prompt("This briefly restarts OpenClaw and may incur a small model charge. Type '"+expected+"' to upgrade the bridge and run one self-test:");if(entered===null)return;
 try{await working("Refreshing the OpenClaw bridge","Installing the version pinned by AtMem, restarting the gateway, verifying the plugin, and recording one fresh test flight.",async function(){var result=await post("/api/bridge/refresh-test",{confirm_host:entered});await reload();await loadBlackbox();if(result.test_flight&&result.test_flight.run_id)await inspectBlackbox(result.test_flight.run_id)})}
 catch(error){showError(error)}
}
async function switchProvider(){
 if(!state)return;clearError();
 if(active()||recovery()){
  var openclaw=state.host==="openclaw";if(!confirm(openclaw?"Restore the verified OpenClaw memory and stop AtMem memory takeover?":"Return to shadow mode and stop injecting AtMem memory?"))return;
  try{await working(openclaw?"Restoring OpenClaw memory":"Returning to shadow mode",openclaw?"Restoring and verifying the frozen native files, then restarting OpenClaw. This can take a minute.":"Stopping context injection while preserving capture and audit evidence.",async function(){await post("/api/restore",{});await reload()})}
  catch(error){showError(error)}
  return
 }
 var expected=state.host||"openclaw";
 var entered=prompt("To activate AtMem, type '"+expected+"':");
 if(entered===null)return;
 try{await working("Activating AtMem",state.host==="openclaw"?"Freezing native memory, checking compatibility, restarting OpenClaw, and verifying memory tools. This can take a minute.":"Authorizing the runtime adapter to use only AtMem context explicitly marked for injection.",async function(){await post("/api/mode",{mode:"active",confirm_host:entered});await reload()})}
 catch(error){showError(error)}
}
var VIEWS={status:"viewStatus",decisions:"viewDecisions",evidence:"viewEvidence"};
function activateView(name){
 var panelId=VIEWS[name]||VIEWS.status;
 document.querySelectorAll(".tabpanel").forEach(function(panel){panel.classList.toggle("active",panel.id===panelId)});
 [["navStatus","status"],["navDecisions","decisions"],["navEvidence","evidence"]].forEach(function(pair){var btn=$(pair[0]);var isActive=(VIEWS[name]?name:"status")===pair[1];btn.classList.toggle("active",isActive);btn.setAttribute("aria-selected",isActive?"true":"false")})
}
function showView(name){if(location.hash!=="#"+name){location.hash=name}else{applyRoute()}}
function applyRoute(){
 var hash=(location.hash||"#status").slice(1);
 if(VIEWS[hash]){activateView(hash);return}
 var target=document.getElementById(hash);
 if(target){var panel=target.closest(".tabpanel");if(panel){var name=Object.keys(VIEWS).find(function(key){return VIEWS[key]===panel.id});activateView(name||"status")}target.scrollIntoView({behavior:"smooth",block:"start"});return}
 activateView("status")
}
window.addEventListener("hashchange",applyRoute);applyRoute();
$("navStatus").onclick=function(){showView("status")};$("navDecisions").onclick=function(){showView("decisions")};$("navEvidence").onclick=function(){showView("evidence")};
$("searchBtn").onclick=search;$("query").addEventListener("keydown",function(event){if(event.key==="Enter")search()});
$("refreshBtn").onclick=refresh;$("switchBtn").onclick=switchProvider;
$("drillBtn").onclick=restoreDrill;
$("verifyBtn").onclick=verifyNow;
$("bridgeRefresh").onclick=refreshBridgeAndTest;
$("reviewRefresh").onclick=refreshReviews;
$("blackboxRefresh").onclick=loadBlackbox;
$("agentRefresh").onclick=function(){reload().catch(showError)};
$("activityQuery").addEventListener("input",function(){clearTimeout(activitySearchTimer);activitySearchTimer=setTimeout(function(){applyActivityFilters().catch(showError)},300)});$("activityTopic").onchange=function(){applyActivityFilters().catch(showError)};$("activityWhen").onchange=function(){applyActivityFilters().catch(showError)};$("activityLoadMore").onclick=function(){loadMoreActivity().catch(showError)};$("showAllFlights").onclick=function(){var query=$("activityQuery").value;showView("blackboxArchiveCard");$("flightQuery").value=query;filterBlackboxArchive()};
$("flightSearch").onclick=filterBlackboxArchive;$("flightQuery").addEventListener("keydown",function(event){if(event.key==="Enter")filterBlackboxArchive()});$("flightStatus").onchange=filterBlackboxArchive;[$("flightSince"),$("flightUntil")].forEach(function(input){input.onchange=function(){flightRange="custom";document.querySelectorAll("[data-flight-range]").forEach(function(button){button.classList.remove("active")});filterBlackboxArchive()}});document.querySelectorAll("[data-flight-range]").forEach(function(button){button.onclick=function(){setFlightRange(button.dataset.flightRange,true)}});
$("auditRun").onclick=function(){auditSearch(true)};$("auditQuery").addEventListener("keydown",function(event){if(event.key==="Enter")auditSearch(true)});
$("auditDirection").onchange=function(){auditSearch(true)};$("auditLimit").onchange=function(){auditSearch(true)};
$("auditNext").onclick=function(){if(!auditLast||!auditLast.next_cursor)return;auditCursors=auditCursors.slice(0,auditPageIndex+1);auditCursors.push(auditLast.next_cursor);auditPageIndex++;loadAudit(false)};
$("auditBack").onclick=function(){if(auditPageIndex===0)return;auditPageIndex--;loadAudit(false)};
document.querySelectorAll("[data-range]").forEach(function(button){button.onclick=function(){var minutes=Number(button.dataset.range||0),now=new Date();$("auditUntil").value=minutes?isoInput(now):"";$("auditSince").value=minutes?isoInput(new Date(now.getTime()-minutes*60000)):"";auditSearch(true)}});
document.querySelectorAll("[data-event-pattern]").forEach(function(button){button.onclick=function(){var pattern=button.dataset.eventPattern||"",select=$("auditType");if(!Array.from(select.options).some(function(o){return o.value===pattern}))select.appendChild(new Option(pattern,pattern));select.value=pattern;auditSearch(true)}});
$("auditReset").onclick=function(){applyAuditFilters({});auditSearch(true)};
$("auditSave").onclick=function(){var name=prompt("Name this audit view:");if(!name||!name.trim())return;var views=savedViews();views.push({name:name.trim(),filters:auditFilters()});localStorage.setItem("atmem-audit-views",JSON.stringify(views));renderSavedViews();$("auditSaved").value=String(views.length-1)};
$("auditSaved").onchange=function(){var view=savedViews()[Number($("auditSaved").value)];if(!view)return;applyAuditFilters(view.filters||{});auditSearch(true)};
$("auditorClose").onclick=closeAuditor;$("auditorBackdrop").addEventListener("click",function(event){if(event.target===$("auditorBackdrop"))closeAuditor()});document.addEventListener("keydown",function(event){if(event.key==="Escape")closeAuditor()});
applyTheme(preferredTheme(),false);$("themeToggle").onclick=function(){applyTheme(document.documentElement.dataset.theme==="dark"?"light":"dark",true)};
async function init(){try{csrf=(await get("/api/session")).csrf_token;renderSavedViews();await Promise.all([get("/api/product").then(function(value){productInfo=value;renderProductVersions()}),reload(),loadAudit(true),loadBlackbox()]);var pollTick=0;setInterval(async function(){if(document.hidden||progressTimer)return;pollTick++;try{if(pollTick%3===0){await reload()}else{await refreshReviews(true)}}catch(_){}},5000)}catch(error){showError(error)}}
init()
})();
