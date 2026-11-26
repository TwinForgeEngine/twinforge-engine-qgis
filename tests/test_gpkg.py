"""'Publish a GeoPackage file': every layer with its stored QGIS style, chunked resumable upload, then the
layer list of the project is filled. Runs against a local server that speaks the TwinForge Engine upload API."""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_styles as T  # noqa: E402
import test_publish_style as P  # noqa: E402
from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsCoordinateTransformContext, QgsProject,  # noqa: E402
                       QgsRendererCategory, QgsVectorFileWriter, QgsVectorLayer)
from twinforge_engine_qgis.core.client import NexusClient  # noqa: E402

S = {"data": b"", "size": 0, "mismatch_once": True, "imported": [], "layers": [], "puts": 0, "keeps": []}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    _send = P.H._send
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""
    def do_POST(self):
        b = self._body(); path = urlparse(self.path).path
        if path.endswith("/gpkg-uploads"):
            j = json.loads(b); S.update(data=b"", size=j["size"])
            return self._send(201, {"id": "U1", "received": 0, "complete": False, "chunkSize": 4096})
        if path.endswith("/import"):
            j = json.loads(b); w = j["layers"][0]; S["keeps"].append(j["keep"])
            S["imported"].append(w); i = len(S["layers"])
            S["layers"].append({"id": f"L{i}", "name": w["name"], "title": w["title"], "kind": "vector"})
            return self._send(200, {"published": 1, "results": [
                {"ok": True, "source": w["source"], "name": w["name"], "layer": {"id": f"L{i}"}, "styleReduced": [], "stream": {"urls": {"mvt": "http://x/mvt"}}}]})
        self._send(404, {"detail": "no"})
    def do_PUT(self):
        b = self._body(); off = int(parse_qs(urlparse(self.path).query)["offset"][0]); S["puts"] += 1
        if S["mismatch_once"] and off > 0:
            S["mismatch_once"] = False
            return self._send(409, {"detail": "offset"}, "offset_mismatch")
        if off != len(S["data"]):
            return self._send(409, {"detail": "offset"}, "offset_mismatch")
        S["data"] += b
        self._send(200, {"id": "U1", "received": len(S["data"]), "complete": len(S["data"]) == S["size"]})
    def do_GET(self):
        path = urlparse(self.path).path
        if path.endswith("/gpkg-uploads/U1"):
            return self._send(200, {"id": "U1", "received": len(S["data"])})
        if path.endswith("/projects/P1/layers"):
            return self._send(200, {"layers": S["layers"]})
        self._send(404, {"detail": "no"})


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def make_gpkg():
    path = os.path.join(tempfile.mkdtemp(), "city.gpkg")
    for i, (kind, name) in enumerate((("poly", "Buildings"), ("line", "Road lines"))):
        lyr = T.layer(kind); lyr.setName(name)
        o = QgsVectorFileWriter.SaveVectorOptions(); o.driverName = "GPKG"; o.layerName = name
        if i:
            o.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
        r = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, path, QgsCoordinateTransformContext(), o)
        assert r[0] == QgsVectorFileWriter.WriterError.NoError, r
    # store a categorized style as the default style of the road layer, inside the GeoPackage
    roads = QgsVectorLayer(f"{path}|layername=Road lines", "r", "ogr"); assert roads.isValid()
    roads.setRenderer(QgsCategorizedSymbolRenderer("highway", [QgsRendererCategory(v, T.sym_for("line", c), v)
                                                               for v, c in zip(T.ROADS, ["#E67E22", "#8E44AD", "#3498DB", "#95A5A6"])]))
    (roads.saveStyleToDatabaseV2 if hasattr(roads, "saveStyleToDatabaseV2") else roads.saveStyleToDatabase)("default", "", True, "")
    del roads
    return path


def test_plan_reads_every_layer_and_its_stored_style():
    path = make_gpkg()
    d = P.dock_for("http://127.0.0.1:9")
    plan = d.gpkg_plan(path, taken={"buildings"})
    by = {p["source"]: p for p in plan}
    assert set(by) == {"Buildings", "Road lines"}
    assert by["Buildings"]["name"] == "buildings_2" and by["Road lines"]["name"] == "road_lines"
    st = by["Road lines"]["style"]
    assert st["renderer"] == "categorized" and st["field"] == "highway" and len(st["classes"]) == 4


def test_upload_resumes_and_layer_list_fills(base):
    path = make_gpkg()
    d = P.dock_for(base); d.scopes = ["gis:read", "gis:publish"]
    d.on_publish_gpkg(path)
    t0 = time.time()
    assert d.remote.count() == 1 and not d.gpkg_btn.isEnabled()          # "No layers in this project yet", task running
    while not d.gpkg_btn.isEnabled() and time.time() - t0 < 30:
        QgsApplication.processEvents(); time.sleep(0.02)
    assert S["data"] == Path(path).read_bytes() and S["puts"] >= 3      # 4 KiB chunks, one 409 resumed
    assert {w["source"] for w in S["imported"]} == {"Buildings", "Road lines"} and S["keeps"] == [True, False]
    assert d.remote.count() == 2 and "Road lines" in d.remote.item(1).text() + d.remote.item(0).text()
    assert d.last_error is None and d.url.text() == "http://x/mvt"
