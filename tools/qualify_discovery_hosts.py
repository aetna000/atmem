"""Retain read-only host inventory. This does NOT qualify live discovery routing.

Only --version and --help are invoked; no prompts, login operations, token files,
configuration edits, provider inference or rental calls. Full bounded output is
retained through the existing encrypted replay evidence boundary.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess

from atmem.code.discovery_hosts import HOSTS

CANDIDATE_FLAGS = {
    'claude': ('--tools', '--mcp-config', '--strict-mcp-config'),
    'codex': ('app-server', 'mcp', 'exec'),
    'copilot': ('--available-tools', '--excluded-tools', '--additional-mcp-config'),
    'muse': ('--mcp-config', '--tools'),
    'grok': ('--mcp-config', '--tools'),
}


def inspect_command(argv, *, timeout=10):
    environment = {key: value for key, value in os.environ.items()
                   if key in {'PATH', 'HOME', 'TMPDIR', 'SystemRoot', 'SHELL', 'LANG'}}
    environment.update(NO_COLOR='1', CI='1')
    if Path(argv[0]).name == 'muse':
        # Installed Meta Muse launcher documents these controls in its source;
        # --help/--version alone do not stop its pre-launch updater/login path.
        environment.update(MUSE_NO_AUTO_UPDATE='1', MUSE_LOGIN='0')
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment, start_new_session=(os.name != 'nt'))
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    # CLI help is normally small. Do not silently truncate full evidence.
    if len(stdout) + len(stderr) > 1_000_000:
        raise ValueError('host inventory output exceeds retention bound')
    return {'argv': argv, 'exit_code': process.returncode, 'timed_out': timed_out,
            'stdout_base64': base64.b64encode(stdout).decode(),
            'stderr_base64': base64.b64encode(stderr).decode(),
            'stdout_sha256': sha256(stdout).hexdigest(), 'stderr_sha256': sha256(stderr).hexdigest()}


def inventory(probe=inspect_command, which=shutil.which):
    rows = []
    for host in HOSTS:
        binary = which(host)
        row = {'host': host, 'platform': platform.system(), 'binary': binary,
               'capability': 'unprobed', 'version': 'unavailable',
               'reason': 'no_live_boundary_or_subscription_probe', 'commands': []}
        if binary:
            version = probe([binary, '--version'])
            help_result = probe([binary, '--help'])
            row['commands'] = [version, help_result]
            text = base64.b64decode(version['stdout_base64']).decode(errors='replace')
            lines = text.strip().splitlines()
            row['version'] = lines[0][:200] if lines else 'unverified'
            help_text = base64.b64decode(help_result['stdout_base64']).decode(errors='replace')
            row['candidate_flags_present'] = [flag for flag in CANDIDATE_FLAGS[host] if flag in help_text]
        else:
            row.update(capability='unavailable', reason='binary_not_found')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args()
    if args.evidence_root.exists():
        raise ValueError('choose a new evidence root; do not overwrite prior inventory')
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.atmem_bridge import ReplayEvidence
    scope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
    principal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(args.evidence_root / 'vault', vault_id='discovery-044', scope=scope)
    rows = inventory()
    evidence.capture(run_id='host-inventory', kind='discovery.host_inventory', principal=principal,
        payload={'format': 'atmem-discovery-host-inventory-v1', 'rows': rows,
                 'model_dispatches': 0, 'qualification': 'read_only_inventory_not_live_routing'})
    checked = evidence.inspect(principal, 'host-inventory')
    if not checked or checked[-1]['envelope']['payload']['rows'] != rows:
        raise ValueError('encrypted inventory roundtrip failed')
    print(json.dumps({'status': 'inventory_retained', 'evidence_root': str(args.evidence_root),
        'model_dispatches': 0, 'rental_spend_usd': 0,
        'hosts': [{key: row[key] for key in ('host', 'platform', 'version', 'capability', 'reason')} for row in rows]}))


if __name__ == '__main__':
    main()
