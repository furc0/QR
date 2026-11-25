"""Mobile catalogue locators. Numbers are permanent within a catalogue."""
import io
import os
import uuid
import threading
import time
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from .main import app, connect, current_user, org_for, WEB


def migrate_0003_mobile():
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("CREATE TABLE IF NOT EXISTS catalogue_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL UNIQUE)")
        c.execute("INSERT OR IGNORE INTO catalogue_identity VALUES(1,?)", (str(uuid.uuid4()),))
        c.execute("""CREATE TABLE IF NOT EXISTS card_numbers (
            number INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT UNIQUE REFERENCES parts(id) ON DELETE SET NULL)""")
        c.execute("""INSERT INTO card_numbers(part_id)
            SELECT p.id FROM parts p LEFT JOIN card_numbers n ON n.part_id=p.id
            WHERE n.number IS NULL ORDER BY p.created_at,p.id""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS assign_card_number AFTER INSERT ON parts
            BEGIN INSERT INTO card_numbers(part_id) VALUES(NEW.id); END""")


migrate_0003_mobile()


def catalogue_id():
    with connect() as c:
        return c.execute("SELECT id FROM catalogue_identity WHERE singleton=1").fetchone()["id"]


def number_for(part_id, user):
    with connect() as c:
        row = c.execute("""SELECT n.number FROM card_numbers n JOIN parts p ON p.id=n.part_id
            WHERE p.id=? AND p.organization_id=?""", (part_id, org_for(user))).fetchone()
    if not row:
        raise HTTPException(404, "Карточка не найдена")
    return str(row["number"]).zfill(6)


@app.get("/api/mobile/info")
def mobile_info():
    return {"service": "qr", "protocol": 1, "catalogue_id": catalogue_id()}


@app.get("/api/mobile/resolve/{number}")
def resolve_number(number: str, u=Depends(current_user)):
    if not number.isascii() or not number.isdecimal() or len(number) > 18 or int(number) < 1:
        raise HTTPException(404, "Номер не найден")
    with connect() as c:
        row = c.execute("""SELECT p.id AS part_id,p.organization_id AS project_id
            FROM card_numbers n JOIN parts p ON p.id=n.part_id
            JOIN memberships m ON m.organization_id=p.organization_id
            WHERE n.number=? AND m.user_id=?""", (int(number), u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Карточка не найдена или нет доступа к проекту")
    return dict(row)


@app.get("/api/mobile/parts/{part_id}/number")
def part_number(part_id: str, u=Depends(current_user)):
    return {"number": number_for(part_id, u)}


@app.get("/api/mobile/parts/{part_id}/label/{kind}/{extension}")
def label(part_id: str, kind: str, extension: str, u=Depends(current_user)):
    number = number_for(part_id, u)
    if kind not in ("qr", "datamatrix") or extension not in ("svg", "png", "pdf"):
        raise HTTPException(404, "Неизвестный формат маркировки")
    import zxingcpp
    fmt = zxingcpp.BarcodeFormat.QRCode if kind == "qr" else zxingcpp.BarcodeFormat.DataMatrix
    barcode = zxingcpp.create_barcode(number, fmt)
    if extension == "svg":
        data = barcode.to_svg(add_quiet_zones=True).encode("utf-8")
        mime = "image/svg+xml"
    else:
        from PIL import Image
        image = Image.fromarray(barcode.to_image(scale=10, add_quiet_zones=True)).convert("RGB")
        out = io.BytesIO()
        image.save(out, format=extension.upper(), dpi=(300, 300))
        data = out.getvalue()
        mime = "image/png" if extension == "png" else "application/pdf"
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{number}-{kind}.{extension}"'})


@app.get("/n/{number}")
def number_page(number: str):
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


# Presence is ephemeral; no device or IP history is persisted.
_presence = {}
_presence_lock = threading.Lock()
class Heartbeat(BaseModel):
    device: str = Field(min_length=36, max_length=36)

def prune_presence(now):
    for key, at in list(_presence.items()):
        if now - at > 45:
            del _presence[key]

@app.post("/api/mobile/heartbeat")
def heartbeat(data: Heartbeat, u=Depends(current_user)):
    try:
        device = str(uuid.UUID(data.device))
    except ValueError:
        raise HTTPException(400, "Неверный ID устройства")
    now = time.monotonic()
    with _presence_lock:
        prune_presence(now)
        key = (org_for(u), u["id"], device)
        if key not in _presence and len(_presence) >= 2000:
            raise HTTPException(429, "Слишком много клиентов")
        _presence[key] = now
    return {"status": "ok"}

@app.get("/api/mobile/presence")
def presence(u=Depends(current_user)):
    with _presence_lock:
        prune_presence(time.monotonic())
        return {"connected_devices": sum(1 for key in _presence if key[0] == org_for(u))}


def pairing_addresses(request):
    if not request.client or request.client.host != "127.0.0.1":
        raise HTTPException(403, "Откройте настройки на ПК через 127.0.0.1")
    from .launcher import lan_addresses
    port = int(os.getenv("QR_LAN_PORT") or request.url.port or 8765)
    return [{"ip": ip, "origin": f"http://{ip}:{port}"} for ip in lan_addresses()]


@app.get("/api/mobile/pairing")
def pairing(request: Request, u=Depends(current_user)):
    return {"catalogue_id": catalogue_id(), "addresses": pairing_addresses(request)}


@app.get("/api/mobile/pairing/{ip}/qr")
def pairing_qr(ip: str, request: Request, u=Depends(current_user)):
    address = next((x for x in pairing_addresses(request) if x["ip"] == ip), None)
    if not address:
        raise HTTPException(404, "IP-адрес уже недоступен. Обновите настройки.")
    import zxingcpp
    value = f'QRPAIR|{catalogue_id()}|{address["origin"]}'
    barcode = zxingcpp.create_barcode(value, zxingcpp.BarcodeFormat.QRCode)
    return Response(barcode.to_svg(add_quiet_zones=True), media_type="image/svg+xml")
