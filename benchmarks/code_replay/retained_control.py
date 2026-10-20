"""Complete bounded worker transport retention, with recoverable heavy JSON."""
import base64
from hashlib import sha256
import json

from benchmarks.code_replay.result_transport import decode_result


def retain_control(save, identity, phase, proc):
    row = {'instance_id': identity, 'phase': phase, 'transport_exit': proc.returncode,
           'transport_failure': None, 'streams': {}}
    def chunks(kind, raw):
        receipts = []
        for offset in range(0, len(raw), 3_000_000):
            receipts.append(save(kind, {'instance_id': identity, 'phase': phase, 'offset': offset,
                'bytes_base64': base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
        return {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': receipts}
    for name, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
        row['streams'][name] = chunks('external.runtime_projection_chunk', raw)
    if proc.returncode == 0:
        try:
            control = json.loads(proc.stdout)
            if (control.get('exit_code') == 0 and not control.get('reason')
                and control.get('raw_output_truncated') is False):
                raw = base64.b64decode(control['raw_output_base64'], validate=True)
                if len(raw) != control['output_bytes']:
                    raise ValueError('worker transport byte count differs')
                worker = decode_result(raw)
                control['worker'] = worker
                decoded = json.dumps(worker, sort_keys=True, separators=(',', ':')).encode()
                if len(decoded) > 3_000_000:
                    row['decoded_worker_stream'] = chunks('external.runtime_projection_decoded_chunk', decoded)
                    heavy = {'original_files_base64', 'candidate_files_base64', 'assembled_files_base64',
                             'public_candidate_files_base64', 'original_files_sha256'} & set(worker)
                    control['worker'] = {k:v for k,v in worker.items() if k not in heavy}
                    row['worker_fields_projection'] = {'omitted_from_inline_only': sorted(heavy),
                                                      'complete_result_retained': True}
            row['controller'] = control
        except (KeyError, ValueError) as exc:
            row['decode_failure'] = type(exc).__name__ + ': ' + str(exc)
    return row
