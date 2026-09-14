import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import notes_web
import pin_reply


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for module in (pin_reply, notes_web):
            for key, value in {"STATE_DIR": root, "STATE_FILE": root / "state.json", "EXPORT_DIR": root / "exports"}.items():
                patcher = patch.object(module, key, value)
                patcher.start()
                self.addCleanup(patcher.stop)
        self.args = SimpleNamespace()

    def test_chinese_markdown_and_settings_survive_reopen(self):
        text = '# 方案\n\n```powershell\nWrite-Output "你好"\n```'
        pin = pin_reply.make_pin('Pinned reply', text, '历史会话')
        notes = notes_web.Notes(self.args, pin)
        notes.change('theme', value='sage')
        notes.change('font', value=18)
        notes.change('status', pin['id'])
        reopened = notes_web.Notes(self.args)
        self.assertEqual(reopened.theme, 'sage')
        self.assertEqual(reopened.font_size, 18)
        self.assertEqual(reopened.pins[0]['text'], text)
        self.assertEqual(reopened.pins[0]['status'], 'done')
        self.assertIn('<pre><code class="language-powershell">', reopened.get_note(pin['id'])['html'])

    def test_markdown_cannot_inject_scripts(self):
        pin = pin_reply.make_pin('Test', '<script>alert(1)</script>\n\n[x](javascript:alert(1))')
        rendered = notes_web.Notes(self.args, pin).get_note(pin['id'])['html']
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('href="javascript:', rendered)

    def test_export_is_utf8_with_source(self):
        pin = pin_reply.make_pin('部署', '正文\n\n```sh\ngit status\n```', '部署任务')
        exported = Path(notes_web.Notes(self.args, pin).export_note(pin['id'])).read_text('utf-8')
        self.assertIn('部署任务', exported)
        self.assertIn(pin['text'], exported)

    def test_corrupt_state_is_not_replaced(self):
        pin_reply.STATE_FILE.write_text('{broken', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            notes_web.Notes(self.args)
        self.assertEqual(pin_reply.STATE_FILE.read_text('utf-8'), '{broken')

    def test_bad_theme_does_not_change_current_theme(self):
        notes = notes_web.Notes(self.args)
        notes.change('theme', value='dark')
        self.assertEqual(notes.change('theme', value='unknown')['theme'], 'dark')

    def test_properties_visibility_persists_without_changing_note(self):
        pin = pin_reply.make_pin('Test', 'Keep this text', 'Source')
        notes = notes_web.Notes(self.args, pin)
        self.assertTrue(notes.get_state()['propertiesCollapsed'])
        self.assertFalse(notes.change('properties_collapsed', value=False)['propertiesCollapsed'])
        reopened = notes_web.Notes(self.args)
        self.assertFalse(reopened.get_state()['propertiesCollapsed'])
        self.assertEqual(reopened.pins, [pin])
        self.assertEqual(reopened.selected, pin['id'])
        self.assertFalse(reopened.change('properties_collapsed', value='false')['propertiesCollapsed'])
        reopened.change('properties_collapsed', value=True)
        self.assertTrue(notes_web.Notes(self.args).get_state()['propertiesCollapsed'])

    def test_edit_persists_markdown_and_preserves_metadata_and_original(self):
        pin = pin_reply.make_pin('Plan', 'original', 'source')
        notes = notes_web.Notes(self.args, pin)
        text = '~~done~~\n\n**next**\n\n```sh\necho hello\n```'
        notes.save_note(pin['id'], text, 'original')
        reopened = notes_web.Notes(self.args)
        saved = reopened.get_note(pin['id'])
        self.assertEqual(saved['text'], text)
        self.assertEqual(saved['original_text'], 'original')
        self.assertIn('<s>done</s>', saved['html'])
        for field in ('id', 'source', 'created_at', 'status', 'title'):
            self.assertEqual(saved[field], pin[field])
        reopened.save_note(pin['id'], '', text)
        self.assertEqual(reopened.pins[0]['original_text'], 'original')
        self.assertEqual(reopened.pins[0]['text'], '')

    def test_edit_conflict_missing_note_and_invalid_input_do_not_overwrite(self):
        pin = pin_reply.make_pin('Plan', 'original')
        notes = notes_web.Notes(self.args, pin)
        for args in [(pin['id'], 'new', 'stale'), ('missing', 'new', 'original'), (pin['id'], None, 'original')]:
            with self.assertRaises(ValueError):
                notes.save_note(*args)
        self.assertEqual(notes.pins[0]['text'], 'original')
        with patch.object(notes, '_save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                notes.save_note(pin['id'], 'new', 'original')
        self.assertEqual(notes.pins[0]['text'], 'original')
        self.assertNotIn('original_text', notes.pins[0])

    def test_preview_is_safe_and_does_not_save(self):
        notes = notes_web.Notes(self.args)
        before = pin_reply.STATE_FILE.read_bytes()
        html = notes.render_markdown('~~done~~ <script>alert(1)</script>\n[x](javascript:alert(1))')
        self.assertIn('<s>done</s>', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('href="javascript:', html)
        self.assertEqual(pin_reply.STATE_FILE.read_bytes(), before)

    def test_native_close_defers_to_editor_before_discarding_work(self):
        notes = notes_web.Notes(self.args)
        notes.set_editing(True)
        with patch.object(notes_web.threading, 'Thread') as thread:
            self.assertFalse(notes._closing())
            thread.return_value.start.assert_called_once()
        notes.set_editing(False)
        with patch.object(notes, '_geometry') as geometry:
            notes._closing()
            geometry.assert_called_once()

    def test_send_uses_length_prefixed_utf8(self):
        server = socket.socket()
        self.addCleanup(server.close)
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        received = []

        def read_request():
            with server.accept()[0] as conn:
                conn.settimeout(3)
                header = conn.recv(4)
                length = int.from_bytes(header, 'big')
                data = b''
                while len(data) < length:
                    data += conn.recv(length - len(data))
                received.append(json.loads(data.decode('utf-8')))
                conn.sendall(b'OK')

        thread = threading.Thread(target=read_request, daemon=True)
        thread.start()
        pin = pin_reply.make_pin('命令 "引用"', '中文\n```sh\necho "$HOME"\n```')
        with patch.object(pin_reply, 'PORT', server.getsockname()[1]):
            self.assertTrue(pin_reply.send_to_running_window(pin))
        thread.join(timeout=3)
        self.assertEqual(received[0]['pin'], pin)


if __name__ == '__main__':
    unittest.main()
