"""Metered provider boundary outside an interrupted worker; never caches replies."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import uuid

from .live_transport import save_json


@contextmanager
def model_broker(transport, observations: Path):
    observations.mkdir(parents=True, exist_ok=False)
    token = secrets.token_urlsafe(32)
    serial = threading.Lock()
    accepting = threading.Event()
    accepting.set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            if self.path != '/completion' or not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(401); return
            self.connection.settimeout(5)
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                self.send_error(400); return
            if not 0 < length <= 16 * 1024 * 1024:
                self.send_error(413); return
            try:
                request = json.loads(self.rfile.read(length))
                if set(request) != {'role', 'request'} or request['role'] not in {'agent', 'simulator'} or not isinstance(request['request'], dict):
                    raise ValueError('invalid broker request')
            except (ValueError, TypeError, OSError):
                self.send_error(400); return
            request_id = uuid.uuid4().hex
            save_json(observations / (request_id + '.received.json'), {'request_id': request_id, 'role': request['role']})
            with serial:
                if not accepting.is_set():
                    try:
                        self.send_error(503, 'broker closing; no provider dispatch')
                    except OSError:
                        pass
                    return
                before_calls = transport.calls
                try:
                    transport.role = request['role']
                    # Every HTTP request is a new provider attempt, even identical
                    # input after restart. Only the budget ledger may refuse it.
                    response = transport.complete(**request['request'])
                except Exception as error:
                    save_json(observations / (request_id + '.failure.json'), {'request_id': request_id,
                        'attempt_id': transport.last_attempt_id, 'dispatch_entered': transport.calls > before_calls,
                        'stage': 'metered_transport', 'error_type': type(error).__name__})
                    try:
                        self.send_error(503, 'metered attempt stopped; inspect accounting; no retry')
                    except OSError:
                        pass
                    return
                finally:
                    transport.role = None
                try:
                    save_json(observations / (request_id + '.response.json'),
                        {'request_id': request_id, 'attempt_id': transport.last_attempt_id,
                         'provider_response_id': response.get('id'), 'state': 'response_received'})
                    body = json.dumps(response).encode()
                    try:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        self.wfile.flush()
                        state = 'socket_write_completed_not_proof_of_worker_consumption'
                    except OSError:
                        state = 'orphaned_response'
                    save_json(observations / (request_id + '.delivery.json'), {'request_id': request_id,
                        'attempt_id': transport.last_attempt_id, 'state': state})
                except Exception as error:
                    # Do not append a second HTTP status after a partial response.
                    # The independent transport ledger retains the charged call.
                    save_json(observations / (request_id + '.failure.json'), {'request_id': request_id,
                        'attempt_id': transport.last_attempt_id, 'stage': 'after_metered_completion',
                        'error_type': type(error).__name__, 'billing_may_have_occurred': True})
                    self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/completion', token
    finally:
        accepting.clear()
        server.shutdown(); server.server_close(); thread.join(3)
        # Grading may reuse this transport only after an in-flight provider call
        # has settled. Closing a worker socket does not cancel provider billing.
        with serial:
            pass
