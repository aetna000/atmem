"""macOS agent filesystem/network boundary, separate from memory authority."""
import json
from pathlib import Path
import platform
import subprocess


def policy(*, readable, writable, ports, sockets=()):
    if platform.system() != 'Darwin':
        raise RuntimeError('This sandbox implementation is qualified only on macOS')
    def subpath(path):
        return '(subpath ' + json.dumps(str(Path(path).resolve())) + ')'
    read = [Path(p).resolve() for p in readable]
    write = [Path(p).resolve() for p in writable]
    for path in read + write:
        if str(path) in {'/', '/Users', '/Volumes', str(Path.home())}:
            raise ValueError('Refusing broad agent filesystem access')
    if any(type(p) is not int or not 1 <= p <= 65535 for p in ports):
        raise ValueError('Explicit local ports required')
    lines = [
        '(version 1)', '(deny default)', '(allow process*)', '(allow sysctl-read)',
        '(allow file-map-executable)', '(allow ipc-posix*)',
        '(allow mach-lookup)',
        '(deny mach-lookup (global-name "com.apple.securityd") (global-name "com.apple.securityd.xpc"))',
        '(deny process-exec (literal "/usr/bin/security") (literal "/usr/bin/osascript") (literal "/usr/bin/open"))',
        '(allow file-read-metadata)',
        # dyld requires reading the root directory itself; this grants no descendant content.
        '(allow file-read* (literal "/") (subpath "/System") (subpath "/usr") (subpath "/bin") '
        '(subpath "/sbin") (subpath "/opt/homebrew") (subpath "/private/etc") '
        '(subpath "/private/var/db/timezone") (literal "/dev/urandom") '
        '(literal "/dev/random") (literal "/dev/null"))',
        '(allow file-write* (literal "/dev/null"))',
    ]
    if read:
        lines.append('(allow file-read* ' + ' '.join(subpath(p) for p in read) + ')')
    if write:
        lines.append('(allow file-read* file-write* ' + ' '.join(subpath(p) for p in write) + ')')
    for port in ports:
        lines.append(f'(allow network-outbound (remote ip "localhost:{port}"))')
    for socket in sockets:
        lines.append('(allow network-outbound (remote unix-socket (literal ' + json.dumps(str(socket)) + ')))')
    return '\n'.join(lines) + '\n'


def run(command, *, profile, environment, cwd, timeout):
    if not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('macOS sandbox-exec unavailable; refusing unsandboxed fallback')
    return subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, *command],
        env=environment, cwd=cwd, text=True, capture_output=True, timeout=timeout)
