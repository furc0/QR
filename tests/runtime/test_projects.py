from fastapi.testclient import TestClient
from qr_server import features, main


def test_membership_roles_and_catalogue_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB", tmp_path / "projects.db")
    main.init()
    features.migrate()
    api = TestClient(main.app)

    def headers(response):
        return {"Authorization": "Bearer " + response.json()["token"]}

    admin = headers(api.post("/api/setup", json=dict(display_name="Admin", email="owner@test.org",
                    password="admin-password", organization_name="Original")))
    original = api.get("/api/me", headers=admin).json()["active_project_id"]
    part = api.post("/api/parts", headers=admin, json={"part_code": "01", "title": "Original part"}).json()["id"]
    account = dict(email="worker@test.org", display_name="Worker", password="worker-password")
    assert api.post("/api/project/users", headers=admin, json=account).status_code == 201
    worker = headers(api.post("/api/login", json=account))
    pid = api.post("/api/projects", headers=admin, json={"name": "Second"}).json()["id"]
    select = f"/api/projects/{pid}/select"
    assert api.post(select, headers=worker).status_code == 403
    second_admin = headers(api.post(select, headers=admin))
    assert api.get("/api/parts", headers=second_admin).json() == []
    assert api.get("/api/parts/" + part, headers=second_admin).status_code == 404
    assert api.get("/api/parts/" + part, headers=admin).status_code == 200
    assert api.post("/api/project/users", headers=second_admin, json=account).status_code == 409
    assert api.post("/api/project/members", headers=second_admin, json={"email": account["email"]}).status_code == 201
    second_worker = headers(api.post(select, headers=worker))
    info = api.get("/api/me", headers=second_worker).json()
    assert info["active_project_id"] == pid
    assert {row["id"] for row in info["organizations"]} == {original, pid}
    assert api.get("/api/project/users", headers=second_worker).status_code == 403
    assert api.post("/api/project/users", headers=second_worker, json=account).status_code == 403
    assert api.post("/api/projects", headers=second_worker, json={"name":"Blocked"}).status_code == 403
    assert len(api.get("/api/project/users", headers=second_admin).json()) == 2


def test_single_permanent_link(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB", tmp_path / "album.db")
    monkeypatch.setattr(features, "DATA", tmp_path)
    monkeypatch.delenv("QR_SHARE_ORIGIN", raising=False)
    main.init()
    features.migrate()
    features.migrate_0002_short_links()
    api = TestClient(main.app)

    def auth(response):
        return {"Authorization": "Bearer " + response.json()["token"]}

    admin = auth(api.post("/api/setup", json=dict(display_name="Owner", organization_name="First",
                  email="owner@qr.test", password="some-password")))
    second = api.post("/api/projects", headers=admin, json={"name":"Second"}).json()["id"]
    second_admin = auth(api.post(f"/api/projects/{second}/select", headers=admin))
    part = api.post("/api/parts", headers=second_admin, json={"part_code":"1","title":"Fixture"}).json()["id"]
    path = f"/api/parts/{part}/share"
    assert api.get(path, headers=second_admin).json()["permalink"] is None
    (tmp_path / "share-origin.txt").write_text("https://qr.example.test")
    link = api.get(path, headers=second_admin).json()["permalink"]
    code = link.rsplit("/", 1)[1]
    assert len(code) == 8 and link == "https://qr.example.test/s/" + code
    assert api.get("/s/" + code).status_code == 200
    resolve = "/api/shared/" + code
    assert api.get(resolve).status_code == 401
    assert api.get(resolve, headers=admin).json() == {"part_id":part,"project_id":second}
    account = dict(email="member@qr.test", display_name="Member", password="some-password")
    api.post("/api/project/users", headers=admin, json=account).raise_for_status()
    assert api.get(resolve, headers=auth(api.post("/api/login",json=account))).status_code == 404
    for revision in (b"initial", b"updated"):
        api.post(f"/api/parts/{part}/documents", headers=second_admin,
                 files={"file":("drawing.pdf", revision)}).raise_for_status()
    (tmp_path / "share-origin.txt").unlink()
    main.init()
    features.migrate_0002_short_links()
    assert TestClient(main.app).get(path, headers=second_admin).json()["permalink"] == link
