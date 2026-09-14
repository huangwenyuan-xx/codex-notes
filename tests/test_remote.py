import json
from pathlib import Path
import runpy
import socket
import sys
import unittest
from unittest.mock import patch

from remote_bridge import Receiver
from remote_protocol import MAX_MESSAGE, receive, send


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.receiver = Receiver({'token': 'test-only-pairing'})

    def test_remote_client_uses_summary_title_without_slicing_body(self):
        client = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'skill/scripts/pin_remote.py'))
        body = '好的，下面详细说明。\n\n检查 SSH 配置。'
        for title, expected in [('SSH 连接失败排查步骤', 'SSH 连接失败排查步骤'), ('Pinned reply', '未命名笔记')]:
            captured = []
            with patch.object(sys, 'argv', ['pin_remote.py', '--text', body, '--title', title]), \
                    patch.dict(client['main'].__globals__, {'deliver': lambda pin, check: captured.append(pin)}), \
                    patch('builtins.print'):
                client['main']()
            self.assertEqual(captured[0]['title'], expected)
            self.assertEqual(captured[0]['text'], body)

    def test_bad_token_never_forwards(self):
        with patch('remote_bridge.send_to_running_window') as forward:
            result = self.receiver.handle({'token': 'wrong', 'type': 'show'})
        self.assertFalse(result['ok'])
        forward.assert_not_called()

    def test_only_note_fields_are_forwarded(self):
        pin = {'id': 'test-id', 'title': '方案', 'text': '```sh\nprintf "%s" "$HOME"\n```',
               'source': 'remote task', 'file': '/do/not/open', 'status': 'done'}
        with patch('remote_bridge.send_to_running_window', return_value=True) as forward:
            result = self.receiver.handle({'token': 'test-only-pairing', 'type': 'add_pin', 'pin': pin})
        self.assertTrue(result['ok'])
        payload = forward.call_args.args[0]
        self.assertEqual(payload['text'], pin['text'])
        self.assertNotIn('file', payload)
        self.assertEqual(payload['status'], 'active')

    def test_unsupported_operations_rejected(self):
        result = self.receiver.handle({'token': 'test-only-pairing', 'type': 'delete'})
        self.assertFalse(result['ok'])

    def test_ping_does_not_open_window(self):
        with patch('remote_bridge.send_to_running_window') as forward:
            self.assertTrue(self.receiver.handle({'token': 'test-only-pairing', 'type': 'ping'})['ok'])
        forward.assert_not_called()

    def test_oversized_frame_rejected_before_read(self):
        a, b = socket.socketpair()
        with a, b:
            a.sendall((MAX_MESSAGE + 1).to_bytes(4, 'big'))
            with self.assertRaises(ValueError):
                receive(b)

    def test_protocol_preserves_markdown_unicode(self):
        a, b = socket.socketpair()
        with a, b:
            expected = {'text': '## 中文\n\n```ps1\necho "$HOME"\n```'}
            send(a, expected)
            self.assertEqual(receive(b), expected)
