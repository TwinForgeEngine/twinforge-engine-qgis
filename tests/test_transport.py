"""Both transports (QgsNetworkAccessManager and urllib) against a local HTTP server: JSON, multipart upload, X-TF-Error mapping."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication
APP = QgsApplication.instance()
from twinforge_engine_qgis.core.client import NexusClient, NexusError, VERSION
GOOD = "tft_" + "A" * 43
SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, err=None):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        if err: self.send_header("X-TF-Error", err)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _auth(self):
        SEEN.append({"ua": self.headers.get("User-Agent"), "auth_ok": self.headers.get("Authorization") == "Bearer " + GOOD})
        if self.headers.get("Authorization") != "Bearer " + GOOD:
            self._send(401, {"detail": "This access token is not valid."}, "token_invalid"); return False
        return True
    def do_GET(self):
        if not self._auth(): return
        if self.path == "/api/v1/gis/me": return self._send(200, {"name": "QGIS", "scopes": ["gis:read", "gis:publish"]})
        self._send(404, {"detail": "nope"}, "project_not_found")
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n)
        if not self._auth(): return
        if self.path.endswith("/layers/vector"):
            ok = b'name="name"' in body and b'filename="roads.geojson"' in body and "multipart/form-data; boundary=" in self.headers.get("Content-Type", "")
            return self._send(201 if ok else 422, {"layer": {"id": "L1"}, "bytes": n}, None if ok else "geojson_invalid")
        if self.path == "/api/v1/gis/projects/personal": return self._send(200, {"id": "P1", "name": "My layers", "role": "owner"})
        self._send(429, {"detail": "slow"}, "rate_limited")


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H); t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.mark.parametrize("tr", ["qgis", "urllib"])
def test_transport(base, tr):
    c = NexusClient(GOOD, base, timeout=10, transport=tr)
    assert c.me()["scopes"] == ["gis:read", "gis:publish"]
    assert c.personal_project()["name"] == "My layers"
    r = c.publish_vector("P1", "roads", "Roads", b'{"type":"FeatureCollection","features":[]}' * 2000, {"renderer": "single"})
    assert r["layer"]["id"] == "L1" and r["bytes"] > 80000
    with pytest.raises(NexusError) as e:
        c._req("POST", "/other", b"{}", "application/json")
    assert e.value.status == 429 and e.value.code == "rate_limited"
    with pytest.raises(NexusError) as e:
        NexusClient("tft_" + "B" * 43, base, transport=tr).me()
    assert e.value.status == 401 and e.value.code == "token_invalid" and e.value.message == "This access token is not valid."
    with pytest.raises(NexusError) as e:
        NexusClient(GOOD, "http://127.0.0.1:9", timeout=3, transport=tr).me()
    assert e.value.code == "network"
    ua = [x["ua"] for x in SEEN if x["auth_ok"]][-1]
    assert ("QGIS/" in ua) if tr == "qgis" else ua == f"TwinForgeEngineQGIS/{VERSION}"   # QGIS sets its own User-Agent


def test_default_transport_inside_qgis_is_qgis():
    assert NexusClient(GOOD).transport == "qgis"
