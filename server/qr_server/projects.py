"""Each project uses the catalogue's existing organization and membership boundary."""
import sqlite3
import uuid
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .main import app, connect, current_user, make_token, org_for, project_admin, pw_hash, stamp


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MemberInput(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: Literal["member", "admin"] = "member"


class UserInput(MemberInput):
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=200)


@app.post("/api/projects", status_code=201)
def create_project(data: ProjectInput, user=Depends(project_admin)):
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Введите название проекта")
    pid = str(uuid.uuid4())
    with connect() as db:
        db.execute("INSERT INTO organizations VALUES(?,?,?)", (pid, name, stamp()))
        db.execute("INSERT INTO memberships VALUES(?,?,?)", (user["id"], pid, "admin"))
    return {"id": pid, "name": name}


@app.post("/api/projects/{pid}/select")
def select_project(pid: str, user=Depends(current_user)):
    with connect() as db:
        member = db.execute("SELECT 1 FROM memberships WHERE user_id=? AND organization_id=?",
                            (user["id"], pid)).fetchone()
    if not member:
        raise HTTPException(403, "Нет доступа к проекту")
    return {"token": make_token(user["id"], pid)}


@app.get("/api/project/users")
def project_users(user=Depends(project_admin)):
    with connect() as db:
        rows = db.execute("""SELECT u.display_name,u.email,m.role FROM users u
            JOIN memberships m ON m.user_id=u.id WHERE m.organization_id=?
            ORDER BY u.display_name,u.email""", (org_for(user),)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/project/users", status_code=201)
def create_user(data: UserInput, user=Depends(project_admin)):
    name = data.display_name.strip()
    if len(name) < 2:
        raise HTTPException(400, "Введите имя пользователя")
    uid = str(uuid.uuid4())
    try:
        with connect() as db:
            db.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                       (uid, data.email.lower(), name, pw_hash(data.password), stamp()))
            db.execute("INSERT INTO memberships VALUES(?,?,?)", (uid, org_for(user), data.role))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Этот email уже зарегистрирован. Используйте добавление по email.")
    return {"id": uid}


@app.post("/api/project/members", status_code=201)
def add_existing_member(data: MemberInput, user=Depends(project_admin)):
    with connect() as db:
        row = db.execute("SELECT id FROM users WHERE email=?", (data.email.lower(),)).fetchone()
        if not row:
            raise HTTPException(404, "Пользователь с таким email не зарегистрирован")
        try:
            db.execute("INSERT INTO memberships VALUES(?,?,?)", (row["id"], org_for(user), data.role))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Пользователь уже участвует в проекте")
    return {"id": row["id"]}
