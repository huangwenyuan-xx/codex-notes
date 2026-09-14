"""Install only the lightweight remote Skill; receive pairing data on stdin."""
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

config = json.load(sys.stdin)
home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
target = home / 'skills' / 'pin-reply'
source = Path(__file__).resolve().parent
if target.exists():
    backup = home / 'skill-backups' / ('pin-reply-' + uuid.uuid4().hex)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, backup)
(target / 'scripts').mkdir(parents=True, exist_ok=True)
shutil.copy2(source / 'SKILL.md', target / 'SKILL.md')
for name in ('pin_remote.py', 'remote_protocol.py'):
    shutil.copy2(source / name, target / 'scripts' / name)
config_path = target / 'config.json'
config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
config_path.chmod(0o600)
print(str(target / 'scripts' / 'pin_remote.py'))
