#!/usr/bin/env python3
"""Real OpenClaw bridge/MCP lost-response probe, with isolated synthetic data.

Not an autonomous LLM or OpenClaw gateway test. Requires a compiled bridge.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading


def proxy(root):
    """Drop only a successful remember reply, then SIGKILL its backend."""
    child = subprocess.Popen(
        [sys.executable, "-m", "atmem.cli", "mcp", "--db", str(root / "memory.db"),
         "--subject", "lost-ack-test"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    requests = {}

    def forward():
        for line in sys.stdin:
            request = json.loads(line)
            with (root / 'transport-requests.jsonl').open('a') as log:
                log.write(json.dumps(request) + '\n')
            requests[request.get("id")] = request
            try:
                child.stdin.write(line)
                child.stdin.flush()
            except (BrokenPipeError, ValueError):
                break

    threading.Thread(target=forward, daemon=True).start()
    for line in child.stdout:
        reply = json.loads(line)
        request = requests.get(reply.get("id"), {})
        if (request.get("params", {}).get("name") == "memory_remember"
                and not (root / "dropped.json").exists()
                and not (root / "no-fault").exists()
                and not reply.get("error") and not reply.get("result", {}).get("isError")):
            payload = json.loads(reply["result"]["content"][0]["text"])
            if not payload.get("records"):
                raise RuntimeError("Refusing fault: no committed record in backend reply")
            with (root / "dropped.json").open("w") as evidence:
                json.dump({"request": request, "reply": reply, "backend_pid": child.pid}, evidence, indent=2)
                evidence.flush()
                os.fsync(evidence.fileno())
            os.kill(child.pid, signal.SIGKILL)
            child.wait()
            # Keep transport open until the real bridge timeout, without sending ack.
            threading.Event().wait(30)
            return
        sys.stdout.write(line)
        sys.stdout.flush()
    child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--proxy", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    if args.proxy:
        proxy(root)
        return
    root.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    bridge = args.bridge.resolve()
    config = {"root": str(root), "bridge": str(bridge), "python": sys.executable,
              "script": str(Path(__file__).resolve()), "repo": str(repo)}
    (root / "config.json").write_text(json.dumps(config))
    driver = r'''
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const c=JSON.parse(readFileSync(process.argv[2],'utf8'));
const {default:plugin}=await import(pathToFileURL(c.bridge+'/index.js'));
const {AtmemClient}=await import(pathToFileURL(c.bridge+'/src/rpc-client.js'));
process.env.PYTHONPATH=c.repo;
const args=['-m','atmem.cli','mcp','--db',c.root+'/memory.db','--subject','lost-ack-test'];
const observer=new AtmemClient({command:c.python,args,idleTimeoutMs:60000});
const tools=new Map(),services=[];
const ctx={agentId:'main',sessionKey:'lost-ack-session',sessionId:'lost-ack-session',
  runId:'lost-ack-turn',senderIsOwner:true,activeModel:{provider:'test',modelId:'deterministic-driver'}};
plugin.register({pluginConfig:{command:c.python,commandArgs:[c.script,'--proxy','--output',c.root],
  dbPath:c.root+'/memory.db',subject:'lost-ack-test',takeoverActive:true,
  recall:{enabled:false,timeoutMs:2000},capture:{enabled:false},persona:{enabled:false},
  tools:{enabled:true},controlPlane:{enabled:false,blackboxEnabled:false}},
  logger:{debug(){},info(){},warn(){},error(){}},on(){},
  registerTool(spec){const tool=typeof spec==='function'?spec(ctx):spec;tools.set(tool.name,tool)},
  registerService(s){services.push(s)}});
const fact='User prefers cobalt blue notebooks.';
const result={scope:'registered OpenClaw bridge tool + real MCP backend; deterministic driver',fact};
try {
  await observer.callTool('memory_stage_user_message',{message:'Remember that I prefer cobalt blue notebooks.',
    source_aliases:['main:lost-ack-turn','main:lost-ack-session'],run_id:'lost-ack-turn'});
  try {await tools.get('memory_remember').execute('write-001',{fact,factKey:'notebook_preference'});
    throw new Error('Expected timeout did not occur');}
  catch(e){assert.match(e.message,/timed out/);result.first_call_error=e.message;}
  result.before_retry=await observer.callTool('memory_list',{include_inactive:true});
  result.dropped=JSON.parse(readFileSync(c.root+'/dropped.json','utf8'));
  assert.equal(result.before_retry.length,1);
  const id=result.before_retry[0].id;
  // Stop/recreate the bridge client connection after the real timeout.
  for(const s of services) await s.stop?.();
  result.same_id_retry=await tools.get('memory_remember').execute('write-001',{fact,factKey:'notebook_preference'});
  result.new_id_retry=await tools.get('memory_remember').execute('write-002',{fact,factKey:'notebook_preference'});
  result.read_back=await tools.get('memory_get').execute('read-001',{path:'atmem://record/'+id});
  result.after_retry=await observer.callTool('memory_list',{include_inactive:true});
  result.verify=await observer.callTool('memory_verify',{});
  result.audit=await observer.callTool('memory_audit',{});
  assert.equal(result.after_retry.length,1);
  assert.equal(result.after_retry[0].id,id);
  assert.equal(result.after_retry[0].content,fact);
  assert.deepEqual(result.after_retry,result.before_retry);
  assert.equal(result.verify.valid,true);
  assert.equal(result.audit.audit_chain_valid,true);
  assert.equal(result.audit.audit_log.filter(e=>e.event_type==='memory.record_created').length,1);
  for(const key of ['same_id_retry','new_id_retry']){
    const p=JSON.parse(result[key].content[0].text);
    assert.equal(p.stored,true);assert.equal(p.record_id,id);assert.equal(p.status,'already_stored');
  }
  assert.match(result.read_back.content[0].text,/User prefers cobalt blue notebooks/);
  result.assertions_passed=true;
}catch(e){result.error=e.stack;process.exitCode=1;}
finally{
  for(const s of services) await s.stop?.();observer.close();
  writeFileSync(c.root+'/result.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify({output:c.root,passed:result.assertions_passed??false,error:result.error}));
}
'''
    (root / "driver.mjs").write_text(driver)
    env = dict(os.environ, PYTHONPATH=str(repo))
    completed = subprocess.run(["node", str(root / "driver.mjs"), str(root / "config.json")], env=env, timeout=60)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
