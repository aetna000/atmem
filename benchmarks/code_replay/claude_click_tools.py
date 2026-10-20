"""Read-only graph proxy plus an offline, source-confined command tool.

Claude has no native tools in this experiment. Only command children enter the
OS sandbox; the trusted proxy can read its own provider state, not arbitrary
model-selected files. No inference is performed by the sandbox executable.
"""
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import time


def shell(config, command):
    if not isinstance(command, str) or not 1 <= len(command) <= 20000:
        raise ValueError("bounded shell command required")
    import shlex
    # The sandbox launcher can replace TMPDIR. Export inside the confined child
    # rather than assuming an inherited environment survives that launcher.
    exports = {k: config['shell_environment'][k] for k in ('PATH', 'PYTHONPATH')}
    exports['TMPDIR'] = config['workspace'] + '/.solver-tmp'
    command = '; '.join('export ' + k + '=' + shlex.quote(v) for k, v in exports.items()) + '; ' + command
    argv = [config["codex"], "sandbox", "-C", config["workspace"], "-P", "click-replay",
            *config["permissions"], "/bin/sh", "-c", command]
    process = subprocess.Popen(argv, env=config["shell_environment"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=35)
        stopped = False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        stopped = True
    output = (stdout + stderr).decode(errors="replace")
    return {"exit_code": process.returncode, "timed_out": stopped,
            "output": output[:24000], "output_truncated": len(output) > 24000}


def serve(config):
    provider = None
    pruner = None
    counter = 0
    consulted = False
    source_consulted = False
    def rpc(method, params=None):
        provider.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 100, "method": method,
                                         "params": params or {}}) + "\n")
        provider.stdin.flush()
        while True:
            line = provider.stdout.readline()
            if not line:
                raise RuntimeError("graph provider terminated")
            reply = json.loads(line)
            if reply.get("id") == 100:
                if "error" in reply:
                    raise RuntimeError(str(reply["error"]))
                return reply["result"]
    with open(config["provider_log"], "a") as logs, open(config["audit"], "a") as audit:
        try:
            if config.get("provider"):
                p = config["provider"]
                provider = subprocess.Popen(p["command"], cwd=p["cwd"], env=p["environment"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=logs, text=True, bufsize=1)
                rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                   "clientInfo": {"name": "claude-comparison", "version": "1"}})
                provider.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                provider.stdin.flush()
                graph_tools = rpc("tools/list")["tools"]
            else:
                graph_tools = []
            tools = [{"name": "workspace_command", "description": "Run an offline shell command in the permitted historical source tree. Use for reading, editing and testing. Python, PYTHONPATH and TMPDIR are configured. 35-second command limit; 24000-character output bound, explicitly marked if exceeded.",
                "inputSchema": {"type": "object", "additionalProperties": False,
                    "properties": {"command": {"type": "string", "minLength": 1, "maxLength": 20000}},
                    "required": ["command"]}}, *graph_tools]
            if config.get('source_reader') is not None:
                tools.append({'name': 'read_source',
                    'description': 'Read selected repository Python source lines for a task-specific goal. Omitted code is explicitly marked; source remains authoritative. Use workspace_command for searches, edits and tests.',
                    'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'properties': {'path': {'type': 'string'}, 'start': {'type': 'integer', 'minimum': 1},
                            'end': {'type': 'integer', 'minimum': 1}, 'goal': {'type': 'string', 'minLength': 1, 'maxLength': 1000}},
                        'required': ['path', 'start', 'end', 'goal']}})
                if config['source_reader'].get('command'):
                    pruner = subprocess.Popen(config['source_reader']['command'], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=logs, text=True, bufsize=1)
                    ready = json.loads(pruner.stdout.readline())
                    if ready.get('status') != 'ready':
                        raise RuntimeError('qualified GPU pruning service unavailable')
            for line in sys.stdin:
                request = json.loads(line)
                if "id" not in request:
                    continue
                started = time.monotonic()
                try:
                    method, params = request["method"], request.get("params", {})
                    if method == "initialize":
                        result = {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "click-comparison", "version": "1"}}
                    elif method == "tools/list":
                        result = {"tools": tools}
                    elif method == "ping":
                        result = {}
                    elif method == "tools/call":
                        counter += 1
                        if counter > 30:
                            raise ValueError("30 tool-call budget exhausted")
                        if params['name'] == 'read_source' and config.get('source_reader') is not None:
                            import shlex
                            from hashlib import sha256
                            args = params.get('arguments', {})
                            if set(args) != {'path', 'start', 'end', 'goal'}:
                                raise ValueError('exact source-read fields required')
                            path = PurePosixPath(args['path'])
                            if path.is_absolute() or '..' in path.parts or not str(path).startswith('src/') or path.suffix != '.py':
                                raise ValueError('permitted repository Python source required')
                            start, end, goal = args['start'], args['end'], args['goal']
                            if type(start) is not int or type(end) is not int or not 1 <= start <= end or end-start >= 400:
                                raise ValueError('source range must contain 1 to 400 lines')
                            if not isinstance(goal, str) or not 1 <= len(goal) <= 1000:
                                raise ValueError('bounded read goal required')
                            observed = shell(config, 'sed -n ' + str(start) + ',' + str(end) + 'p ' + shlex.quote(str(path)))
                            if observed['exit_code'] or observed['timed_out'] or observed['output_truncated']:
                                raise ValueError('source read failed or exceeded output bound; narrow the range')
                            code = observed['output']
                            value = {'path': str(path), 'start': start, 'end': end,
                                     'source_window_sha256': sha256(code.encode()).hexdigest(), 'code': code,
                                     'input_window_bytes': len(code.encode()), 'omitted': False}
                            if pruner:
                                pruner.stdin.write(json.dumps({'query': goal, 'code': code}) + '\n');pruner.stdin.flush()
                                pruned = json.loads(pruner.stdout.readline())
                                if pruned.get('error'):
                                    raise RuntimeError('pruning failed: ' + str(pruned['error']))
                                value.update(code=pruned['pruned_code'], omitted=True,
                                             pruning={k: v for k, v in pruned.items() if k != 'pruned_code'})
                            source_consulted = True
                            result = {'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': False}
                        elif params["name"] == "workspace_command":
                            if config.get('require_source_consult') and not source_consulted:
                                raise ValueError('Read relevant implementation with read_source before workspace commands in this controlled experiment; code_query discover can locate symbols first')
                            if config.get('require_graph_consult') and not consulted:
                                raise ValueError('Consult an available graph tool before workspace commands in this explicit-consult experiment')
                            args = params.get("arguments", {})
                            if set(args) != {"command"}:
                                raise ValueError("exact command field required")
                            value = shell(config, args["command"])
                            result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
                        elif params["name"] in {t["name"] for t in graph_tools}:
                            result = rpc(method, params)
                            if not result.get('isError'):
                                consulted = True
                        else:
                            raise ValueError("unknown tool")
                    else:
                        raise ValueError("unsupported MCP method")
                    reply = {"jsonrpc": "2.0", "id": request["id"], "result": result}
                except Exception as exc:
                    reply = {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32602, "message": str(exc)}}
                audit.write(json.dumps({"request": request, "response": reply,
                    "elapsed_ms": int((time.monotonic() - started) * 1000)}) + "\n")
                audit.flush()
                print(json.dumps(reply), flush=True)
        finally:
            if pruner:
                pruner.terminate()
                try:
                    pruner.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pruner.kill();pruner.wait()
            if provider:
                provider.terminate()
                try:
                    provider.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    provider.kill()


if __name__ == "__main__":
    serve(json.loads(sys.argv[1]))
