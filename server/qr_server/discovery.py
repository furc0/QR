"""Unauthenticated discovery contains only a catalogue ID and TCP port."""
import json
import socket
import threading
import time

PORT = 8764
PROBE = b"QR_DISCOVER_V1"


def serve_discovery(stop: threading.Event, catalogue_id: str, port: int):
    payload = json.dumps({"service":"qr","protocol":1,"catalogue_id":catalogue_id,"port":port}).encode()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", PORT))
            sock.settimeout(0.5)
            next_beacon = 0.0
            while not stop.is_set():
                if time.monotonic() >= next_beacon:
                    try:
                        sock.sendto(payload, ("255.255.255.255", PORT))
                    except OSError:
                        pass
                    next_beacon = time.monotonic() + 3
                try:
                    data, peer = sock.recvfrom(256)
                    if data == PROBE:
                        sock.sendto(payload, peer)
                except (socket.timeout, OSError):
                    pass
    except OSError as exc:
        print("QR UDP discovery unavailable:", exc, flush=True)
