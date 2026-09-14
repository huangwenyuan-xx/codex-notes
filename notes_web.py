"""Native floating window with an offline, document-style WebView interface."""
from __future__ import annotations

import json
import re
import socket
import threading
import webbrowser
from pathlib import Path

import webview
from markdown_it import MarkdownIt

from pin_reply import HOST, PORT, STATE_DIR, STATE_FILE, EXPORT_DIR, load_state, pin_to_markdown, safe_filename, send_to_running_window


class Notes:
    def __init__(self, args, initial_pin=None):
        self.lock = threading.RLock()
        self.state = load_state()
        self.pins = self.state.get("pins", [])
        if initial_pin:
            self.pins.append(initial_pin)
        self.selected = self.state.get("selected")
        if initial_pin or not any(p["id"] == self.selected for p in self.pins):
            self.selected = self.pins[-1]["id"] if self.pins else None
        self.font_size = max(13, min(20, self.state.get("web_font_size", 15)))
        self.topmost = self.state.get("topmost", True)
        self.theme = self.state.get("theme", "light")
        if self.theme not in ("light", "sage", "dark"):
            self.theme = "light"
        self.window = None
        self.ready = threading.Event()
        self.renderer = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table")
        self._save()

    def _save(self):
        with self.lock:
            self.state.update(pins=self.pins, selected=self.selected,
                              web_font_size=self.font_size, topmost=self.topmost, theme=self.theme)
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = STATE_FILE.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(STATE_FILE)

    def _snapshot(self):
        return {"pins": [{k: p.get(k, "") for k in ("id", "title", "status", "created_at", "source")} for p in self.pins],
                "selected": self.selected, "fontSize": self.font_size, "topmost": self.topmost, "theme": self.theme}

    def get_state(self):
        with self.lock:
            return self._snapshot()

    def get_note(self, pin_id):
        with self.lock:
            pin = next((p for p in self.pins if p["id"] == pin_id), None)
            if pin is None:
                return None
            self.selected = pin_id
            self._save()
            return {**pin, "html": self.renderer.render(pin["text"])}

    def change(self, action, pin_id=None, value=None):
        with self.lock:
            pin = next((p for p in self.pins if p["id"] == pin_id), None)
            if action == "status" and pin:
                pin["status"] = "active" if pin.get("status") == "done" else "done"
            elif action == "delete" and pin:
                self.pins.remove(pin)
                if self.selected == pin_id:
                    self.selected = self.pins[-1]["id"] if self.pins else None
            elif action == "clear":
                self.pins.clear()
                self.selected = None
            elif action == "font":
                self.font_size = max(13, min(20, int(value)))
            elif action == "theme" and value in ("light", "sage", "dark"):
                self.theme = value
            self._save()
            return self._snapshot()

    def copy_text(self, text):
        # Clipboard access must run on the Windows Forms STA thread.
        from System import Action
        from System.Windows.Forms import Clipboard
        self.window.native.Invoke(Action(lambda: Clipboard.SetText(str(text) or " ")))
        return True

    def export_note(self, pin_id):
        with self.lock:
            pin = next(p for p in self.pins if p["id"] == pin_id)
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            path = EXPORT_DIR / (pin["id"][:8] + "-" + safe_filename(pin["title"]))
            path.write_text(pin_to_markdown(pin), encoding="utf-8")
            return str(path)

    def open_link(self, url):
        if str(url).startswith(("https://", "http://")):
            webbrowser.open(url)

    def window_action(self, action):
        if action == "minimize":
            self.window.minimize()
        elif action == "maximize":
            from System.Windows.Forms import FormWindowState
            if self.window.native.WindowState == FormWindowState.Maximized:
                self.window.restore()
            else:
                self._geometry()
                self.window.maximize()
            return self.window.native.WindowState == FormWindowState.Maximized
        elif action == "close":
            self.window.destroy()
        elif action == "topmost":
            self.topmost = not self.topmost
            self.window.on_top = self.topmost
            self._save()
        return self.topmost

    def resize_from_edge(self, edge):
        import ctypes
        from ctypes import wintypes
        from System import Action
        from System.Windows.Forms import FormWindowState

        edges = {"w": 1, "e": 2, "n": 3, "nw": 4, "ne": 5, "s": 6, "sw": 7, "se": 8}
        if edge not in edges:
            return False

        # Enter Windows' native sizing loop, keeping minimum size and DPI behavior.
        def resize():
            if self.window.native.WindowState != FormWindowState.Normal:
                return
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.ReleaseCapture.argtypes = []
            user32.ReleaseCapture.restype = wintypes.BOOL
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.ReleaseCapture()
            user32.SendMessageW(self.window.native.Handle.ToInt64(), 0x0112, 0xF000 + edges[edge], 0)

        self.window.native.Invoke(Action(resize))
        return True

    def _sync_window_state(self):
        from System.Windows.Forms import FormWindowState
        if self.ready.is_set():
            maximized = self.window.native.WindowState == FormWindowState.Maximized
            self.window.evaluate_js(f"window.setMaximized({json.dumps(maximized)})")

    def _geometry(self):
        from System.Windows.Forms import FormWindowState
        if self.window.native.WindowState != FormWindowState.Normal:
            return
        if self.window.width > 0 and self.window.x > -10000:
            self.state["geometry"] = f"{self.window.width}x{self.window.height}{self.window.x:+d}{self.window.y:+d}"
            self._save()

    def _publish(self):
        if self.ready.wait(20):
            self.window.restore()
            self.window.show()
            self.window.evaluate_js("window.refreshNotes()")

    def _serve(self, server):
        def receive(conn, length):
            data = bytearray()
            while len(data) < length:
                part = conn.recv(length - len(data))
                if not part:
                    raise ValueError("Incomplete message")
                data.extend(part)
            return data

        with server:
            while True:
                conn, _ = server.accept()
                with conn:
                    try:
                        conn.settimeout(2)
                        length = int.from_bytes(receive(conn, 4), "big")
                        if not 0 < length <= 8_000_000:
                            raise ValueError("Invalid message size")
                        message = json.loads(receive(conn, length).decode("utf-8"))
                        if message.get("type") == "add_pin":
                            pin = message["pin"]
                            if not all(isinstance(pin.get(k), str) for k in ("id", "text", "title")):
                                raise ValueError("Invalid note")
                            with self.lock:
                                if not any(p["id"] == pin["id"] for p in self.pins):
                                    self.pins.append(pin)
                                self.selected = pin["id"]
                                self._save()
                        elif message.get("type") != "show":
                            raise ValueError("Unknown message")
                        conn.sendall(b"OK")
                        threading.Thread(target=self._publish, daemon=True).start()
                    except (ValueError, KeyError, OSError):
                        try:
                            conn.sendall(b"ERR")
                        except OSError:
                            pass


class Bridge:
    """Expose commands only; native window objects must never enter the JS bridge."""
    def __init__(self, notes):
        self._notes = notes

    def get_state(self):
        return self._notes.get_state()

    def get_note(self, pin_id):
        return self._notes.get_note(pin_id)

    def change(self, action, pin_id=None, value=None):
        return self._notes.change(action, pin_id, value)

    def copy_text(self, text):
        return self._notes.copy_text(text)

    def export_note(self, pin_id):
        return self._notes.export_note(pin_id)

    def open_link(self, url):
        return self._notes.open_link(url)

    def window_action(self, action):
        return self._notes.window_action(action)

    def resize_from_edge(self, edge):
        return self._notes.resize_from_edge(edge)


def run(args, pin):
    if send_to_running_window(pin):
        return 0
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind((HOST, PORT))
    except OSError:
        server.close()
        return 0 if send_to_running_window(pin) else 2
    server.listen(8)
    notes = Notes(args, pin)
    geometry = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", notes.state.get("geometry", ""))
    width, height = max(480, args.width), max(380, args.height)
    x, y = args.x, args.y
    if geometry and x is None:
        width, height, x, y = map(int, geometry.groups())
        width, height = max(480, width), max(380, height)
    notes.window = webview.create_window(
        "Codex Notes", str(Path(__file__).parent / "ui" / "index.html"), js_api=Bridge(notes),
        width=width, height=height, x=x, y=y, min_size=(480, 380),
        frameless=True, easy_drag=False, shadow=True, resizable=True, on_top=notes.topmost,
        text_select=True, background_color="#ffffff",
    )
    notes.window.events.loaded += notes.ready.set
    notes.window.events.closing += notes._geometry
    notes.window.events.resized += lambda *_: notes._geometry()
    notes.window.events.moved += lambda *_: notes._geometry()
    notes.window.events.maximized += notes._sync_window_state
    notes.window.events.restored += notes._sync_window_state
    threading.Thread(target=notes._serve, args=(server,), daemon=True).start()
    webview.start(gui="edgechromium")
    return 0
