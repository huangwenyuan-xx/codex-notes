"""Small bounded JSON protocol, carried only over loopback and SSH."""
import json
import socket

MAX_MESSAGE = 8_000_000


def receive(sock):
    def exact(length):
        data = bytearray()
        while len(data) < length:
            part = sock.recv(length - len(data))
            if not part:
                raise ConnectionError('Incomplete bridge response')
            data.extend(part)
        return data
    length = int.from_bytes(exact(4), 'big')
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Invalid bridge message size')
    value = json.loads(exact(length).decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Expected an object')
    return value


def send(sock, value):
    data = json.dumps(value, ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_MESSAGE:
        raise ValueError('Reply is too large')
    sock.sendall(len(data).to_bytes(4, 'big') + data)


def request(port, token, kind, pin=None):
    with socket.create_connection(('127.0.0.1', port), timeout=3) as sock:
        sock.settimeout(20)
        send(sock, {'token': token, 'type': kind, 'pin': pin})
        return receive(sock)
