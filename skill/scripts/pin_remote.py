"""Linux/headless client: send selected Markdown to the paired desktop."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import uuid

from remote_protocol import request

CONFIG = Path(__file__).resolve().parents[1] / 'config.json'


def deliver(pin=None, check=False):
    config = json.loads(CONFIG.read_text('utf-8'))
    response = request(config['remote_port'], config['token'], 'ping' if check else ('add_pin' if pin else 'show'), pin)
    if not response.get('ok'):
        raise RuntimeError(response.get('error', 'Desktop did not acknowledge'))
    return response


def main():
    parser = argparse.ArgumentParser(description='Pin a reply on your paired desktop via SSH.')
    content = parser.add_mutually_exclusive_group()
    content.add_argument('--file')
    content.add_argument('--text')
    parser.add_argument('--title', default='Pinned reply')
    parser.add_argument('--source', default='remote Codex conversation')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = Path(args.file).read_text(encoding='utf-8-sig') if args.file else (args.text or '')
    pin = None
    if text.strip() and not args.check:
        title = args.title
        if title == 'Pinned reply':
            title = next((line.strip().strip('#*-` ')[:48] for line in text.splitlines() if len(line.strip()) >= 6), title)
        pin = {'id': uuid.uuid4().hex, 'title': title, 'text': text.strip(), 'source': args.source,
               'status': 'active', 'created_at': datetime.now().isoformat(timespec='seconds')}
    deliver(pin, args.check)
    print('Desktop bridge connected.' if args.check else 'Reply delivered to the desktop window.' if pin else 'Desktop notebook opened.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('Not delivered. Open Codex Notes on the paired computer and check its SSH connection. '
              f'({type(error).__name__})', file=sys.stderr)
        raise SystemExit(1)
