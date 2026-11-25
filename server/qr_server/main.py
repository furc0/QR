from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, time, uuid, base64
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Depends, Header, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.getenv("QR_DATA_DIR",ROOT/"data")).resolve()
FILES=DATA/"files"; WEB=ROOT/"web"; DB=DATA/"qr.sqlite3"; SECRET=DATA/".session_secret"
DATA.mkdir(parents=True,exist_ok=True); FILES.mkdir(parents=True,exist_ok=True)
app=FastAPI(title="QR Engineering Catalogue API",version="0.1.0")
origins=[x.strip() for x in os.getenv("QR_CORS_ORIGINS","").split(",") if x.strip()]
if origins:
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["*"],allow_headers=["Authorization","Content-Type"])

@contextmanager
def connect():
    c=sqlite3.connect(DB,timeout=20); c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memberships(user_id TEXT NOT NULL REFERENCES users(id),organization_id TEXT NOT NULL REFERENCES organizations(id),role TEXT NOT NULL,PRIMARY KEY(user_id,organization_id));
        CREATE TABLE IF NOT EXISTS parts(id TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),part_code TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL CHECK(kind IN ('part','assembly')),material TEXT NOT NULL DEFAULT '',mass TEXT NOT NULL DEFAULT '',dimensions TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(organization_id,part_code));
        CREATE INDEX IF NOT EXISTS parts_org_title_idx ON parts(organization_id,title);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,part_id TEXT NOT NULL REFERENCES parts(id),revision INTEGER NOT NULL,snapshot_json TEXT NOT NULL,summary TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(part_id,revision));
        CREATE TABLE IF NOT EXISTS bom_items(id TEXT PRIMARY KEY,organization_id TEXT NOT NULL,assembly_part_id TEXT NOT NULL REFERENCES parts(id),component_part_id TEXT NOT NULL REFERENCES parts(id),quantity REAL NOT NULL CHECK(quantity>0),unit_code TEXT NOT NULL,position_no INTEGER NOT NULL,created_at TEXT NOT NULL,CHECK(assembly_part_id<>component_part_id));
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,organization_id TEXT NOT NULL,part_id TEXT NOT NULL REFERENCES parts(id),original_filename TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS document_versions(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),version_number INTEGER NOT NULL,storage_path TEXT NOT NULL,mime_type TEXT NOT NULL,size_bytes INTEGER NOT NULL,checksum_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(document_id,version_number));
        """)
init()
def stamp(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def pw_hash(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    return salt.hex()+":"+hashlib.pbkdf2_hmac("sha256",password.encode(),salt,310000).hex()
def pw_ok(password,encoded):
    try:
        s,d=encoded.split(":",1); return hmac.compare_digest(pw_hash(password,bytes.fromhex(s)).split(":",1)[1],d)
    except Exception: return False
def secret():
    if not SECRET.exists(): SECRET.write_bytes(secrets.token_bytes(32))
    return SECRET.read_bytes()
def make_token(uid):
    body=base64.urlsafe_b64encode(json.dumps({"sub":uid,"exp":int(time.time())+1209600},separators=(",",":")).encode()).rstrip(b"=")
    sig=hmac.new(secret(),body,hashlib.sha256).digest()
    return (body+b"."+base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()
def current_user(authorization:str|None=Header(default=None)):
    try:
        if not authorization or not authorization.startswith("Bearer "): raise ValueError()
        body,sig=authorization[7:].encode().split(b".",1)
        supplied=base64.urlsafe_b64decode(sig+b"="*(-len(sig)%4))
        if not hmac.compare_digest(hmac.new(secret(),body,hashlib.sha256).digest(),supplied): raise ValueError()
        p=json.loads(base64.urlsafe_b64decode(body+b"="*(-len(body)%4)))
        if p["exp"]<int(time.time()): raise ValueError()
        with connect() as c: u=c.execute("SELECT * FROM users WHERE id=?",(p["sub"],)).fetchone()
        if not u: raise ValueError()
        return u
    except Exception: raise HTTPException(401,"Сессия недействительна. Войдите снова.")
def org_for(user):
    with connect() as c: r=c.execute("SELECT organization_id FROM memberships WHERE user_id=? ORDER BY rowid LIMIT 1",(user["id"],)).fetchone()
    if not r: raise HTTPException(403,"Нет членства в организации")
    return r["organization_id"]

class Setup(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    display_name:str=Field(min_length=2,max_length=100)
    password:str=Field(min_length=10,max_length=200)
    organization_name:str=Field(min_length=2,max_length=120)
class Login(BaseModel):
    email:str; password:str
class Part(BaseModel):
    part_code:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=1,max_length=240)
    description:str=""
    kind:str="part"
    material:str=""
    mass:str=""
    dimensions:str=""
    category_id:str|None=None
class Bom(BaseModel):
    component_part_id:str
    quantity:float=Field(gt=0)
    unit_code:str="шт."
    position_no:int=0

@app.get("/api/health")
def health():
    with connect() as c: c.execute("SELECT 1")
    return {"status":"ok","service":"qr","storage":"sqlite","mode":"local-server"}
@app.get("/api/setup-status")
def setup_status():
    with connect() as c: n=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    return {"setup_required":n==0}
@app.post("/api/setup")
def setup(data:Setup):
    with connect() as c:
        if c.execute("SELECT 1 FROM users LIMIT 1").fetchone(): raise HTTPException(409,"Первичная настройка уже выполнена")
        uid,oid,t=str(uuid.uuid4()),str(uuid.uuid4()),stamp()
        try:
            c.execute("INSERT INTO users VALUES(?,?,?,?,?)",(uid,data.email.strip().lower(),data.display_name,pw_hash(data.password),t))
            c.execute("INSERT INTO organizations VALUES(?,?,?)",(oid,data.organization_name,t))
            c.execute("INSERT INTO memberships VALUES(?,?,?)",(uid,oid,"admin"))
        except sqlite3.IntegrityError: raise HTTPException(400,"Не удалось создать пользователя. Проверьте email.")
    return {"token":make_token(uid)}
@app.post("/api/login")
def login(data:Login):
    with connect() as c: u=c.execute("SELECT * FROM users WHERE email=?",(data.email.strip().lower(),)).fetchone()
    if not u or not pw_ok(data.password,u["password_hash"]): raise HTTPException(401,"Неверный email или пароль")
    return {"token":make_token(u["id"])}
@app.get("/api/me")
def me(u=Depends(current_user)):
    with connect() as c:
        orgs=c.execute("SELECT o.id,o.name,m.role FROM organizations o JOIN memberships m ON m.organization_id=o.id WHERE m.user_id=?",(u["id"],)).fetchall()
    return {"user":{"id":u["id"],"email":u["email"],"display_name":u["display_name"]},"organizations":[dict(x) for x in orgs]}
@app.get("/api/parts")
def parts(q:str="",kind:str="",u=Depends(current_user)):
    oid=org_for(u); sql="SELECT * FROM parts WHERE organization_id=?"; args=[oid]
    if q.strip():
        like="%"+q.strip()+"%"; sql+=" AND (part_code LIKE ? OR title LIKE ? OR description LIKE ?)"; args += [like,like,like]
    if kind in ("part","assembly"): sql+=" AND kind=?"; args.append(kind)
    sql+=" ORDER BY updated_at DESC"
    with connect() as c: rows=c.execute(sql,args).fetchall()
    return [dict(x) for x in rows]
@app.post("/api/parts")
def create_part(data:Part,u=Depends(current_user)):
    if data.kind not in ("part","assembly"): raise HTTPException(400,"Недопустимый тип")
    oid,t,pid=org_for(u),stamp(),str(uuid.uuid4())
    with connect() as c:
        if data.category_id and not c.execute("SELECT 1 FROM categories WHERE id=? AND organization_id=?",(data.category_id,oid)).fetchone():
            raise HTTPException(404,"Категория не найдена в этой организации")
        try:
            c.execute("INSERT INTO parts(id,organization_id,part_code,title,description,kind,material,mass,dimensions,created_at,updated_at,category_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(pid,oid,data.part_code.strip(),data.title.strip(),data.description,data.kind,data.material,data.mass,data.dimensions,t,t,data.category_id))
            c.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),pid,1,json.dumps(data.model_dump(),ensure_ascii=False),"Создание",t))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc): raise HTTPException(409,"Код уже используется в этой организации")
            raise
    return {"id":pid,"revision":1}
@app.get("/api/parts/{pid}")
def part_detail(pid:str,u=Depends(current_user)):
    oid=org_for(u)
    with connect() as c:
        p=c.execute("SELECT * FROM parts WHERE id=? AND organization_id=?",(pid,oid)).fetchone()
        if not p: raise HTTPException(404,"Карточка не найдена")
        docs=c.execute("SELECT d.id,d.original_filename,v.version_number,v.size_bytes,v.mime_type,v.checksum_sha256 FROM documents d JOIN document_versions v ON v.document_id=d.id WHERE d.part_id=? ORDER BY v.created_at DESC",(pid,)).fetchall()
        bom=c.execute("SELECT b.*,p.part_code,p.title FROM bom_items b JOIN parts p ON p.id=b.component_part_id WHERE b.assembly_part_id=? AND b.organization_id=? ORDER BY b.position_no",(pid,oid)).fetchall()
    return {"part":dict(p),"documents":[dict(x) for x in docs],"bom":[dict(x) for x in bom]}
@app.post("/api/parts/{pid}/bom")
def add_bom(pid:str,data:Bom,u=Depends(current_user)):
    oid,t=org_for(u),stamp()
    if pid==data.component_part_id: raise HTTPException(400,"Сборка не может содержать саму себя")
    with connect() as c:
        parent=c.execute("SELECT kind FROM parts WHERE id=? AND organization_id=?",(pid,oid)).fetchone()
        comp=c.execute("SELECT id FROM parts WHERE id=? AND organization_id=?",(data.component_part_id,oid)).fetchone()
        if not parent or parent["kind"]!="assembly": raise HTTPException(400,"Родитель должен быть сборкой")
        if not comp: raise HTTPException(404,"Компонент не найден")
        cycle=c.execute("""WITH RECURSIVE walk(id) AS (
          SELECT component_part_id FROM bom_items WHERE assembly_part_id=? AND organization_id=?
          UNION SELECT b.component_part_id FROM bom_items b JOIN walk w ON b.assembly_part_id=w.id WHERE b.organization_id=?)
          SELECT 1 FROM walk WHERE id=? LIMIT 1""",(data.component_part_id,oid,oid,pid)).fetchone()
        if cycle: raise HTTPException(409,"Изменение создаёт цикл в спецификации")
        bid=str(uuid.uuid4()); c.execute("INSERT INTO bom_items VALUES(?,?,?,?,?,?,?,?)",(bid,oid,pid,data.component_part_id,data.quantity,data.unit_code,data.position_no,t))
    return {"id":bid}
@app.post("/api/parts/{pid}/documents")
async def upload(pid:str,file:UploadFile=File(...),u=Depends(current_user)):
    oid,t=org_for(u),stamp()
    with connect() as c:
        if not c.execute("SELECT 1 FROM parts WHERE id=? AND organization_id=?",(pid,oid)).fetchone(): raise HTTPException(404,"Карточка не найдена")
    raw=await file.read()
    if len(raw)>100*1024*1024: raise HTTPException(413,"Максимум 100 МБ на файл в MVP")
    did,vid=str(uuid.uuid4()),str(uuid.uuid4()); folder=FILES/oid/pid/did; folder.mkdir(parents=True,exist_ok=True)
    path=folder/"v1.bin"; path.write_bytes(raw); name=Path(file.filename or "document.bin").name[:240]
    with connect() as c:
        c.execute("INSERT INTO documents VALUES(?,?,?,?)",(did,oid,pid,name,t))
        c.execute("INSERT INTO document_versions VALUES(?,?,?,?,?,?,?,?)",(vid,did,1,str(path),file.content_type or "application/octet-stream",len(raw),hashlib.sha256(raw).hexdigest(),t))
    return {"document_id":did,"filename":name,"size_bytes":len(raw)}
@app.get("/api/documents/{did}/download")
def download(did:str,u=Depends(current_user)):
    oid=org_for(u)
    with connect() as c:
        r=c.execute("SELECT v.storage_path,d.original_filename FROM documents d JOIN document_versions v ON v.document_id=d.id WHERE d.id=? AND d.organization_id=? ORDER BY v.version_number DESC LIMIT 1",(did,oid)).fetchone()
    if not r: raise HTTPException(404,"Файл не найден")
    path=Path(r["storage_path"]).resolve()
    if FILES not in path.parents or not path.is_file(): raise HTTPException(404,"Файл отсутствует")
    return FileResponse(path,filename=r["original_filename"])
from . import features\n\nif WEB.exists(): app.mount("/",StaticFiles(directory=WEB,html=True),name="web")
