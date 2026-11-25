from __future__ import annotations

import argparse
import errno
import ipaddress
from pathlib import Path
from contextlib import ExitStack
import os
import socket
import threading
import webbrowser

import uvicorn


def lan_addresses():
    networks = [ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        addresses = []
    # A routing lookup discovers the active adapter even without local DNS.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        try:
            route.connect(("192.0.2.1", 9))
            addresses.insert(0, route.getsockname()[0])
        except OSError:
            pass
    available = []
    for ip in dict.fromkeys(addresses):
        if any(ipaddress.ip_address(ip) in net for net in networks):
            with socket.socket() as probe:
                try:
                    probe.bind((ip, 0))
                except OSError:
                    continue
                available.append(ip)
    return available


def bind_listeners(hosts, first, fixed):
    if not 1 <= first <= 65535:
        raise ValueError("QR port must be between 1 and 65535")
    for port in range(first, first + 1 if fixed else 65536):
        with ExitStack() as stack:
            listeners = []
            try:
                for host in hosts:
                    sock = stack.enter_context(socket.socket())
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    else:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((host, port))
                    sock.listen(socket.SOMAXCONN)
                    sock.setblocking(False)
                    listeners.append(sock)
            except OSError as exc:
                if fixed:
                    raise RuntimeError(f"QR port {port} is unavailable. Close the old server and retry.") from exc
                if exc.errno not in (errno.EADDRINUSE, errno.EACCES):
                    raise
                continue
            stack.pop_all()
            return listeners, port
    raise RuntimeError("No free QR port")


def create_server_socket(start_port=8765, host="127.0.0.1"):
    sockets, port = bind_listeners([host], start_port, False)
    return sockets[0], port


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open-browser", action="store_true")
    options = parser.parse_args()
    data = Path(os.getenv("QR_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    data.mkdir(parents=True, exist_ok=True)
    port_file = data / ".qr-lan-port"
    saved = port_file.read_text().strip() if port_file.exists() else ""
    configured = os.getenv("QR_PORT") or saved
    addresses = lan_addresses()
    sockets, port = bind_listeners(["127.0.0.1", *addresses], int(configured or "8765"), bool(configured))
    if not saved and not os.getenv("QR_PORT"):
        with port_file.open("x") as f:
            f.write(str(port))
    address = f"http://127.0.0.1:{port}"
    os.environ["QR_LAN_ORIGINS"] = ",".join(f"http://{ip}:{port}" for ip in addresses)
    print("LAN IP addresses:", os.environ["QR_LAN_ORIGINS"] or "offline; reconnect and restart QR", flush=True)
    print(f"QR is starting at {address}", flush=True)
    print("Keep this window open. Runtime data is stored in the data folder.", flush=True)

    config = uvicorn.Config("qr_server.main:app", host="127.0.0.1", port=port, proxy_headers=False, log_level="info")
    try:
        # The socket is already listening. The browser request will be served
        # after Uvicorn finishes application startup.
        if options.open_browser:
            threading.Thread(target=webbrowser.open, args=(address,), daemon=True).start()
        server = uvicorn.Server(config)
        server.run(sockets=sockets)
        if not server.started:
            raise SystemExit(1)
    finally:
        for sock in sockets:
            sock.close()


if __name__ == "__main__":
    main()
