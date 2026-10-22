import json
from pathlib import Path
import subprocess
import sys

from atmem.mcp.strict_proxy import argument_error


def test_closed_root_arguments_reject_without_rewriting_values():
    assert argument_error({'properties':{}},{'query':'not accepted'})
    assert argument_error({'properties':{}},{}) is None
    assert argument_error({'properties':{},'additionalProperties':True},{'query':'allowed'}) is None
    assert argument_error({'properties':{'name':{}},'required':['name']},{})


def test_real_proxy_rejects_before_backend_and_preserves_valid_calls(tmp_path):
    source=tmp_path/'server.py'
    source.write_text('import json,sys\nfor line in sys.stdin:\n r=json.loads(line)\n if r["method"]=="tools/list": result={"tools":[{"name":"list_items","inputSchema":{"type":"object","properties":{}}}]}\n else: result={"content":[{"type":"text","text":json.dumps(r["params"]["arguments"])}]}\n print(json.dumps({"jsonrpc":"2.0","id":r["id"],"result":result}),flush=True)\n')
    messages=[{'id':1,'method':'tools/list'},
              {'id':2,'method':'tools/call','params':{'name':'list_items','arguments':{'query':'wrong'}}},
              {'id':3,'method':'tools/call','params':{'name':'list_items','arguments':{}}}]
    script=Path(__file__).resolve().parents[1]/'atmem/mcp/strict_proxy.py'
    process=subprocess.run([sys.executable,'-I',str(script),'--',sys.executable,'-I',str(source)],
        input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,capture_output=True,timeout=10)
    assert process.returncode==0,process.stderr
    replies=[json.loads(line) for line in process.stdout.splitlines()]
    assert replies[1]['result']['isError'] is True
    assert replies[2]['result']['content'][0]['text']=='{}'
