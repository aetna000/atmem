"""Two actual MCP client identities and a real application-owned effect path."""
import sys
import time

from atmem.contracts.feedback import MCPInvocation
from atmem.evidence.models import EvidenceRole
from atmem.private_paths import protect_private_path
from rag_fixtures import setup_rag
from test_governed_mcp import Client


def test_two_stdio_clients_cannot_bypass_native_policy_or_repeat_another_actors_write(tmp_path):
    f = setup_rag(tmp_path)
    f.feedback.clock = time.time
    second = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="second-proxy-user",
                              role=EvidenceRole.INVESTIGATOR, scope=f.scope.evidence_scope())
    for principal in (f.user["principal_id"], second["principal_id"]):
        f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=principal,
                               operations=("read", "execute"), expires_at=int(time.time())+600)
    owner_file = tmp_path/"owner.token"
    owner_file.touch()
    protect_private_path(owner_file)
    owner_file.write_text(f.owner["token"])
    script = tmp_path/"proxy_app.py"
    # This fixture app is owner configuration, not a model-supplied handler or
    # endpoint. Its one target path is fixed outside the tool arguments.
    script.write_text('''import argparse
from pathlib import Path
from atmem import Memory
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService
from atmem.knowledge.rag.service import RagService
from atmem.mcp.governed import GovernedMCPServer
from atmem.mcp.guarded import GuardedDispatcher
p=argparse.ArgumentParser()
for key in ('root','vault-id','credential-file','agent','workspace'):
    p.add_argument('--'+key, required=True)
p.add_argument('command')
a=p.parse_args()
root=Path(a.root)
e=EvidenceService(root,vault_id=a.vault_id)
m=Memory(':memory:',auto_vectors=False)
f=FeedbackService(e,memory=m)
s=f.bind(Path(a.credential_file).read_text(),agent_id=a.agent,workspace_id=a.workspace)
d=GuardedDispatcher(f,versions={'adapter':'fixture-v1'})
schema={'type':'object','properties':{'body':{'type':'string','maxLength':100}},'required':['body'],'additionalProperties':False}
def write(args):
    with (root.parent/'proxy-effects.txt').open('a') as stream:
        stream.write(args['body']+'\\n')
    return {'accepted':True}
d.register((root.parent/'owner.token').read_text(),s.scope,tool='fixture.write',schema_version='v1',schema=schema,invoke=write,native_guard=lambda args:args['body']!='forbidden')
GovernedMCPServer(f,RagService(f),s,dispatcher=d).serve()
m.close()
''')
    clients = []
    path = tmp_path/"proxy-effects.txt"
    try:
        a = Client(f, tmp_path, f.user["token"], "proxy-a", command=[sys.executable, str(script)])
        clients.append(a)
        b = Client(f, tmp_path, second["token"], "proxy-b", command=[sys.executable, str(script)])
        clients.append(b)
        tools = a.call("tools/list")["result"]["tools"]
        assert next(t for t in tools if t["name"] == "guarded_execute")["annotations"]["readOnlyHint"] is False
        invocation = MCPInvocation("fixture.write", "v1", {"body": "once"}, "actor-a")
        result = a.tool("guarded_execute", invocation=invocation.to_dict())["structuredContent"]
        assert result["status"] == "reported_complete" and path.read_text() == "once\n"
        assert a.tool("guarded_execute", invocation=invocation.to_dict())["structuredContent"]["receipt_id"] == result["receipt_id"]
        assert b.tool("guarded_execute", invocation=invocation.to_dict())["isError"]
        blocked = b.tool("guarded_execute", invocation=MCPInvocation("fixture.write", "v1", {"body": "forbidden"}, "actor-b").to_dict())
        assert blocked["structuredContent"]["status"] == "blocked"
        assert path.read_text() == "once\n"
        assert b.tool("guarded_inspect", receipt_id=result["receipt_id"])["structuredContent"]["status"] == "reported_complete"
        f.feedback.revoke_agent(f.owner["token"], f.scope, principal_id=second["principal_id"])
        assert b.call("tools/list")["error"]["code"] == -32001
    finally:
        for client in clients:
            client.close()
