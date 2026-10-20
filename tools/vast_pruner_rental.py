"""One benchmark-owned, budget-bounded Vast rental. Never log credentials."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

BASE = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks')
ROOT = Path(os.environ.get('ATMEM_PRUNER_GPU_ROOT', str(BASE / 'swe-pruner-gpu-20261020')))
if ROOT.parent != BASE or ROOT.name not in {'swe-pruner-gpu-20261020', 'swe-pruner-gpu-20261020-cached-original', 'swe-pruner-gpu-20261020-fast-host'}:
    raise ValueError('explicit benchmark-owned rental root required')
STATE = ROOT / 'rental.json'
IMAGE = 'vastai/pytorch@sha256:4f5768d796e2c30a966ae4f54a7870a012e4b13a3d899fb46c0dbb3b45feff86'


def api(method, path, payload=None):
    values = {}
    for line in Path(os.environ.get('ATMEM_PUBLISH_ENV', str(Path(__file__).resolve().parents[1] / '.env.atmem-c709e'))).read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name, value = line.split('=', 1)
            parts = shlex.split(value, comments=True)
            values[name.strip().removeprefix('export ')] = parts[0] if parts else ''
    url = 'https://console.vast.ai' + path
    request = urllib.request.Request(url, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + values['VAST_AI'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response)


def save(value):
    temporary = STATE.with_name(STATE.name + '.' + str(os.getpid()) + '.tmp')
    with temporary.open('w') as out:
        json.dump(value, out, indent=2)
    os.replace(temporary, STATE)


def instances():
    query = urllib.parse.urlencode({'limit': 100, 'select_filters': '{}'})
    result = api('GET', '/api/v1/instances/?' + query)
    if result.get('next_token'):
        raise RuntimeError('unexpected paginated account; inspect before renting')
    return result.get('instances') or []


def search():
    query = {'verified': {'eq': True}, 'rentable': {'eq': True}, 'rented': {'eq': False},
             'num_gpus': {'eq': 1}, 'gpu_ram': {'gte': 16000}, 'compute_cap': {'gte': 800, 'lt': 1000},
             'reliability2': {'gte': 0.99}, 'disk_space': {'gte': 40}, 'inet_down': {'gte': 100},
             'direct_port_count': {'gte': 1}, 'cuda_max_good': {'gte': 12.9},
             'dph_total': {'lte': 0.35}, 'inet_down_cost': {'lte': 0.01}, 'inet_up_cost': {'lte': 0.01},
             'type': 'on-demand', 'allocated_storage': 32,
             'order': [['dph_total', 'asc']], 'limit': 15}
    if ROOT.name.endswith('-cached-original'):
        query.update(machine_id={'eq': 92580}, reliability2={'gte': 0.98})
    if ROOT.name.endswith('-fast-host'):
        query.update(cpu_cores_effective={'gte': 8}, disk_bw={'gte': 1500}, inet_down={'gte': 500},
                     dph_total={'lte': 0.60}, is_vm_deverified={'eq': False})
    result = api('POST', '/api/v0/bundles/', query)
    offers = result.get('offers') or []
    if not offers:
        raise RuntimeError('no qualifying affordable Ampere/Ada offer')
    (ROOT / 'offers.json').write_text(json.dumps(offers, indent=2))
    return offers


def destroy(state, reason):
    if state.get('destroyed'):
        return state
    identity = state['instance_id']
    live = [x for x in instances() if x['id'] == identity]
    if live and live[0].get('label') != state['label']:
        raise RuntimeError('instance ownership label mismatch; no deletion attempted')
    result = api('DELETE', f'/api/v0/instances/{identity}/') if live else {'already_absent': True}
    if any(x['id'] == identity for x in instances()):
        raise RuntimeError('destroy not yet confirmed; retry exact owned instance')
    state.update(destroyed=True, destroy_reason=reason, destroy_response=result,
                 ended_epoch=time.time(), ending_credit=api('GET', '/api/v0/users/current/').get('credit'))
    save(state)
    return state


def main():
    global ROOT, STATE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['rent', 'status', 'destroy', 'watch'])
    parser.add_argument('--fallback', action='store_true', help='one separate second-host attempt after confirmed first teardown')
    parser.add_argument('--resume-uncreated', action='store_true', help='refresh an unavailable offer only when no instance was created')
    args = parser.parse_args()
    previous = None
    if ROOT.name.endswith(('-cached-original', '-fast-host')):
        previous = json.loads((BASE / 'swe-pruner-gpu-20261020/rental.json').read_text())
        fallback = json.loads((BASE / 'swe-pruner-gpu-20261020-fallback/rental.json').read_text())
        if not previous.get('destroyed') or not fallback.get('destroyed'):
            raise RuntimeError('prior rentals must be confirmed destroyed before cache reuse')
    if args.fallback:
        previous = json.loads(STATE.read_text())
        if not previous.get('destroyed'):
            raise RuntimeError('destroy and verify original rental before fallback')
        ROOT = ROOT.with_name(ROOT.name + '-fallback')
        STATE = ROOT / 'rental.json'
    if args.action == 'rent':
        if args.resume_uncreated:
            old = json.loads(STATE.read_text())
            if old.get('instance_id') or any(x.get('label') == old['label'] for x in instances()):
                raise RuntimeError('existing instance prevents uncreated-offer refresh')
            (ROOT / ('unavailable-offer-' + str(old['offer']['id']) + '.json')).write_text(json.dumps(old, indent=2))
        ROOT.mkdir(mode=0o700, exist_ok=args.resume_uncreated)
        existing = instances()
        credit = api('GET', '/api/v0/users/current/').get('credit')
        if credit is None or credit < 3:
            raise RuntimeError('insufficient existing credit; no top-up authorized')
        offers = search()
        selected = offers[0]
        # Conservative 90-minute compute+disk and 30 GB in + 1 GB out reserve.
        bound = 1.5 * (selected['dph_total'] + 32 * selected['storage_cost'] / 720)
        bound += 30 * selected['inet_down_cost'] + selected['inet_up_cost']
        if bound >= 3:
            raise RuntimeError('planned all-in reservation exceeds owner ceiling')
        anchor = previous['starting_credit'] if previous else credit
        if anchor-credit+bound >= 3:
            raise RuntimeError('combined attempts would exceed campaign ceiling')
        state = {'label': ROOT.name.replace('swe-pruner-gpu-', 'atmem-swe-pruner-'), 'budget_usd': 3,
                 'starting_credit': anchor, 'existing_instance_ids': [x['id'] for x in existing],
                 'offer': selected, 'image': IMAGE, 'planned_upper_bound_usd': bound,
                 'created_epoch': time.time(), 'deadline_epoch': time.time() + 5400,
                 'destroyed': False}
        save(state)
        rejected = []
        result = None
        for selected in offers[:8]:
            bound = 1.5 * (selected['dph_total'] + 32 * selected['storage_cost'] / 720)
            bound += 30 * selected['inet_down_cost'] + selected['inet_up_cost']
            if anchor-credit+bound >= 3:
                continue
            state.update(offer=selected, planned_upper_bound_usd=bound, unavailable_offers=rejected)
            save(state)
            try:
                result = api('PUT', f'/api/v0/asks/{selected["id"]}/',
                    {'client_id': 'me', 'image': IMAGE, 'disk': 32, 'label': state['label'],
                     'runtype': 'ssh_direc ssh_proxy', 'env': {}, 'cancel_unavail': True})
                break
            except urllib.error.HTTPError as exc:
                error = json.loads(exc.read())
                if exc.code != 400 or 'no_such_ask' not in str(error.get('msg', '')):
                    raise RuntimeError('rental rejected: ' + str(error.get('error', exc.code))) from None
                rejected.append({'offer_id': selected['id'], 'error': 'no_such_ask'})
        if result is None:
            raise RuntimeError('all bounded candidates unavailable; no instance created')
        if not result.get('success') or not result.get('new_contract'):
            raise RuntimeError('creation rejected; no successful contract ID returned')
        state.update(instance_id=result['new_contract'],
                     create_response={k: result[k] for k in ('success', 'new_contract')})
        save(state)
        with (ROOT / 'watchdog.log').open('x') as log:
            watcher = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watch', *(['--fallback'] if args.fallback else [])],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        state['watchdog_pid'] = watcher.pid
        save(state)
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(ROOT / 'ssh_key')], check=True)
        attached = api('POST', f'/api/v0/instances/{state["instance_id"]}/ssh/',
                       {'ssh_key': (ROOT / 'ssh_key.pub').read_text().strip()})
        print(json.dumps({'instance_id': state['instance_id'], 'gpu': selected['gpu_name'],
                          'hourly_offer': selected['dph_total'], 'planned_upper_bound_usd': bound,
                          'ssh_attached': attached.get('success', False)}), flush=True)
        return
    state = json.loads(STATE.read_text())
    if args.action == 'destroy':
        closed = destroy(state, 'completed_or_failed_benchmark')
        print(json.dumps({k: closed.get(k) for k in ('instance_id', 'destroyed', 'ending_credit', 'destroy_reason')}))
    elif args.action == 'status':
        live = [x for x in instances() if x['id'] == state['instance_id']]
        fields = ('id', 'label', 'actual_status', 'status_msg', 'ssh_host', 'ssh_port',
                  'public_ipaddr', 'ports', 'dph_total', 'gpu_name', 'start_date')
        print(json.dumps([{k: x.get(k) for k in fields} for x in live], indent=2))
    else:
        while True:
            state = json.loads(STATE.read_text())
            if state.get('destroyed'):
                return
            # Credit delta is conservative if other owner workloads also spend.
            try:
                credit = api('GET', '/api/v0/users/current/').get('credit')
                if time.time() >= state['deadline_epoch'] or (credit is not None and state['starting_credit'] - credit >= 2.5):
                    destroy(state, 'deadline_or_budget_guard')
                    return
            except Exception as exc:
                print(json.dumps({'watchdog_retry': type(exc).__name__}), flush=True)
            time.sleep(20)


if __name__ == '__main__':
    main()
