"""Explicit local command execution feeding the existing experience authority.

This is an operator-invoked command producer, not an MCP execution tool, shell,
sandbox or automatic host-outcome qualification. Never import it from a remote
dashboard action. Captured output is encrypted by the existing Code store.
"""
import base64
from hashlib import sha256
import hmac
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from uuid import uuid4

from atmem.code.experience import CodeExperience
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content
from atmem.knowledge.contracts import ExecutionReceipt, ExperienceProposal, SourceAnchor, source_path, text


def _execute(argv, root, timeout, max_output):
    process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()
    lock = threading.Lock()
    def read(stream, index):
        try:
            while True:
                part = stream.read(4096)
                if not part:
                    break
                with lock:
                    remaining = max_output - sum(map(len, buffers))
                    buffers[index].extend(part[:max(0, remaining)])
                    if len(part) > remaining:
                        exceeded.set()
        finally:
            stream.close()
    threads = [threading.Thread(target=read, args=(s, i), daemon=True)
               for i, s in enumerate((process.stdout, process.stderr))]
    for thread in threads:
        thread.start()
    deadline, stopped = time.monotonic() + timeout, None
    while process.poll() is None:
        if exceeded.is_set() or time.monotonic() >= deadline:
            stopped = 'output_limit' if exceeded.is_set() else 'timeout'
            break
        time.sleep(.01)
    # Also close inherited pipes of descendants after the direct child exits.
    for thread in threads:
        thread.join(timeout=.1)
    if stopped or any(t.is_alive() for t in threads):
        stopped = stopped or 'incomplete_output'
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # Some restricted hosts deny group signalling even for a
                # direct child. Never broaden the target: kill that child only
                # and let the bounded pipe-close check refuse incomplete data.
                if process.poll() is None:
                    process.kill()
    process.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=2)
    if any(t.is_alive() for t in threads):
        raise RuntimeError('command output could not be closed safely')
    if exceeded.is_set():
        stopped = 'output_limit'
    return process.returncode, bytes(buffers[0]), bytes(buffers[1]), stopped


def run_command(application, scope, root, argv, *, intent, anchors, note='', timeout=300, max_output=500000):
    """Run exactly the explicit argv. No shell parsing, auto-install or retries."""
    if scope.subject_id != application.subject_id:
        raise PermissionError('command subject mismatch')
    application.authorize(scope.project_id)
    text(intent, 'intent', 1000)
    if note:
        text(note, 'attributed note', 500)
    if not isinstance(argv, (list, tuple)) or not 1 <= len(argv) <= 128:
        raise ValueError('bounded command argv required')
    for value in argv:
        text(value, 'command argument', 2048)
    if type(timeout) is not int or not 1 <= timeout <= 1800 or type(max_output) is not int or not 1024 <= max_output <= 500000:
        raise ValueError('invalid command limits')
    if not isinstance(anchors, (list, tuple)) or not 1 <= len(anchors) <= 64:
        raise ValueError('one to 64 explicit source anchors required')
    names = sorted({source_path(name) for name in anchors})
    if any(not screen_content(value, trusted=True).admissible for value in [intent, note, *argv, *names] if value):
        raise PermissionError('command metadata failed secret screening')
    key = os.urandom(32)
    service = CodeExperience(application, scope, producer_keys={'local-command': key})
    baseline, files, _ = service.capture_snapshot(root)  # Includes project/root authorization.
    for name in names:
        if name not in files:
            raise ValueError('anchor must be an admitted source file')
    started = time.monotonic()
    code, stdout, stderr, stopped = _execute(list(argv), str(Path(root).resolve(strict=True)), timeout, max_output)
    elapsed = int((time.monotonic() - started) * 1000)
    result = {'format': 'atmem-code-command-result-v1', 'exit_code': code,
              'stdout_base64': base64.b64encode(stdout).decode(), 'stderr_base64': base64.b64encode(stderr).decode(),
              'stop_reason': stopped, 'elapsed_ms': elapsed}
    response = {'format': 'atmem-code-command-run-v1', 'exit_code': code, 'elapsed_ms': elapsed,
                'stop_reason': stopped, 'capture_coverage': 'command_and_source_only',
                'reconstruction_status': 'not_reconstructable', 'formation': {'formed': False}}
    # Do not hide recognized secrets in base64 and then expose them in ordinary
    # Code inspection. No full Agent Black Box claim is made by this producer.
    if any(not screen_content(value.decode('utf-8', errors='replace'), trusted=True).admissible for value in (stdout, stderr) if value):
        if application.settings(scope.project_id)['auto_capture']:
            application.store.append_audit_event(subject_id=scope.subject_id, actor='local-command', event_type='code.command_capture_withheld',
                payload={'project_id': scope.project_id, 'reason': 'secret_output', 'exit_code': code,
                         'capture_coverage': 'metadata_only', 'reconstruction_status': 'not_reconstructable'})
        return {**response, 'capture': 'withheld', 'reason': 'secret_output', 'output_withheld': True}
    response['stdout'] = stdout.decode('utf-8', errors='replace')
    response['stderr'] = stderr.decode('utf-8', errors='replace')
    try:
        current, _, _ = service.capture_snapshot(root)
        stable = current.snapshot_id == baseline.snapshot_id
    except (ValueError, OSError):
        stable = False
    result['source_stable'] = stable
    raw = canonical_json(result).encode()
    identity = 'command-' + uuid4().hex
    bound_code = code if not stopped and stable and -255 <= code <= 255 else None
    receipt = ExecutionReceipt(identity, scope, 'local-command', identity, baseline.snapshot_id,
        baseline.configuration_sha256, tuple(argv), bound_code, sha256(raw).hexdigest(), identity)
    def sign(value):
        return hmac.new(key, canonical_json(value.to_dict()).encode(), sha256).hexdigest()
    source_anchors = tuple(SourceAnchor(name, dict(baseline.files)[name], 1,
        max(1, len(files[name].splitlines()))) for name in names)
    outcome = 'unknown' if bound_code is None else 'observed_pass' if code == 0 else 'observed_failure'
    observation = 'Explicit local command exited ' + str(code) + '. Source stable: ' + str(stable) + '.'
    if stopped:
        observation += ' Capture incomplete: ' + stopped + '.'
    if note:
        observation += ' User note: ' + note
    proposal = ExperienceProposal(identity, scope, baseline.snapshot_id, intent, observation,
                                  outcome, source_anchors, (identity,))
    with application.store.transaction():
        captured = service.receipt(receipt, baseline, raw, sign(receipt))
        formation = service.form(proposal, baseline, producer_id='local-command', signature=sign(proposal))
    return {**response, 'capture': captured, 'formation': formation, 'outcome': outcome,
            'source_stable': stable, 'experience_id': identity,
            'assurance': 'locally_observed_command_not_verified_fix'}
