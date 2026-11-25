"""Mobile catalogue locators. Numbers are permanent within a catalogue."""
import io
import uuid
from fastapi import Depends, HTTPException
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
