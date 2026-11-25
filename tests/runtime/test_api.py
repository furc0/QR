from fastapi.testclient import TestClient
from qr_server.main import app

client = TestClient(app)
token = None

def auth():
    return {"Authorization": "Bearer " + token}

def create_part(code, title, kind="part"):
    r = client.post("/api/parts", headers=auth(), json={
        "part_code": code, "title": title, "kind": kind,
        "description": "", "material": "Сталь", "mass": "1.2", "dimensions": "10x20x30"
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]

def test_first_run_auth_catalog_and_tenant_code_uniqueness():
    global token
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/setup-status").json()["setup_required"] is True
    r = client.post("/api/setup", json={
        "email": "admin@example.test", "display_name": "Admin",
        "password": "correct horse battery", "organization_name": "Test Org"
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    assert client.get("/api/me", headers=auth()).status_code == 200

    part_id = create_part("A-001", "Test bracket")
    assert client.get("/api/parts", headers=auth()).json()[0]["id"] == part_id
    duplicate = client.post("/api/parts", headers=auth(), json={
        "part_code": "A-001", "title": "Duplicate", "kind": "part"
    })
    assert duplicate.status_code == 409

    login = client.post("/api/login", json={
        "email": "admin@example.test", "password": "correct horse battery"
    })
    assert login.status_code == 200
    assert client.post("/api/login", json={
        "email": "admin@example.test", "password": "wrong password"
    }).status_code == 401

def test_bom_rejects_cycles_and_accepts_valid_rows():
    a = create_part("ASM-A", "Assembly A", "assembly")
    b = create_part("ASM-B", "Assembly B", "assembly")
    leaf = create_part("P-LEAF", "Leaf component")
    valid = client.post("/api/parts/" + a + "/bom", headers=auth(),
                        json={"component_part_id": leaf, "quantity": 2, "unit_code": "шт.", "position_no": 1})
    assert valid.status_code == 200, valid.text
    assert client.post("/api/parts/" + a + "/bom", headers=auth(),
                       json={"component_part_id": b, "quantity": 1}).status_code == 200
    cycle = client.post("/api/parts/" + b + "/bom", headers=auth(),
                        json={"component_part_id": a, "quantity": 1})
    assert cycle.status_code == 409

def test_file_upload_and_download():
    part_id = create_part("FILE-01", "Drawing holder")
    uploaded = client.post("/api/parts/" + part_id + "/documents", headers=auth(),
                           files={"file": ("drawing.txt", b"QR test drawing", "text/plain")})
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()["document_id"]
    downloaded = client.get("/api/documents/" + doc_id + "/download", headers=auth())
    assert downloaded.status_code == 200
    assert downloaded.content == b"QR test drawing"


def test_categories_share_links_and_3d_model_upload():
    part_id = create_part("CAT-3D-01", "Rotor support")
    created = client.post("/api/categories", headers=auth(), json={"name": "Кронштейны"})
    assert created.status_code == 200, created.text
    category_id = created.json()["id"]
    assigned = client.patch("/api/parts/" + part_id + "/category", headers=auth(),
                            json={"category_id": category_id})
    assert assigned.status_code == 200
    detail = client.get("/api/parts/" + part_id, headers=auth()).json()["part"]
    assert detail["category_id"] == category_id

    share = client.get("/api/parts/" + part_id + "/share", headers=auth())
    assert share.status_code == 200
    assert share.json()["url"] == "/parts/" + part_id
    assert client.get("/parts/" + part_id).status_code == 200

    model = client.post("/api/parts/" + part_id + "/models", headers=auth(),
                        files={"file": ("sample.stl", b"solid test\\nendsolid test", "model/stl")})
    assert model.status_code == 200, model.text
    model_id = model.json()["id"]
    listing = client.get("/api/parts/" + part_id + "/models", headers=auth())
    assert listing.status_code == 200
    assert listing.json()[0]["file_format"] == "STL"
    download = client.get("/api/models/" + model_id + "/download", headers=auth())
    assert download.status_code == 200
    assert download.content == b"solid test\\nendsolid test"

    deleted = client.delete("/api/categories/" + category_id, headers=auth())
    assert deleted.status_code == 200
    assert deleted.json()["parts_preserved"] is True
    assert client.get("/api/parts/" + part_id, headers=auth()).json()["part"]["category_id"] is None
