"""CLI/MCP/API share actual encrypted state and exact metric denominators."""
import json
import subprocess
import sys
import time

from atmem.mcp.governed import GovernedMCPServer
from atmem.private_paths import protect_private_path
from test_feedback_actions import actions_fixture
from test_governed_mcp import initialize, request


def test_cli_mcp_and_api_report_identical_counts_and_recheck_revocation(tmp_path):
    f,outcome=actions_fixture(tmp_path)
    f.feedback.clock=time.time
    f.feedback.grant_agent(f.owner['token'],f.scope,principal_id=f.user['principal_id'],
                           operations=('read','report'),expires_at=int(time.time())+600)
    f.feedback.schedule(f.owner['token'],f.scope,schedule_id='schedule',tasks=(
        {'outcome_id':'outcome','episode_id':'episode','answerable':True},))
    token=tmp_path/'application.token'
    token.touch()
    protect_private_path(token)
    token.write_text(f.user['token'])
    payload=tmp_path/'outcome.json'
    payload.write_text(json.dumps(outcome.to_dict()))
    prefix=[sys.executable,'-m','atmem.cli_feedback','--root',str(f.evidence.root),'--vault-id','rag',
            '--credential-file',str(token),'--agent','writer','--workspace','project']
    def run(*args):
        return subprocess.run(prefix+list(args),capture_output=True,text=True,encoding='utf-8',timeout=15)
    written=run('report','--file',str(payload),'--key','first')
    assert written.returncode==0,written.stderr
    assert json.loads(written.stdout)['verified_success'] is False
    cli=run('quality','--schedule','schedule')
    assert cli.returncode==0,cli.stderr
    expected=f.feedback.quality(f.session,schedule_id='schedule')
    assert json.loads(cli.stdout)==expected
    server=GovernedMCPServer(f.feedback,f.rag,f.session)
    initialize(server)
    mcp=server.handle(request('tools/call',{'name':'feedback_quality','arguments':{'schedule_id':'schedule'}}))
    assert mcp['result']['structuredContent']==expected
    f.feedback.revoke_agent(f.owner['token'],f.scope,principal_id=f.user['principal_id'])
    denied=run('outcome','--id','outcome')
    assert denied.returncode==2 and denied.stdout==''
    assert f.user['token'] not in denied.stderr and 'five days' not in denied.stderr
