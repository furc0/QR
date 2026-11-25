import uuid
from fastapi.testclient import TestClient
from qr_server.main import app, connect
from qr_server.mobile import migrate_0003_mobile
import zxingcpp
from PIL import Image
import io

client = TestClient(app)

def test_mobile_number_and_permissions():
    email = "mobile-" + uuid.uuid4().hex + "@example.test"
    # Existing suite initializes the database. Use a separate organization.
    from qr_server.main import pw_hash, stamp, make_token
    uid, oid = str(uuid.uuid4()), str(uuid.uuid4())
    with connect() as c:
        c.execute("INSERT INTO users VALUES(?,?,?,?,?)",(uid,email,"Mobile",pw_hash("test-password"),stamp()))
        c.execute("INSERT INTO organizations VALUES(?,?,?)",(oid,"Mobile Test",stamp()))
        c.execute("INSERT INTO memberships VALUES(?,?,?)",(uid,oid,"admin"))
    h = {"Authorization":"Bearer "+make_token(uid,oid)}
    p = client.post("/api/parts",headers=h,json={"part_code":"MOBILE","title":"Test"}).json()["id"]
    endpoint = f"/api/mobile/parts/{p}/number"
    n = client.get(endpoint,headers=h).json()["number"]
    migrate_0003_mobile()
    assert client.get(endpoint,headers=h).json()["number"] == n
    info = client.get("/api/mobile/info").json()
    assert info["catalogue_id"] == client.get("/api/mobile/info").json()["catalogue_id"]
    assert client.get("/api/mobile/resolve/"+n,headers=h).json()["part_id"] == p
    assert client.get("/api/mobile/resolve/"+n).status_code == 401
    assert client.get("/n/"+n).status_code == 200
    for kind in ("qr","datamatrix"):
        for ext in ("svg","png","pdf"):
            r = client.get(f"/api/mobile/parts/{p}/label/{kind}/{ext}",headers=h)
            assert r.status_code == 200, r.text
            if ext == "png":
                assert zxingcpp.read_barcode(Image.open(io.BytesIO(r.content))).text == n
    with connect() as c:
        c.execute("DELETE FROM memberships WHERE user_id=? AND organization_id=?",(uid,oid))
    assert client.get("/api/mobile/resolve/"+n,headers=h).status_code in (401,403,404)


def test_presence_requires_login():
    assert client.get("/api/mobile/presence").status_code == 401
    assert client.post("/api/mobile/heartbeat",json={"device":str(uuid.uuid4())}).status_code == 401
