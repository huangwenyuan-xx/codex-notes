"""Pair a Linux SSH host with this Windows desktop, without public listeners."""
import argparse
import json
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time

from remote_bridge import CONFIG, ensure_running
from remote_protocol import request

ROOT = Path(__file__).resolve().parent


def run_command(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'SSH command failed')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description='Connect a remote Linux Codex task to the desktop notebook.')
    parser.add_argument('--host', help='An existing SSH alias or user@host')
    parser.add_argument('--remote-port', type=int, default=48219)
    parser.add_argument('--local-port', type=int, default=48220)
    parser.add_argument('--disconnect', action='store_true')
    args = parser.parse_args()
    previous = json.loads(CONFIG.read_text('utf-8')) if CONFIG.exists() else None
    if args.disconnect:
        if previous:
            previous['enabled'] = False
            CONFIG.write_text(json.dumps(previous), encoding='utf-8')
            try:
                request(previous['local_port'], previous['token'], 'shutdown')
            except OSError:
                pass
        print('Remote bridge disconnected.')
        return
    if not args.host or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', args.host):
        parser.error('Specify --host with an existing SSH alias or user@host.')
    if not all(1024 <= p <= 65535 for p in (args.remote_port, args.local_port)):
        parser.error('Ports must be between 1024 and 65535.')
    ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', args.host]
    stage = run_command(ssh + ['mktemp -d /tmp/codex-notes-XXXXXXXX'])
    if not re.fullmatch(r'/tmp/codex-notes-[A-Za-z0-9]+', stage):
        raise RuntimeError('Unexpected staging path')
    if previous:
        try:
            request(previous['local_port'], previous['token'], 'shutdown')
            time.sleep(2)
        except OSError:
            pass
    token = secrets.token_urlsafe(32)
    config = {'enabled': True, 'ssh_host': args.host, 'local_port': args.local_port,
              'remote_port': args.remote_port, 'token': token}
    sources = [ROOT / 'scripts/install_remote.py', ROOT / 'skill/scripts/pin_remote.py',
               ROOT / 'remote_protocol.py', ROOT / 'skill/SKILL.md']
    run_command(['scp', '-q', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                 *map(str, sources), f'{args.host}:{stage}/'])
    remote_config = {'mode': 'ssh-remote', 'remote_port': args.remote_port, 'token': token}
    remote_script = run_command(ssh + [f'python3 {stage}/install_remote.py'], input=json.dumps(remote_config))
    if not remote_script.startswith('/') or '\n' in remote_script:
        raise RuntimeError('Unexpected remote skill path')
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2), encoding='utf-8')
    ensure_running()
    import shlex
    for _ in range(15):
        time.sleep(1)
        result = subprocess.run(ssh + [f'python3 {shlex.quote(remote_script)} --check'],
                                capture_output=True, text=True, timeout=25)
        if result.returncode == 0:
            listeners = run_command(ssh + [f"ss -H -ltn 'sport = :{args.remote_port}'"])
            addresses = [line.split()[3] for line in listeners.splitlines() if len(line.split()) >= 4]
            if not addresses or any(address not in (f'127.0.0.1:{args.remote_port}', f'[::1]:{args.remote_port}') for address in addresses):
                config['enabled'] = False
                CONFIG.write_text(json.dumps(config), encoding='utf-8')
                request(config['local_port'], token, 'shutdown')
                raise RuntimeError('SSH server did not restrict the port to loopback. Pairing disabled; check GatewayPorts.')
            print('Paired. Remote pin requests now open in this desktop notebook.')
            print('Remote Skill:', remote_script)
            return
    raise RuntimeError('Tunnel not ready. Inspect remote-bridge.log in the notebook data folder.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
