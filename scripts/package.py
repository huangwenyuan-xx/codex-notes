"""Create a source-only archive using an explicit file allowlist."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitignore", ".gitattributes",
    "requirements.txt", "pin_reply.py", "notes_web.py", "pin-reply.ps1", "setup.ps1", "install-skill.ps1",
    "skill/SKILL.md", "skill/scripts/pin.ps1", "scripts/package.py", "tests/test_notes.py",
    "ui/index.html", "ui/notes.css", "ui/notes.js", "ui/vendor/lucide.min.js", "ui/vendor/LICENSE-lucide",
    "docs/images/light.png", "docs/images/sage.png", "docs/images/dark.png", ".github/workflows/ci.yml",
    "remote_protocol.py", "remote_bridge.py", "connect_remote.py", "scripts/install_remote.py",
    "skill/scripts/pin_remote.py", "tests/test_remote.py",
    "ui/path-copy.js", "tests/test_paths.cjs",
]


def package(root=ROOT):
    missing = [name for name in FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    target = root / "dist" / "codex-notes-source.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(root / name, "codex-notes/" + name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    return target


if __name__ == "__main__":
    print(package())
