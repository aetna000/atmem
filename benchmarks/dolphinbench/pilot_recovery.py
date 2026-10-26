"""Offline evidence reconstruction and explicitly admitted pilot epochs.

No provider or application dispatch lives in this module. Historical verification
is deliberately separate from load_condition: a retained old byte snapshot never
qualifies old code for new execution. Local operator proofs are not attestations.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import copy
import fcntl
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from .readiness import admit, identity, load_condition, pin, read, save, sha, verify_pin
from .recording import fingerprint, micros
from .tool_defaults import MCP_METADATA, _same

ROOT = Path(__file__).resolve().parents[2]
REPAIR_SOURCES = frozenset({
    'benchmarks/dolphinbench/tool_defaults.py',
    'benchmarks/dolphinbench/pilot_readiness.py',
    'benchmarks/dolphinbench/readiness.py',
    'benchmarks/dolphinbench/pilot_recovery.py',
    'benchmarks/dolphinbench/recovery_supervisor.py',
    'scripts/launch_dolphin_readiness.py',
})
IMPORTED = frozenset({'morgan/023', 'morgan/085'})
RECOVERED = 'morgan/129'
LINEAGE = 'Partial 20 results span two HARNESS revisions; scientific configuration unchanged.'


def lineage(revisions):
    if revisions not in (2, 3):
        raise ValueError('At most two bounded harness repair epochs')
    return LINEAGE if revisions == 2 else LINEAGE.replace('two HARNESS', 'three HARNESS')


def same_science(old, new):
    def scientific(value):
        value = copy.deepcopy(value)
        value['inputs'].pop('source_manifest')
        return value
    if scientific(old) != scientific(new):
        raise ValueError('Scientific configuration/selected IDs changed')
    if new['budget']['caps_usd']['pilot'] != 10:
        raise ValueError('Recovery requires the same cumulative USD10 cap')


def historical_condition(bundle_path):
    """Bundle maps *every* original source pin to retained before-repair bytes.

    Format: {condition: pin, source_manifest: pin,
             snapshots: [{original: old_pin, retained: snapshot_pin}, ...]}.
    No old path is resolved as executing code or blessed by this verifier.
    """
    bundle = read(bundle_path)
    old = read(verify_pin(bundle['condition']))
    manifest_path = verify_pin(bundle['source_manifest'])
    if sha(manifest_path) != old['inputs']['source_manifest']['sha256']:
        raise ValueError('Historical source manifest bytes differ')
    source = read(manifest_path)
    snapshots = bundle['snapshots']
    if len(snapshots) != len(source) or len({s['original']['path'] for s in snapshots}) != len(source):
        raise ValueError('Every historical source requires one retained snapshot')
    if sorted((s['original'] for s in snapshots), key=lambda p: p['path']) != sorted(source, key=lambda p: p['path']):
        raise ValueError('Historical snapshot inventory differs')
    for item in snapshots:
        retained = verify_pin(item['retained'])
        if sha(retained) != item['original']['sha256']:
            raise ValueError('Historical snapshot bytes differ: ' + item['original']['path'])
    # Scientific inputs are inherited in place, still immutable and byte checked.
    for role, entry in old['inputs'].items():
        if role != 'source_manifest':
            verify_pin(entry)
    return old, source


def verify_transition(bundle_path, new_condition):
    old, source = historical_condition(bundle_path)
    same_science(old, new_condition)
    before = {p['path']: p['sha256'] for p in source}
    after = {p['path']: p['sha256'] for p in read(new_condition['inputs']['source_manifest']['path'])}
    if len(before) != len(source) or len(after) != len(read(new_condition['inputs']['source_manifest']['path'])):
        raise ValueError('Duplicate source paths')
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    allowed = {str(ROOT / p) for p in REPAIR_SOURCES}
    if not changed or not set(changed) <= allowed or set(before) - set(after):
        raise ValueError('Source change outside bounded repair allowlist')
    return old, changed


def source_changes(bundle_path, condition, changed):
    bundle = read(bundle_path)
    before = {p['path']: p['sha256'] for p in read(bundle['source_manifest']['path'])}
    after = {p['path']: p['sha256'] for p in read(condition['inputs']['source_manifest']['path'])}
    return [{'path': p, 'old_sha256': before.get(p), 'new_sha256': after.get(p)} for p in changed]


def inventory(directory):
    directory = Path(directory).resolve()
    paths = []
    for p in sorted(directory.rglob('*')):
        if p.is_symlink():
            raise ValueError('Evidence symlinks are not supported: ' + str(p))
        if p.is_file() and not p.name.startswith('._') and p.name not in {
                '.lock', 'budget.db-shm', 'budget.db-wal'}:
            paths.append(pin(p))
    return paths


def inherited_copy_sources(parent):
    parent = Path(parent)
    files = []
    for folder in ('tests', 'grades', 'native', 'judge-calls', 'subscription/calls'):
        files.extend(p for p in sorted((parent / folder).rglob('*'))
                     if p.is_file() and not p.name.startswith('._') and p.suffix != '.inflight')
    for launch in sorted((parent / 'launches').glob('*')):
        for folder in ('judge-calls', 'subscription/calls'):
            files.extend(p for p in sorted((launch / folder).rglob('*'))
                         if p.is_file() and not p.name.startswith('._'))
    return files


def copy_exact(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as stream, destination.open('xb') as out:
        shutil.copyfileobj(stream, out)
        out.flush()
        os.fsync(out.fileno())
    if sha(source) != sha(destination):
        raise ValueError('Copy changed bytes')


def snapshot_budget(source, destination, campaign):
    """Never open original SQLite: stage DB/WAL bytes, then backup that copy.

    Parent must be exited/quiescent. Compare source bytes before/after copying;
    include a WAL if present and retain its pin. SHM is rebuildable in temp only.
    Finalize and validate locally before publishing bytes to the epoch volume.
    """
    source, destination = Path(source), Path(destination)
    journal = Path(str(source) + '-journal')
    if journal.exists() and journal.stat().st_size:
        raise ValueError('Hot/uncertain parent SQLite rollback journal; reconcile first')
    for suffix in ('', '-wal', '-shm', '-journal'):
        existing = Path(str(destination) + suffix)
        if existing.exists():
            raise FileExistsError(existing)
    files = [source] + ([Path(str(source) + '-wal')] if Path(str(source) + '-wal').exists() else [])
    pins = [pin(p) for p in files]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        staged = Path(temp) / 'budget.db'
        standalone = Path(temp) / 'standalone.db'
        for p in files:
            copy_exact(p, Path(str(staged) + str(p)[len(str(source)):]))
        for entry in pins:
            verify_pin(entry)
        with closing(sqlite3.connect(staged)) as db:
            with closing(sqlite3.connect(standalone)) as out:
                db.backup(out)
                if out.execute('PRAGMA journal_mode=DELETE').fetchone() != ('delete',):
                    raise ValueError('Standalone budget backup required')
        if any(Path(str(standalone) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
            raise ValueError('Budget backup still has SQLite sidecars; refuse main-file-only inheritance')
        with closing(sqlite3.connect(standalone.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Standalone budget backup failed integrity check')
        budget_status(standalone, campaign)
        for entry in pins:
            verify_pin(entry)
        # No SQLite connection touches the destination: WAL conversion needs
        # local locking/SHM support that the epoch filesystem may not provide.
        copy_exact(standalone, destination)
    return pins


def budget_status(path, campaign, *, inflight_since=None):
    # This can be the live epoch ledger: include its WAL in the read transaction.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('SELECT cap,identity FROM campaign WHERE singleton=1').fetchone()
        if row != (micros(10), fingerprint(campaign)):
            raise ValueError('Inherited ledger identity or cumulative cap differs')
        for state, created in db.execute("SELECT state,created FROM calls WHERE state NOT IN ('completed','unsent')"):
            if (state != 'reserved' or inflight_since is None or type(created) not in (int, float)
                    or not math.isfinite(created) or not inflight_since <= created <= time.time() + 5):
                raise ValueError('Unresolved charge/reservation: stop before continuation')
        for state, reserved, actual, usage, response_hash in db.execute(
                'SELECT state,reserved,actual,usage_json,response_sha256 FROM calls'):
            if type(reserved) is not int or reserved < 0:
                raise ValueError('Invalid budget reservation')
            if state == 'completed':
                measured = json.loads(usage) if isinstance(usage, str) else {}
                if (not isinstance(measured, dict) or type(actual) is not int or not 0 <= actual <= reserved or
                        not isinstance(response_hash, str) or len(response_hash) != 64 or
                        any(type(measured.get(k)) is not int or measured[k] < 0
                            for k in ('prompt_tokens', 'completion_tokens'))):
                    raise ValueError('Unresolved actual charge/usage in completed budget call')
            elif state == 'reserved' and any(v is not None for v in (actual, usage, response_hash)):
                raise ValueError('Malformed live reservation requires reconciliation')
        spent = db.execute("SELECT COALESCE(SUM(actual),0) FROM calls WHERE state='completed'").fetchone()[0]
        reserved = db.execute("SELECT COALESCE(SUM(reserved),0) FROM calls WHERE state='reserved'").fetchone()[0]
        if spent is None or not 0 <= spent <= spent + reserved <= micros(10):
            raise ValueError('Cumulative budget exceeded')
        return spent


def verify_inherited_budget(inherited, current, campaign, *, inflight_since=None):
    """Carry every old row and charge unchanged, not just the nominal cap."""
    budget_status(inherited, campaign)
    spent = budget_status(current, campaign, inflight_since=inflight_since)
    with closing(sqlite3.connect(Path(inherited).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as old:
        rows = old.execute('SELECT * FROM calls').fetchall()
    with closing(sqlite3.connect(Path(current).resolve().as_uri() + '?mode=ro', uri=True)) as new:
        for row in rows:
            if new.execute('SELECT * FROM calls WHERE call_id=?', (row[0],)).fetchone() != row:
                raise ValueError('Inherited budget call/charge was modified or removed')
    return spent


def _decode_json(content):
    # Duplicate/nonfinite JSON is refused by the common reader for each line.
    # Avoid temporary evidence writes: same strict parsing policy in memory.
    def pairs(items):
        value = {}
        for k, v in items:
            if k in value:
                raise ValueError('Duplicate JSON key')
            value[k] = v
        return value
    def finite(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite JSON')
        return result
    return json.loads(content, object_pairs_hook=pairs, parse_float=finite,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _jsonl(path):
    return [_decode_json(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _state_contains(value, expected):
    if _same(value, expected):
        return True
    if isinstance(value, dict):
        return any(_state_contains(v, expected) for v in value.values())
    if isinstance(value, list):
        return any(_state_contains(v, expected) for v in value)
    return False


def _verify_results(messages, calls):
    """Compare retained native result payloads to independent backend results."""
    visible = []
    for message in messages:
        for call in message.get('tool_calls', []):
            name = call['name']
            if not name.startswith('mcp__dolphinbench_apps__'):
                continue
            if name.removeprefix('mcp__dolphinbench_apps__') in MCP_METADATA:
                continue
            replies = [m for m in messages if m.get('role') == 'tool' and m.get('tool_call_id') == call['id']]
            if len(replies) != 1:
                raise ValueError('Unique retained tool-result witness required')
            content = replies[0]['content']
            if isinstance(content, str) and content.startswith('<untrusted_tool_result '):
                content = content.rstrip('\n')
                if not content.startswith('<untrusted_tool_result source="' + name + '">\n') or not content.endswith('\n</untrusted_tool_result>'):
                    raise ValueError('Native result wrapper target differs')
                content = content.split('\n\n', 1)[1].removesuffix('\n</untrusted_tool_result>')
            value = _decode_json(content) if isinstance(content, str) else content
            if isinstance(value, dict) and 'result' in value:
                payload = value['result']
                payload = _decode_json(payload) if isinstance(payload, str) else payload
                if 'structuredContent' in value:
                    structured = value['structuredContent']['result']
                    structured = _decode_json(structured) if isinstance(structured, str) else structured
                    if not _same(payload, structured):
                        raise ValueError('Native structured result disagrees')
                value = payload
            visible.append((name.removeprefix('mcp__dolphinbench_apps__'), value))
    if len(visible) != len(calls) or any(name != call['tool'] or not _same(value, call['result'])
            for (name, value), call in zip(visible, calls)):
        raise ValueError('Native tool results disagree with independent app log')


def reconstruct_129(parent, proofs, ledger, spec, default_sources, *, coverage_parent=None):
    """Rebuild exact export, never run tools, grade, or change completed=false."""
    from .export import export_interaction
    from harness.submission import check_messages, check_settings, grading_calls
    default_sources = sorted(map(Path, default_sources))
    if not default_sources:
        raise ValueError('Pinned application signature sources are required')
    coverage_parent = Path(parent if coverage_parent is None else coverage_parent).resolve()
    native = Path(parent) / 'native/tests/morgan/129'
    process_path = native / 'process.json'
    process = read(process_path)
    if process.get('exit_code') != 0:
        raise ValueError('Process success required; uncertain action cannot be replayed')
    events = [_decode_json(line) for line in process['stdout'].splitlines() if line.startswith('{')]
    results = [r for r in events if r.get('type') == 'result']
    if len(results) != 1 or results[0].get('exit_code') != 0:
        raise ValueError('Unique successful native result required')
    duration = results[0].get('duration_ms')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Missing native duration; supply original timestamp evidence; do not fabricate latency')
    api = verify_pin(proofs['api_witness'])
    session = results[0].get('session_id')
    api_events = _jsonl(api)
    if not session or not api_events or any(e.get('session_id') != session for e in api_events):
        raise ValueError('Native API witness belongs to another process session')
    shutdown_path = verify_pin(proofs['shutdown_witness']) if 'shutdown_witness' in proofs else None
    shutdown = _jsonl(shutdown_path) if shutdown_path else []
    if shutdown_path and (not shutdown or any(e.get('format') != 'atmem-hermes-shutdown-observation-v1' for e in shutdown)):
        raise ValueError('Native shutdown witness missing')
    for event in shutdown:
        drain = event.get('drain', {})
        if (drain.get('status') != 'drained' or any(drain.get(k) != 0 for k in
                ('abandoned_writes', 'abandoned_prefetches', 'active_tasks'))
                or not isinstance(event.get('providers'), list) or any(
                    p.get('name') != 'atmem' or p.get('pending_writes') != 0 or p.get('write_errors') != 0
                    for p in event['providers'])):
            raise ValueError('Uncertain native shutdown')
    if (native / 'context-delivery.json').exists() and any(e['providers'] for e in shutdown):
        if read(native / 'context-delivery.json').get('mode') == 'installed AtMem API to native ephemeral_system_prompt':
            raise ValueError('Native provider activity conflicts with original API context delivery')
    if not any(e['providers'] for e in shutdown):
        delivery_path = (verify_pin(proofs['context_delivery']) if 'context_delivery' in proofs
                         else native / 'context-delivery.json' if shutdown_path else None)
        if delivery_path != native / 'context-delivery.json':
            raise ValueError('Original context-delivery proof required in place of absent native provider hook')
        delivery = read(delivery_path)
        if (delivery.get('mode') != 'installed AtMem API to native ephemeral_system_prompt'
                or delivery.get('actual_native_process_exit_code') != 0):
            raise ValueError('Empty provider shutdown requires original API context-delivery evidence')
    outcome_path = native / 'app-evidence/outcome.json'
    outcome = read(outcome_path)
    if outcome.get('completed') is not False or len(outcome.get('artifacts', [])) != 2:
        raise ValueError('Expected original incomplete outcome and both independent snapshots')
    retained = {verify_pin(p).name: verify_pin(p) for p in outcome['artifacts']}
    if set(retained) != {'state.json', 'calls.jsonl'}:
        raise ValueError('Independent state/log snapshots required')
    # Independently retained live app files must match the journal snapshot bytes.
    intent_path = native / 'app-evidence/intent.json'
    intent = read(intent_path)
    state_path, log_path = verify_pin(proofs['independent_state']), verify_pin(proofs['independent_log'])
    if (str(state_path) != intent['state'] or str(log_path) != intent['log'] or
            sha(state_path) != sha(retained['state.json']) or sha(log_path) != sha(retained['calls.jsonl'])):
        raise ValueError('Independent state/log do not match original intent and snapshots')
    calls = [{k: c[k] for k in ('tool', 'args', 'result')} for c in _jsonl(log_path)]
    state = read(state_path)
    bookings = [c for c in calls if c['tool'].startswith('book_')]
    if [c['tool'] for c in bookings] != ['book_flight', 'book_hotel']:
        raise ValueError('Missing, repeated or uncertain booking actions')
    for c in bookings:
        result = c['result']
        if (result.get('ok') is not True or not result.get('booking', {}).get('id')
                or not _state_contains(state, result['booking'])):
            raise ValueError('Booking result absent from independent persisted state')
    artifacts = [process_path, api, outcome_path, intent_path, Path(ledger),
                 state_path, log_path, *retained.values(), *default_sources]
    if shutdown_path:
        artifacts.append(shutdown_path)
    if (native / 'context-delivery.json').exists():
        artifacts.append(native / 'context-delivery.json')
    # Only a closed, standalone inherited backup is accepted here. Immutable
    # reading cannot create or mutate sidecars in the retained evidence bundle.
    if Path(str(ledger) + '-wal').exists() and Path(str(ledger) + '-wal').stat().st_size:
        raise ValueError('Offline recovery requires a standalone SQLite backup, not a live WAL database')
    with closing(sqlite3.connect(Path(ledger).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        transports = sorted((native / 'calls').rglob('transport.json'))
        if not transports:
            raise ValueError('Missing task129 gateway transports')
        all_transports = list((coverage_parent / 'native/tests').glob('*/*/calls/tests/*/transport.json'))
        all_transports += list((coverage_parent / 'judge-calls').glob('judge/*/transport.json'))
        all_transports += list((coverage_parent / 'launches').glob('*/judge-calls/judge/*/transport.json'))
        all_ids = [p.parent.name for p in all_transports]
        ledger_ids = {r[0] for r in db.execute('SELECT call_id FROM calls')}
        if len(all_ids) != len(set(all_ids)) or set(all_ids) != ledger_ids:
            raise ValueError('Ledger/gateway coverage is not a complete bijection')
        artifacts.extend(all_transports)
        for transport in transports:
            directory = transport.parent
            meta, request, response = read(transport), read(directory / 'request.json'), read(directory / 'response.json')
            if request.get('model') != 'openai/gpt-5.6-luna' or request.get('reasoning_effort') != 'high':
                raise ValueError('Retained reader settings differ from frozen Luna/high')
            row = db.execute('SELECT state,request_sha256,response_sha256 FROM calls WHERE call_id=?', (directory.name,)).fetchone()
            if (meta.get('call_id') != directory.name or meta.get('phase') != 'tests'
                    or row != ('completed', fingerprint(request), fingerprint(response['response']))):
                raise ValueError('Missing completed budget/gateway proof')
            artifacts.extend([transport, directory / 'request.json', directory / 'response.json'])
    exported = export_interaction(native / 'calls', api, app_calls=calls, default_source_paths=default_sources)
    _verify_results(exported['messages'], calls)
    dated = '[' + spec['narrative_anchor_date'] + '] ' + spec['test']
    if [m.get('content') for m in exported['messages'] if m.get('role') == 'user'] != [dated]:
        raise ValueError('Original dated user boundary differs')
    check_settings(exported['settings'], RECOVERED)
    check_messages(exported['messages'], RECOVERED)
    evidence = {'settings': exported['settings'], 'row': {'persona': 'morgan', 'test_id': '129',
        'messages': exported['messages'], 'duration_ms': duration, 'app_calls': calls},
        'attempts': [{'auxiliary_calls': exported['auxiliary_calls']}]}
    # Preserve the upstream serialized-argument validator too. Independent
    # semantics/results were separately proved above by normalizer/results/state.
    grading_calls(evidence['row'], RECOVERED)
    receipt = {'schema': 'dolphin-offline-recovery-v1', 'task': RECOVERED,
        'reconstruction_parent': str(Path(parent).resolve()),
        'coverage_parent': str(coverage_parent),
        'original_outcome_unchanged': pin(outcome_path), 'proofs': [pin(p) for p in artifacts],
        'duration_basis': 'original native result duration_ms; excludes controller overhead, not exact adapter latency',
        'shutdown_basis': ('retained native shutdown observation' if shutdown_path else
            'original installed API context-delivery disables native memory provider; no provider shutdown hook applies'),
        'provider_calls': 0, 'app_calls_dispatched': 0, 'regraded': False,
        'export_sha256': identity(evidence), 'proof_descriptor': proofs}
    return evidence, receipt


@lru_cache(maxsize=4)
def _cached_release(root, digest):
    sys.path.insert(0, root)
    from harness.submission import read_release
    # Recovery needs boundary/grade metadata, never app-state setup. Keep the
    # exact relevant values without retaining/copying600 large mock states at
    # every forwarding guard. Actual execution still uses upstream read_release.
    keys = ('id', 'test', 'narrative_anchor_date', 'grade')
    return {p: {'tests': [{k: test[k] for k in keys} for test in value['tests']]}
            for p, value in read_release(Path(root)).items()}


@lru_cache(maxsize=4)
def _installed_release(product_python, site, root, digest):
    # Fixed offline parser command. No adapter, provider, grader or app dispatch.
    code = ('import sys,json;sys.path.append(sys.argv[1]);sys.path.insert(0,sys.argv[2]);'
            'from harness.submission import read_release;from pathlib import Path;'
            'r=read_release(Path(sys.argv[2]));'
            'keys=("id","test","narrative_anchor_date","grade");'
            'print(json.dumps({p:{"tests":[{k:t[k] for k in keys} for t in v["tests"]]} for p,v in r.items()}))')
    result = subprocess.run([product_python, '-I', '-B', '-c', code, site, root],
                            check=True, capture_output=True, text=True, timeout=120)
    return json.loads(result.stdout)


def _release(condition):
    # Homebrew's parent Python may have a different minor ABI from the frozen
    # installed product. Run only the offline release parser in the matching
    # interpreter; never append incompatible native dependency packages.
    root = condition['bindings']['upstream_root']
    if root not in sys.path:
        sys.path.insert(0, root)
    site = condition['bindings']['controller_site']
    product = condition['bindings']['product_python']
    digest = condition['inputs']['upstream_manifest']['sha256']
    if Path(sys.executable).resolve() != Path(product).resolve():
        return copy.deepcopy(_installed_release(product, site, root, digest))
    if site not in sys.path:
        sys.path.append(site)
    return copy.deepcopy(_cached_release(root, digest))


def _default_sources(condition):
    root = Path(condition['bindings']['upstream_root'])
    manifest = read(condition['inputs']['upstream_manifest']['path'])['files']
    paths = sorted((root / 'mock_mcp').glob('repair*.py'))
    if not paths or any(manifest.get(str(p.relative_to(root))) != sha(p) for p in paths):
        raise ValueError('Application signature source differs from pinned upstream manifest')
    return paths


def _historical_epoch(parent, old):
    """Validate prior epoch as historical evidence after another source repair.

    This does not admit the prior source for execution. The new condition must
    independently pass ordinary admission and fresh qualification.
    """
    path = Path(parent) / 'epoch-transition.json'
    if not path.exists():
        return None
    prior = read(path)
    if (prior.get('schema') != 'dolphin-recovery-epoch-v1'
            or prior.get('new_condition_sha256') != identity(old)
            or prior.get('lineage') != lineage(prior.get('harness_revisions'))):
        raise ValueError('Invalid prior epoch history')
    verify_pin(prior['condition'])
    ancestor, changed = verify_transition(verify_pin(prior['historical_bundle']), old)
    if changed != prior['changed_sources'] or identity(ancestor) != prior['old_condition_sha256']:
        raise ValueError('Prior epoch source history differs')
    for entry in prior['inherited'] + prior['copies'] + [prior['recovery'], prior['inherited_budget']]:
        verify_pin(entry)
    recovered = read(prior['recovery']['path'])
    for entry in recovered['proofs'] + [recovered['evidence']]:
        verify_pin(entry)
    preflight_resume(parent, old)
    campaign = {**read(old['inputs']['options']['path'])['campaign_identity'], 'cap_usd': 10}
    verify_inherited_budget(prior['inherited_budget']['path'], Path(parent) / 'budget.db', campaign)
    return prior


def prepare_epoch(bundle_path, condition_path, receipts, parent, output, proofs_path):
    condition = admit(condition_path, receipts, 'pilot')
    old, changed = verify_transition(bundle_path, condition)
    parent, output = Path(parent).resolve(), Path(output).resolve()
    if output == parent or output.is_relative_to(parent) or parent.is_relative_to(output):
        raise ValueError('Separate recovery output required')
    if read(parent / 'execution-condition.json') != old:
        raise ValueError('Parent condition differs from historical bytes')
    if output.exists():
        raise FileExistsError('Epoch already exists; inspect/verify it, never re-import or reset')
    saved = {p.parent.name + '/' + p.stem for p in (parent / 'tests').glob('*/*.json') if not p.name.startswith('._')}
    grades = {p.parent.name + '/' + p.stem for p in (parent / 'grades').glob('*/*.json') if not p.name.startswith('._')}
    inflight = {p.parent.name + '/' + p.stem for p in (parent / 'tests').glob('*/*.inflight') if not p.name.startswith('._')}
    prior = _historical_epoch(parent, old)
    revisions = 2 if prior is None else prior['harness_revisions'] + 1
    lineage(revisions)
    selected = {k for group in read(condition['inputs']['selection']['path'])['groups'].values() for k in group}
    if prior is None:
        valid_inventory = saved == IMPORTED and grades == IMPORTED and inflight == {RECOVERED}
    else:
        valid_inventory = (IMPORTED | {RECOVERED} <= saved <= selected and
                           IMPORTED <= grades <= saved and not inflight)
    if not valid_inventory:
        raise ValueError('Unexpected parent execution/grade/inflight inventory; manual reconciliation required')
    parent_pins = inventory(parent)
    bundle_pins = [pin(bundle_path), pin(proofs_path)]
    output.mkdir(parents=True)
    save(output / 'epoch-intent.json', {'parent': str(parent), 'new_condition': pin(condition_path),
                                      'historical_bundle': pin(bundle_path), 'no_replay': True})
    campaign = copy.deepcopy(read(condition['inputs']['options']['path'])['campaign_identity'])
    campaign['cap_usd'] = 10
    ledger_pins = snapshot_budget(parent / 'budget.db', output / 'budget.db', campaign)
    copy_exact(output / 'budget.db', output / 'inherited-budget.db')
    release = _release(condition)
    for key in saved:
        persona, item = key.split('/')
        imported_spec = next(s for s in release[persona]['tests'] if str(s['id']).zfill(3) == item)
        if key in grades:
            checks = read(parent / 'grades' / (key + '.json'))['checks']
            expected = len(imported_spec['grade']['config']['assertions'])
            if len(checks) != expected or any(type(c.get('passed')) is not bool or c.get('check') != i for i, c in enumerate(checks)):
                raise ValueError('Inherited grade is incomplete: ' + key)
        blocked = any(a.get('gate_blocked') is True for a in read(parent / 'tests' / (key + '.json')).get('attempts', []))
        if blocked:
            if read(parent / 'native/tests' / key / 'pre-action-ruling.json').get('reason') == 'authorized':
                raise ValueError('Inherited refusal lacks policy evidence: ' + key)
            continue
        outcome = read(parent / 'native/tests' / key / 'app-evidence/outcome.json')
        recovered = prior is not None and key == RECOVERED
        if (outcome.get('completed') is not True and not recovered) or len(outcome.get('artifacts', [])) != 2:
            raise ValueError('Inherited interaction is not complete: ' + key)
        for entry in outcome['artifacts']:
            verify_pin(entry)
    spec = next(s for s in release['morgan']['tests'] if str(s['id']).zfill(3) == '129')
    default_sources = _default_sources(condition)
    origin = parent if prior is None else Path(read(prior['recovery']['path'])['reconstruction_parent'])
    evidence, recovery = reconstruct_129(origin, read(proofs_path), output / 'inherited-budget.db', spec, default_sources,
                                         coverage_parent=parent)
    # Copy evidence, never live listeners, old admissions, PID tokens or app workspaces.
    copies = []
    for p in inherited_copy_sources(parent):
        dest = output / p.relative_to(parent)
        copy_exact(p, dest)
        copies.append(pin(dest))
    if RECOVERED in saved:
        if read(output / 'tests/morgan/129.json') != evidence:
            raise ValueError('Prior recovered execution changed; refuse re-export replacement')
    else:
        save(output / 'tests/morgan/129.json', evidence)
    recovery['evidence'] = pin(output / 'tests/morgan/129.json')
    recovery['original_condition_sha256'] = (identity(old) if prior is None else
        read(prior['recovery']['path'])['original_condition_sha256'])
    save(output / 'recovery-129.json', recovery)
    save(output / 'execution-condition.json', condition)
    for entry in parent_pins + ledger_pins:
        verify_pin(entry)
    transition = {'schema': 'dolphin-recovery-epoch-v1', 'lineage': lineage(revisions), 'harness_revisions': revisions,
        'parent': str(parent), 'historical_bundle': pin(bundle_path), 'condition': pin(condition_path),
        'old_condition_sha256': identity(old), 'new_condition_sha256': identity(condition),
        'changed_sources': changed, 'source_changes': source_changes(bundle_path, condition, changed),
        'inherited': parent_pins + ledger_pins + bundle_pins,
        'copies': copies, 'inherited_budget': pin(output / 'inherited-budget.db'),
        'recovery': pin(output / 'recovery-129.json'),
        'imported_ids': sorted(saved), 'imported_grade_ids': sorted(grades), 'reconstructed_id': RECOVERED,
        'execution_conditions': {key: (prior or {}).get('execution_conditions', {}).get(key, identity(old))
                                 for key in saved | {RECOVERED}},
        'grade_conditions': {key: (prior or {}).get('grade_conditions', {}).get(key, identity(old)) for key in grades},
        'original_score_unchanged': '390/600', 'conditional_75_4_not_full_score': True,
        'scientific_configuration_unchanged': True, 'not_single_harness_revision': True}
    save(output / 'epoch-transition.json', transition)
    verify_epoch(output, condition_path)
    return transition


def verify_epoch(output, condition_path, *, inflight_since=None):
    output = Path(output).resolve()
    transition = read(output / 'epoch-transition.json')
    condition = load_condition(condition_path)
    if (transition.get('schema') != 'dolphin-recovery-epoch-v1'
            or transition.get('lineage') != lineage(transition.get('harness_revisions'))):
        raise ValueError('Invalid recovery epoch')
    verify_pin(transition['condition'])
    if pin(condition_path) != transition['condition'] or identity(condition) != transition['new_condition_sha256']:
        raise ValueError('Recovery condition changed')
    old, changed = verify_transition(verify_pin(transition['historical_bundle']), condition)
    if changed != transition['changed_sources'] or identity(old) != transition['old_condition_sha256']:
        raise ValueError('Recovery source transition changed')
    if transition['source_changes'] != source_changes(transition['historical_bundle']['path'], condition, changed):
        raise ValueError('Old/new source digest transition changed')
    if read(output / 'execution-condition.json') != condition:
        raise ValueError('Epoch execution condition differs')
    for entry in transition['inherited'] + transition['copies']:
        verify_pin(entry)
    parent = Path(transition['parent'])
    parent_files = inventory(parent)
    inherited_by_path = {p['path']: p for p in transition['inherited']}
    if any(inherited_by_path.get(p['path']) != p for p in parent_files):
        raise ValueError('Inherited artifact inventory is incomplete or changed')
    expected_copies = [{'path': str(output / p.relative_to(parent)), 'sha256': sha(p)}
                       for p in inherited_copy_sources(parent)]
    if sorted(expected_copies, key=lambda p: p['path']) != sorted(transition['copies'], key=lambda p: p['path']):
        raise ValueError('Inherited copy inventory is incomplete or changed')
    budget = verify_pin(transition['inherited_budget'])
    campaign = copy.deepcopy(read(condition['inputs']['options']['path'])['campaign_identity'])
    campaign['cap_usd'] = 10
    verify_inherited_budget(budget, output / 'budget.db', campaign, inflight_since=inflight_since)
    recovery = read(verify_pin(transition['recovery']))
    for entry in recovery['proofs']:
        verify_pin(entry)
    verify_pin(recovery['evidence'])
    release = _release(condition)
    spec = next(s for s in release['morgan']['tests'] if str(s['id']).zfill(3) == '129')
    sources = _default_sources(condition)
    rebuilt, proof = reconstruct_129(recovery['reconstruction_parent'], recovery['proof_descriptor'], budget, spec, sources,
                                     coverage_parent=recovery['coverage_parent'])
    if (identity(rebuilt) != recovery['export_sha256'] or rebuilt != read(recovery['evidence']['path'])
            or any(recovery.get(k) != proof[k] for k in proof)):
        raise ValueError('Recovery receipt does not reproduce exact offline export')
    if (not IMPORTED <= set(transition['imported_ids']) or transition['reconstructed_id'] != RECOVERED
            or set(transition['execution_conditions']) != set(transition['imported_ids']) | {RECOVERED}
            or set(transition['grade_conditions']) != set(transition['imported_grade_ids'])):
        raise ValueError('Inherited task inventory changed')
    return transition


@contextmanager
def epoch_lock(output):
    path = Path(output) / '.recovery.lock'
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Recovery epoch is already running') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def preflight_resume(output, condition):
    """Refuse uncertainty before even starting a fresh local provider listener."""
    output = Path(output)
    selected = {k for group in read(condition['inputs']['selection']['path'])['groups'].values() for k in group}
    for folder, extension in (('tests', '.inflight'), ('tests', '.returned')):
        for p in (output / folder).glob('*/*' + extension):
            if p.name.startswith('._'):
                continue
            if extension == '.inflight' or not p.with_suffix('.json').exists():
                raise ValueError('Uncertain saved interaction requires reconciliation: ' + str(p))
    for folder, target in (('dispatch-intents', 'tests'), ('grade-intents', 'grades')):
        for p in (output / folder).glob('*/*.json'):
            key = p.parent.name + '/' + p.stem
            if key not in selected or not (output / target / (key + '.json')).exists():
                raise ValueError('Uncertain ' + folder + ': ' + key)
    for key in selected:
        execution = output / 'tests' / (key + '.json')
        apps = output / 'apps' / key
        if not execution.exists() and apps.exists() and any(apps.iterdir()):
            raise ValueError('Uncertain app workspace cannot be reset: ' + key)


def initialize_run_identity(output, condition_path, sliced_release, configuration):
    """Bind imported evidence to this epoch before Runner/provider startup.

    The recovery entry point holds epoch_lock throughout initialization and
    execution. Preparation deliberately leaves run.json absent: its identity
    must describe the new sliced release and actual executing adapter, never
    the parent's harness. Ordinary Runner initialization remains unchanged.
    """
    output = Path(output)
    verify_epoch(output, condition_path)  # Includes science and inherited accounting.
    condition = load_condition(condition_path)
    preflight_resume(output, condition)
    from harness.runner import digest
    fingerprint = {'version': 1, 'release': digest(sliced_release), 'configuration': configuration}
    path = output / 'run.json'
    if path.is_symlink():
        raise ValueError('Recovery run identity must be a regular local record')
    if path.exists():
        if read(path) != fingerprint:
            raise ValueError('Run inputs changed; use a new output directory')
    else:
        save(path, fingerprint)  # O_EXCL, file fsync and directory fsync; never replace.


def execute_once(runner, output, persona, spec, *, boundary):
    """Intent persists across crash; a saved execution is never sent to _apps."""
    output = Path(output)
    item = str(spec['id']).zfill(3)
    execution, grade = output / 'tests' / persona / (item + '.json'), output / 'grades' / persona / (item + '.json')
    boundary()
    if grade.exists():
        if not execution.exists():
            raise ValueError('Saved grade without execution')
        return read(grade)
    if execution.exists():
        evidence = read(execution)
    else:
        save(output / 'dispatch-intents' / persona / (item + '.json'), {'task': persona + '/' + item,
            'condition': pin(output / 'execution-condition.json'), 'unknown_effect_requires_escalation': True})
        evidence = runner._execute('tests', persona, spec)
        if not execution.exists():
            save(execution, evidence)
        elif read(execution) != evidence:
            raise ValueError('Returned execution differs from saved evidence; unknown effect, escalate without replay')
    boundary()
    # A failed/unknown judge request is also never silently repeated.
    save(output / 'grade-intents' / persona / (item + '.json'), {'execution': pin(execution)})
    value = runner._grade(spec, evidence)
    save(grade, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    history = commands.add_parser('verify-history')
    history.add_argument('--bundle', type=Path, required=True)
    prepare = commands.add_parser('prepare')
    for name in ('bundle', 'condition', 'receipts', 'parent', 'output', 'proofs'):
        prepare.add_argument('--' + name, type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--condition', type=Path, required=True)
    verify.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'verify-history':
        old, _ = historical_condition(args.bundle)
        print(json.dumps({'historical_bytes_verified': True, 'condition_sha256': identity(old), 'admitted_for_execution': False}))
    elif args.command == 'prepare':
        prepare_epoch(args.bundle, args.condition, args.receipts, args.parent, args.output, args.proofs)
        print(json.dumps({'epoch_prepared': True, 'provider_calls': 0, 'app_calls_dispatched': 0}))
    else:
        verify_epoch(args.output, args.condition)
        print(json.dumps({'epoch_verified': True, 'provider_calls': 0, 'app_calls_dispatched': 0}))


if __name__ == '__main__':
    main()
