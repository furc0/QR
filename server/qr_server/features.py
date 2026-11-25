from __future__ import annotations
import hashlib, uuid, sqlite3, unicodedata
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .main import app, connect, org_for, current_user, DATA, FILES, WEB, stamp

router = APIRouter()
MODELS = DATA / "models"
MODELS.mkdir(parents=True, exist_ok=True)

def migrate():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS categories(
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(organization_id,name))""")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(parts)").fetchall()}
        if "category_id" not in cols:
            c.execute("ALTER TABLE parts ADD COLUMN category_id TEXT REFERENCES categories(id)")
        c.execute("""CREATE TABLE IF NOT EXISTS part_models(
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organizations(id),
            part_id TEXT NOT NULL REFERENCES parts(id), original_filename TEXT NOT NULL,
            file_format TEXT NOT NULL, storage_path TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            checksum_sha256 TEXT NOT NULL, created_at TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS part_models_part_idx ON part_models(part_id)")

migrate()

class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class CategoryAssignment(BaseModel):
    category_id: str | None = None

@router.get("/api/categories")
def list_categories(u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        rows = c.execute("""SELECT c.id,c.name,c.created_at,COUNT(p.id) AS part_count
            FROM categories c LEFT JOIN parts p ON p.category_id=c.id
            WHERE c.organization_id=? GROUP BY c.id ORDER BY c.name COLLATE NOCASE""",(oid,)).fetchall()
    return [dict(r) for r in rows]

@router.post("/api/categories")
def create_category(data: CategoryInput, u=Depends(current_user)):
    oid, cid = org_for(u), str(uuid.uuid4())
    name = unicodedata.normalize("NFC", data.name.strip())
    if not name:
        raise HTTPException(400, "Название категории обязательно")
    with connect() as c:
        existing = c.execute("SELECT name FROM categories WHERE organization_id=?", (oid,)).fetchall()
        if any(unicodedata.normalize("NFC", row["name"]).casefold() == name.casefold() for row in existing):
            raise HTTPException(409, "Такая категория уже существует")
        try:
            c.execute("INSERT INTO categories VALUES(?,?,?,?)",(cid,oid,name,stamp()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Такая категория уже существует")
    return {"id":cid,"name":name}

@router.patch("/api/categories/{category_id}")
def rename_category(category_id: str, data: CategoryInput, u=Depends(current_user)):
    oid = org_for(u)
    name = unicodedata.normalize("NFC", data.name.strip())
    if not name:
        raise HTTPException(400, "Название категории обязательно")
    with connect() as c:
        current = c.execute("SELECT id FROM categories WHERE id=? AND organization_id=?", (category_id,oid)).fetchone()
        if not current:
            raise HTTPException(404, "Категория не найдена")
        existing = c.execute("SELECT id,name FROM categories WHERE organization_id=? AND id<>?", (oid,category_id)).fetchall()
        if any(unicodedata.normalize("NFC", row["name"]).casefold() == name.casefold() for row in existing):
            raise HTTPException(409, "Такая категория уже существует")
        try:
            c.execute("UPDATE categories SET name=? WHERE id=? AND organization_id=?",(name,category_id,oid))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Такая категория уже существует")
    return {"id":category_id,"name":name}

@router.delete("/api/categories/{category_id}")
def delete_category(category_id: str, u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        if not c.execute("SELECT 1 FROM categories WHERE id=? AND organization_id=?",(category_id,oid)).fetchone():
            raise HTTPException(404, "Категория не найдена")
        c.execute("UPDATE parts SET category_id=NULL WHERE category_id=? AND organization_id=?",(category_id,oid))
        c.execute("DELETE FROM categories WHERE id=? AND organization_id=?",(category_id,oid))
    return {"deleted":True,"parts_preserved":True}

@router.patch("/api/parts/{part_id}/category")
def assign_category(part_id: str, data: CategoryAssignment, u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        if not c.execute("SELECT 1 FROM parts WHERE id=? AND organization_id=?",(part_id,oid)).fetchone():
            raise HTTPException(404, "Деталь не найдена")
        if data.category_id and not c.execute("SELECT 1 FROM categories WHERE id=? AND organization_id=?",(data.category_id,oid)).fetchone():
            raise HTTPException(404, "Категория не найдена")
        c.execute("UPDATE parts SET category_id=?,updated_at=? WHERE id=? AND organization_id=?",
                  (data.category_id,stamp(),part_id,oid))
    return {"category_id":data.category_id}

@router.get("/api/parts/{part_id}/share")
def part_share(part_id: str, u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        if not c.execute("SELECT 1 FROM parts WHERE id=? AND organization_id=?",(part_id,oid)).fetchone():
            raise HTTPException(404, "Деталь не найдена")
    return {"url":f"/parts/{part_id}","part_id":part_id,"access":"organization-authenticated"}

@router.get("/parts/{part_id}")
def part_page(part_id: str):
    # The page itself is addressable; its API data remains protected by organization login.
    return FileResponse(WEB / "index.html")

@router.get("/api/parts/{part_id}/models")
def list_models(part_id: str, u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        if not c.execute("SELECT 1 FROM parts WHERE id=? AND organization_id=?",(part_id,oid)).fetchone():
            raise HTTPException(404, "Деталь не найдена")
        rows = c.execute("""SELECT id,original_filename,file_format,size_bytes,checksum_sha256,created_at
            FROM part_models WHERE part_id=? AND organization_id=? ORDER BY created_at DESC""",(part_id,oid)).fetchall()
    return [dict(r) for r in rows]

@router.post("/api/parts/{part_id}/models")
async def upload_model(part_id: str, file: UploadFile = File(...), u=Depends(current_user)):
    oid = org_for(u)
    name = Path(file.filename or "model").name[:240]
    ext = Path(name).suffix.lower()
    if ext not in {".stl",".obj",".step",".stp"}:
        raise HTTPException(415, "Поддерживаются STL, OBJ, STEP и STP")
    with connect() as c:
        if not c.execute("SELECT 1 FROM parts WHERE id=? AND organization_id=?",(part_id,oid)).fetchone():
            raise HTTPException(404, "Деталь не найдена")
    mid = str(uuid.uuid4())
    folder = MODELS / oid / part_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (mid + ext)
    temporary = folder / (mid + ext + ".uploading")
    size_bytes = 0
    checksum = hashlib.sha256()
    try:
        with temporary.open("xb") as stored:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > 250 * 1024 * 1024:
                    raise HTTPException(413, "Максимальный размер 3D-модели — 250 МБ")
                stored.write(chunk)
                checksum.update(chunk)
        if size_bytes == 0:
            raise HTTPException(400, "Файл модели пуст")
        temporary.replace(path)
        with connect() as c:
            c.execute("INSERT INTO part_models VALUES(?,?,?,?,?,?,?,?,?)",
                      (mid,oid,part_id,name,ext[1:].upper(),str(path),size_bytes,checksum.hexdigest(),stamp()))
    except Exception:
        temporary.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {"id":mid,"filename":name,"format":ext[1:].upper(),"size_bytes":size_bytes}

@router.get("/api/models/{model_id}/download")
def download_model(model_id: str, u=Depends(current_user)):
    oid = org_for(u)
    with connect() as c:
        row = c.execute("SELECT * FROM part_models WHERE id=? AND organization_id=?",(model_id,oid)).fetchone()
    if not row:
        raise HTTPException(404, "3D-модель не найдена")
    path = Path(row["storage_path"]).resolve()
    if MODELS not in path.parents or not path.is_file():
        raise HTTPException(404, "Файл модели отсутствует")
    return FileResponse(path, filename=row["original_filename"], media_type="application/octet-stream")

app.include_router(router)
