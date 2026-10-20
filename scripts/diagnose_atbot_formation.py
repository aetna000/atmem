"""One separately budgeted public-history AtBot diagnostic, not a benchmark score.

Uses the installed companion's unchanged extraction prompt/schema/validation.
Never writes canonical memory or changes the running campaign configuration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--confirm-paid-call', action='store_true')
    parser.add_argument('--record-error-probe', action='store_true',
                        help='One explicit second request after an HTTP 400, sharing the same US$0.04 ledger')
    parser.add_argument('--patched-wire-probe', action='store_true',
                        help='One final request with the separately installed provider wire fix, sharing the same ledger')
    args = parser.parse_args()
    if not args.confirm_paid_call:
        parser.error('Explicit paid-call flag required')
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    if args.record_error_probe and args.patched_wire_probe:
        parser.error('Select only one explicit probe')
    if args.patched_wire_probe:
        if not (root / 'upstream-error-probe.json').exists():
            raise ValueError('Patched-wire probe requires the preserved schema-rejection evidence')
        (root / 'calls-patched-wire').mkdir(mode=0o700)
    elif args.record_error_probe:
        prior = list((root / 'calls').rglob('error.json'))
        if len(prior) != 1 or json.loads(prior[0].read_text()).get('http_status') != 400:
            raise ValueError('Error probe requires the preserved first HTTP 400 receipt')
        (root / 'calls-error-probe').mkdir(mode=0o700)
    else:
        root.mkdir(mode=0o700)  # Refuse implicit replay of an existing diagnostic.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from benchmarks.dolphinbench.gateway import Gateway, Handler, save_new
    from benchmarks.dolphinbench.recording import BudgetLedger
    from scripts.openrouter_azure_sol import load_key
    from atbot import __version__
    from atbot.companion import CompanionRuntime
    from atbot.config import AtBotConfig, ProviderConfig

    class MetadataHandler(Handler):
        def do_GET(self):
            if self.path != '/v1/models':
                return self.error_response(404, 'Only declared model metadata is exposed')
            # AtBot's normal availability probe checks HTTP status, not model
            # reasoning. The Azure route was separately queried before this call.
            raw = json.dumps({'object': 'list', 'data': [{'id': self.server.model}]}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    identity = {'diagnostic': 'installed-atbot-on-one-public-history-message',
                'benchmark_score': False, 'canonical_writes': False,
                'model': 'openai/gpt-4.1-mini', 'maximum_additional_usd': 0.04}
    output_name = 'calls-patched-wire' if args.patched_wire_probe else 'calls-error-probe' if args.record_error_probe else 'calls'
    gateway = Gateway(key=load_key(args.env_file), output=root / output_name, ledger_path=root / 'budget.db',
        campaign_identity=identity, cap_usd=0.04, phase='qualification',
        model=identity['model'], input_per_million=1, output_per_million=5,
        output_token_cap=1024 if args.patched_wire_probe else 1536)
    gateway.RequestHandlerClass = MetadataHandler
    actual_urlopen = urllib.request.urlopen
    if args.record_error_probe or args.patched_wire_probe:
        def observed_urlopen(request, *args, **kwargs):
            try:
                return actual_urlopen(request, *args, **kwargs)
            except urllib.error.HTTPError as exc:
                if getattr(request, 'full_url', '').startswith('https://openrouter.ai/'):
                    body = exc.read(32000)
                    if gateway.key.encode() in body:
                        raise ValueError('Secret screen failed for upstream diagnostic')
                    save_new(root / ('upstream-patched-wire-error.json' if args.patched_wire_probe else 'upstream-error-probe.json'), {'http_status': exc.code,
                        'body': body.decode(errors='replace'), 'diagnostic_only': True})
                raise
        urllib.request.urlopen = observed_urlopen
    gateway.start()
    os.environ['ATMEM_DIAGNOSTIC_PROXY_KEY'] = gateway.local_token
    try:
        record = json.loads(Path('/Volumes/AtMemDolphin/campaign-atmem-239-frozen/ingestion/morgan/000001.json').read_text())
        message = next(m['content'] for m in record['row']['messages'] if m['role'] == 'user')
        runtime = CompanionRuntime(AtBotConfig(remote_egress_allowed=True,
            providers=[ProviderConfig(name='openrouter-azure-diagnostic', kind='openai-compatible',
                model=identity['model'], endpoint=gateway.base_url.removesuffix('/v1'),
                api_key_env='ATMEM_DIAGNOSTIC_PROXY_KEY', egress_class='remote')]))
        result = runtime.propose_memories(message, remote=True)
        import atbot.providers.openai_compatible as wire
        save_new(root / 'result.json', {'identity': identity, 'atbot_version': __version__,
            'patched_wire_probe': args.patched_wire_probe,
            'wire_module_sha256': hashlib.sha256(Path(wire.__file__).read_bytes()).hexdigest(),
            'source': 'public DolphinBench Morgan ingestion 000001', 'result': result})
        book = BudgetLedger(root / 'budget.db', cap_usd=0.04, identity=identity)
        try:
            print(json.dumps({'diagnostic_only': True, 'proposal_count': len(result['proposals']),
                'provider': result['interpreter']['provider'], 'canonical_writes': 0,
                'accounting': book.totals()}), flush=True)
        finally:
            book.close()
    finally:
        gateway.stop()
        urllib.request.urlopen = actual_urlopen
        os.environ.pop('ATMEM_DIAGNOSTIC_PROXY_KEY', None)


if __name__ == '__main__':
    main()
