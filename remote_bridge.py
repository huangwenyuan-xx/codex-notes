"""Authenticated local receiver plus a reconnecting reverse SSH tunnel."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

from pin_reply import STATE_DIR, send_to_running_window
from remote_protocol import receive, send, request

CONFIG = STATE_DIR / 'remote-bridge.json'
STATUS = STATE_DIR / 'remote-bridge-status.json'
CREATE_HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def python_window():
    candidate = Path(sys.executable).with_name('pythonw.exe')
    return str(candidate if candidate.exists() else Path(sys.executable))


def ensure_running():
    if not CONFIG.exists():
        return
    config = json.loads(CONFIG.read_text('utf-8'))
    if not config.get('enabled'):
        return
    try:
        if request(config['local_port'], config['token'], 'ping').get('ok'):
            return
    except (OSError, ValueError):
        pass
    subprocess.Popen([python_window(), str(Path(__file__).resolve()), '--serve'],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=CREATE_HIDDEN)


class Receiver:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def handle(self, message):
        supplied = message.get('token')
        if not isinstance(supplied, str) or not secrets.compare_digest(supplied, self.config['token']):
            return {'ok': False, 'error': 'Pairing rejected'}
        kind = message.get('type')
        if kind == 'ping':
            return {'ok': True, 'service': 'codex-notes-bridge'}
        if kind == 'shutdown':
            self.stop.set()
            return {'ok': True}
        if kind not in ('add_pin', 'show'):
            return {'ok': False, 'error': 'Unsupported bridge operation'}
        pin = message.get('pin') if kind == 'add_pin' else None
        if kind == 'add_pin':
            if not isinstance(pin, dict) or not all(isinstance(pin.get(k), str) for k in ('id', 'text', 'title')):
                return {'ok': False, 'error': 'Invalid note'}
            # Forward only note fields, never paths or executable operations.
            pin = {k: pin.get(k, '') for k in ('id', 'text', 'title', 'source', 'created_at')}
            pin['status'] = 'active'
        with self.lock:
            if send_to_running_window(pin):
                return {'ok': True, 'id': pin['id'] if pin else None}
            root = Path(__file__).resolve().parent
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            descriptor, filename = tempfile.mkstemp(prefix='remote-request-', suffix='.json', dir=STATE_DIR)
            payload = dict(pin or {})
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                json.dump(payload, file, ensure_ascii=False)
            process = subprocess.Popen([python_window(), str(root / 'pin_reply.py'), '--request', filename, '--consume-request'],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=CREATE_HIDDEN)
            deadline = time.monotonic() + 14
            while time.monotonic() < deadline:
                time.sleep(.25)
                # The same note ID makes acknowledgment retries idempotent.
                if send_to_running_window(pin):
                    return {'ok': True, 'id': pin['id'] if pin else None}
                if process.poll() not in (None, 0):
                    break
            return {'ok': False, 'error': 'Desktop app did not acknowledge; check its startup-error.log'}


def serve(config):
    receiver = Receiver(config)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(20)
            try:
                send(self.request, receiver.handle(receive(self.request)))
            except (OSError, ValueError, TypeError):
                pass

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    try:
        server = Server(('127.0.0.1', config['local_port']), Handler)
    except OSError:
        return 2
    server.timeout = .5

    def tunnel():
        while not receiver.stop.is_set():
            command = ['ssh', '-N', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                       '-o', 'ConnectTimeout=8', '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=15',
                       '-o', 'ServerAliveCountMax=3', '-R',
                       f"127.0.0.1:{config['remote_port']}:127.0.0.1:{config['local_port']}", config['ssh_host']]
            try:
                with (STATE_DIR / 'remote-bridge.log').open('w', encoding='utf-8') as log:
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                               stderr=log, creationflags=CREATE_HIDDEN)
                    STATUS.write_text(json.dumps({'pid': os.getpid(), 'ssh_pid': process.pid}), encoding='utf-8')
                    while process.poll() is None and not receiver.stop.wait(1):
                        pass
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            receiver.stop.wait(5)

    worker = threading.Thread(target=tunnel, daemon=True)
    worker.start()
    with server:
        while not receiver.stop.is_set():
            server.handle_request()
    worker.join(timeout=7)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    if args.serve:
        raise SystemExit(serve(json.loads(CONFIG.read_text('utf-8'))))
    ensure_running()
