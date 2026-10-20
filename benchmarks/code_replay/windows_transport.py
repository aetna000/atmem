"""Operator-only WSL Docker controller; no password or owner key handling."""
import ast
import os
from pathlib import Path
import sys


REMOTE_LOADER = "import sys,json;job=json.load(sys.stdin);exec(job['program'])"
FRAMED_LOADER = ("import sys,json;size=int(sys.stdin.buffer.readline(16));"
    "assert 1<=size<=64000000;raw=sys.stdin.buffer.read(size);assert len(raw)==size;"
    "job=json.loads(raw);exec(job['program'])")


def framed_input(job):
    """Avoid depending on Windows/WSL closing inherited stdin at JSON EOF."""
    import json
    raw = json.dumps(job).encode()
    if not 1 <= len(raw) <= 64_000_000:
        raise ValueError('bounded operator job required')
    return str(len(raw)).encode() + b'\n' + raw


def framed_command():
    """New explicit transport version; original frozen cohorts stay unchanged."""
    if os.environ.get("ATMEM_BENCHMARK_LOCAL_WSL") == "1":
        if sys.platform != "linux" or not Path("/mnt/c").is_dir():
            raise ValueError("local operator transport requires the authorized WSL host")
        return [sys.executable, "-I", "-S", "-c", FRAMED_LOADER]
    result = command()
    result[-1] = result[-1].replace(REMOTE_LOADER.replace('"', '\\"'), FRAMED_LOADER.replace('"', '\\"'))
    if FRAMED_LOADER not in result[-1]:
        raise ValueError('review Windows framed loader quoting')
    return result


def controller_source():
    source = (Path(__file__).parent / "external_qualification.py").read_text()
    functions = [node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "execute_worker"]
    if len(functions) != 1:
        raise ValueError("existing bounded controller required")
    body = ast.get_source_segment(source, functions[0])
    guard = 'shutil.disk_usage("/private/tmp").free'
    if body.count(guard) != 2 or body.count("tempfile.TemporaryFile()") != 2:
        raise ValueError("review Windows adaptation when controller changes")
    body = body.replace(guard, 'min(shutil.disk_usage("/tmp").free, shutil.disk_usage("/mnt/c").free)')
    body = body.replace("tempfile.TemporaryFile()", 'tempfile.TemporaryFile(dir="/dev/shm")')
    return "import base64,json,shutil,subprocess,tempfile,time,sys\n" + body


def worker_program():
    # REMOTE_LOADER already decoded stdin. Never consume the JSON stream twice.
    return controller_source() + '\nprint(json.dumps(execute_worker(job["command"],job["payload"],job["name"])))\n'


def command():
    return ["ssh", "-S", "/private/tmp/atmem-click-windows-20261018.sock", "-o", "BatchMode=yes", "-T",
        "user@192.168.0.87", 'wsl -d Ubuntu -u root -- python3 -c "' + REMOTE_LOADER.replace('"', '\\"') + '"']
