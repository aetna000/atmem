"""Real browser check against an isolated installed-wheel dashboard, not user data."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile


def serve(root):
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer, dashboard_html
    from atmem.service.household import HouseholdApplication
    from atmem.code.install import CodeInstall
    from atmem.code.contracts import CodeObservation
    from atmem.code.identity import CodeIdentity
    from atmem.code.formation import CodeFormation
    from atmem.memory import Memory

    root.mkdir(parents=True, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(root / 'home')
    project = root / 'project'
    project.mkdir()
    (project / 'parser.py').write_text('def parse(value):\n    return value.strip()\n')
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    subprocess.run(['git', '-C', str(project), 'add', 'parser.py'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Release fixture',
        '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    database = root / 'memory.db'
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    try:
        CodeInstall(memory.store).setup(project, subject_id='local', profile_id='shared',
            agent_id='codex', host='codex', apply=True)
        scope = CodeIdentity(memory.store).resolve(project, subject_id='local',
            profile_id='shared', agent_id='codex')
        result = CodeFormation(memory).form(CodeObservation('browser-event', 'browser-session',
            'browser-turn', 'codex', 'user_turn', 'Remember that my preferred formatter is Ruff.',
            '2026-10-20T10:00:00+00:00', 'conversation:browser', None, scope))
        assert result['formed'], result
    finally:
        memory.close()
    manager = ControlPlaneManager.start(host='generic', subject_id='local',
        state_path=root / 'state.json', control_root=root / 'control', memory_db=database)
    identity = manager.identity_service()
    bootstrap = identity.bootstrap()
    password = secrets.token_urlsafe(30)
    session = identity.login('administrator', bootstrap['password'])
    identity.change_password(session['session_token'], bootstrap['password'], password)
    identity.logout(session['session_token'])
    server = ControlDashboardServer(('127.0.0.1', 0), manager, html=dashboard_html())
    # Anonymous pipe to this script's browser driver only; never retained in reports.
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
        'password': password, 'project_id': scope.project_id}), flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--python', help='Installed candidate interpreter')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve)
        return
    from playwright.sync_api import sync_playwright, expect
    workspace = Path(tempfile.mkdtemp(prefix='atmem-code-browser-'))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['ATMEM_NONINTERACTIVE'] = '1'
    with (workspace / 'server.log').open('w') as log:
        child = subprocess.Popen([args.python, '-I', str(Path(__file__).resolve()),
            '--serve', str(workspace / 'state')], cwd=workspace, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            line = child.stdout.readline()
            if not line:
                raise RuntimeError('isolated dashboard did not start; inspect ' + str(workspace / 'server.log'))
            connection = json.loads(line)
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(headless=True)
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(connection['url'])
                page.locator('#loginPassword').fill(connection['password'])
                page.locator('#loginForm button[type=submit]').click()
                page.locator('#navMemory').click()
                page.get_by_role('button', name='Coding memory', exact=False).click()
                page.locator('#codeRefresh').click()
                expect(page.locator('#codeProject option[value="' + connection['project_id'] + '"]')).to_have_count(1)
                page.locator('#codeProject').select_option(connection['project_id'])
                page.locator('#codeQuery').fill('Ruff')
                page.locator('#codeSearch').click()
                expect(page.locator('#codeResults')).to_contain_text('Ruff')
                # Shared settings are persisted by the real authorized dashboard API.
                page.get_by_text('Automatic memory settings', exact=True).click()
                page.locator('#codeAutoCapture').uncheck()
                page.locator('#codeAutoRecall').uncheck()
                page.locator('#codeSettings button[type=submit]').click()
                expect(page.locator('#codeStatus')).to_have_text('Settings saved')
                page.locator('#codeClearPreview').click()
                expect(page.locator('#codeClearApply')).to_be_enabled()
                page.locator('#codeClearApply').click()
                expect(page.locator('#codeClearSummary')).to_contain_text('Local deletion verified')
                expect(page.locator('#codeResults')).to_contain_text('No memories match')
                assert not errors, errors
                page.screenshot(path=str(workspace / 'coding-memory.png'), full_page=True)
                browser.close()
            report = {'format': 'atmem-code-browser-check-v1', 'passed': True,
                'checks': ['administrator login', 'project selector', 'shared memory search',
                    'pause capture/recall settings', 'scoped clear preview', 'verified deletion'],
                'javascript_errors': errors, 'installed_python': args.python,
                'artifacts': str(workspace), 'owner_data_opened': False}
            args.report.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report))
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
