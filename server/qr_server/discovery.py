"""Unauthenticated discovery contains only a catalogue ID and TCP port."""
import json
import socket
import threading
import time
import ipaddress
import os
import subprocess

PORT = 8764
PROBE = b"QR_DISCOVER_V1"


def network_targets():
    """Windows hotspot owner is usually the PC's IPv4 default gateway."""
    targets = {"255.255.255.255"}
    if os.name != "nt":
        return targets
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        raw = subprocess.check_output(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "$a=@(Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength);"
             "$g=@(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop);"
             "@{addresses=$a;gateways=$g}|ConvertTo-Json -Compress"],
            timeout=6, creationflags=flags, stderr=subprocess.DEVNULL).decode("utf-8-sig")
        data = json.loads(raw)
        for entry in data.get("addresses") or []:
            try:
                ip = ipaddress.ip_interface(f'{entry["IPAddress"]}/{entry["PrefixLength"]}')
                if ip.ip.is_private and not ip.ip.is_loopback and not ip.ip.is_link_local and ip.network.prefixlen < 31:
                    targets.add(str(ip.network.broadcast_address))
            except (KeyError, ValueError):
                continue
        for address in data.get("gateways") or []:
            try:
                ip = ipaddress.ip_address(address)
                if ip.is_private and not ip.is_unspecified and not ip.is_loopback:
                    targets.add(str(ip))
            except ValueError:
                continue
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return targets


def serve_discovery(stop: threading.Event, catalogue_id: str, port: int):
    payload = json.dumps({"service":"qr","protocol":1,"catalogue_id":catalogue_id,"port":port}).encode()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", PORT))
            sock.settimeout(0.5)
            next_beacon = 0.0
            next_refresh = 0.0
            targets = {"255.255.255.255"}
            while not stop.is_set():
                if time.monotonic() >= next_refresh:
                    targets = network_targets()
                    next_refresh = time.monotonic() + 15
                if time.monotonic() >= next_beacon:
                    for target in targets:
                        try:
                            sock.sendto(payload, (target, PORT))
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


def serve_mdns(stop, catalogue_id, port):
    """Re-register after changing adapters; UDP remains the fallback."""
    from .launcher import lan_addresses
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
    service_type = "_qrcatalogue._tcp.local."
    name = f"QR-{catalogue_id[:8]}.{service_type}"
    previous = ()
    zc = info = None
    def close():
        if zc:
            try:
                if info:
                    zc.unregister_service(info)
            except Exception:
                pass
            finally:
                zc.close()
    try:
        while not stop.is_set():
            addresses = tuple(sorted(lan_addresses()))
            if addresses != previous:
                close()
                zc = info = None
                previous = ()
                if addresses:
                    try:
                        zc = Zeroconf(ip_version=IPVersion.V4Only)
                        info = ServiceInfo(service_type, name, addresses=[socket.inet_aton(a) for a in addresses],
                            port=port, properties={"catalogue_id":catalogue_id,"protocol":"1"},
                            server=f"qr-{catalogue_id[:8]}.local.")
                        zc.register_service(info)
                        previous = addresses
                    except Exception as exc:
                        print("QR mDNS unavailable:", exc, flush=True)
                        close()
                        zc = info = None
            stop.wait(12)
    finally:
        close()
