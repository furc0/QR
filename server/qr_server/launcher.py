from __future__ import annotations

import os
import socket

import uvicorn


def create_server_socket(start_port: int = 8765, host: str = "127.0.0.1") -> tuple[socket.socket, int]:
    """Bind the first available TCP port at or above start_port."""
    if not 1 <= start_port <= 65535:
        raise ValueError("QR_PORT must be between 1 and 65535")

    for port in range(start_port, 65536):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_socket.bind((host, port))
            server_socket.listen(socket.SOMAXCONN)
            server_socket.setblocking(False)
            return server_socket, port
        except OSError:
            server_socket.close()

    raise RuntimeError(f"No free TCP port found at or above {start_port}")


def main() -> None:
    preferred_port = int(os.getenv("QR_PORT", "8765"))
    server_socket, port = create_server_socket(preferred_port)
    address = f"http://127.0.0.1:{port}"

    if port != preferred_port:
        print(
            f"Port {preferred_port} is busy; QR selected the next available port.",
            flush=True,
        )
    print(f"QR is starting at {address}", flush=True)
    print("Keep this window open. Runtime data is stored in the data folder.", flush=True)

    config = uvicorn.Config("qr_server.main:app", host="127.0.0.1", port=port, log_level="info")
    try:
        uvicorn.Server(config).run(sockets=[server_socket])
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
