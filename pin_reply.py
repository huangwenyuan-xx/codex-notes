"""Codex Notes command line and shared, UI-independent note utilities."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import uuid
from datetime import datetime
from pathlib import Path

CODEX_DIR = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
STATE_DIR = Path(os.environ.get("CODEX_NOTES_DATA_DIR") or CODEX_DIR / "pin-reply-tool")
STATE_FILE = STATE_DIR / "state.json"
EXPORT_DIR = STATE_DIR / "exports"
HOST = "127.0.0.1"
PORT = int(os.environ.get("CODEX_NOTES_PORT", "48217"))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    # Do not silently overwrite a damaged state file with an empty notebook.
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("pins", []), list):
        raise ValueError("Invalid notebook state; restore state.json from a backup.")
    return state


def normalize_title(title: str, text: str) -> str:
    if title.strip() not in ("", "Codex pinned reply", "Pinned reply", "固定：上条回复", "固定上条回复", "上条回复"):
        return title.strip()[:80]
    for line in text.splitlines():
        candidate = line.strip().strip("#*-` ")
        if len(candidate) >= 6:
            return candidate[:48]
    return "Pinned reply"


def make_pin(title: str, text: str, source: str = "current Codex task", pin_id=None) -> dict:
    clean_text = text.strip()
    return {"id": pin_id or uuid.uuid4().hex, "title": normalize_title(title, clean_text),
            "text": clean_text, "source": source.strip() or "current Codex task",
            "status": "active", "created_at": datetime.now().isoformat(timespec="seconds")}


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^\w\-. \u4e00-\u9fff]+", "-", text).strip(" .-")
    return (re.sub(r"\s+", "-", cleaned)[:60] or "pinned-reply") + ".md"


def pin_to_markdown(pin: dict) -> str:
    return (f"# {pin.get('title', 'Pinned reply')}\n\n"
            f"- Status: {pin.get('status', 'active')}\n"
            f"- Created: {pin.get('created_at', '')}\n"
            f"- Source: {pin.get('source', '')}\n\n{pin.get('text', '')}\n")


def send_to_running_window(pin: dict | None) -> bool:
    payload = json.dumps({"type": "add_pin" if pin else "show", "pin": pin}, ensure_ascii=False).encode("utf-8")
    try:
        with socket.create_connection((HOST, PORT), timeout=2) as sock:
            sock.sendall(len(payload).to_bytes(4, "big") + payload)
            return sock.recv(16) == b"OK"
    except OSError:
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Pin Markdown replies in Codex Notes.")
    content = parser.add_mutually_exclusive_group()
    content.add_argument("--text")
    content.add_argument("--file", help="UTF-8 Markdown file")
    content.add_argument("--request", help="JSON request created by the PowerShell launcher")
    parser.add_argument("--consume-request", action="store_true", help="Delete launcher-owned request after reading")
    parser.add_argument("--title", default="Pinned reply")
    parser.add_argument("--source", default="current Codex task")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=620)
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate runtime and local assets without opening a window")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        import webview
        from markdown_it import MarkdownIt
        from webview.platforms.winforms import _is_chromium
        if not _is_chromium():
            raise RuntimeError("Microsoft Edge WebView2 Runtime is required.")
        for name in ("index.html", "notes.css", "notes.js", "path-copy.js", "vendor/lucide.min.js",
                     "vendor/easymde.min.js", "vendor/easymde.min.css"):
            if not (Path(__file__).parent / "ui" / name).is_file():
                raise FileNotFoundError(name)
        print("Codex Notes runtime check passed.")
        return 0

    text, pin_id = args.text or "", None
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8-sig")
    if args.request:
        request = json.loads(Path(args.request).read_text(encoding="utf-8-sig"))
        text, pin_id = request.get("text", ""), request.get("id")
        args.title, args.source = request.get("title", args.title), request.get("source", args.source)
        args.width, args.height = int(request.get("width", args.width)), int(request.get("height", args.height))
        if args.consume_request:
            Path(args.request).unlink()
    pin = make_pin(args.title, text, args.source, pin_id) if text.strip() else None
    if args.send:
        return 0 if send_to_running_window(pin) else 1
    if os.name == 'nt':
        from remote_bridge import ensure_running
        ensure_running()
    from notes_web import run
    return run(args, pin)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if sys.stderr is not None:
            print(str(exc), file=sys.stderr)
        raise SystemExit(2)
