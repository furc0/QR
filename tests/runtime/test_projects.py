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
