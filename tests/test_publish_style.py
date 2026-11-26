"""Panel publish path against a local server that validates styles exactly like TwinForge Engine
(core/tfstyle.py + field inference on the uploaded GeoJSON). Covers the 0.2.3 'style could not be read' bug."""
import json, os, sys, threading
from email.parser import BytesParser
from email.policy import default as POLICY
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_styles as T  # noqa: E402  (QGIS app + layer helpers)
from qgis.core import QgsApplication, QgsCategorizedSymbolRenderer, QgsMessageLog, QgsRendererCategory  # noqa: E402
from twinforge_engine_qgis.core import tfstyle  # noqa: E402
from twinforge_engine_qgis.core.client import NexusClient  # noqa: E402
from twinforge_engine_qgis.core.style_export import server_fields  # noqa: E402
GOOD = "tft_" + "S" * 43
SEEN = {"styles": [], "refuse_next": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, err=None):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        if err: self.send_header("X-TF-Error", err)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        msg = BytesParser(policy=POLICY).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw)
        parts = {p.get_param("name", header="content-disposition"): p.get_payload(decode=True) for p in msg.iter_parts()}
        style = json.loads(parts["style"]); SEEN["styles"].append(style)
        if SEEN["refuse_next"]:
            SEEN["refuse_next"] -= 1
            return self._send(422, {"detail": "test refusal"}, "style_invalid")
        try:
            st = tfstyle.normalize(style, sorted(server_fields(parts["file"])))
        except tfstyle.StyleError as e:
            return self._send(422, {"detail": str(e)}, "style_invalid")
        self._send(201, {"layer": {"id": "L1"}, "styleReduced": st["reduced"], "stream": {"urls": {"mvt": "http://x/s/a/mvt"}}})


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


class _Bar:
    def pushMessage(self, *a, **k): pass


class Iface:
    def messageBar(self): return _Bar()


DOCKS = []


def dock_for(base):
    from twinforge_engine_qgis.dock import TwinForgeDock
    d = TwinForgeDock(Iface()); d.client = NexusClient(GOOD, base, timeout=10)
    d.project.addItem("p", "P1"); d.project.setCurrentIndex(d.project.count() - 1); DOCKS.append(d)
    return d


def test_road_layer_with_empty_field_publishes_with_its_categories(base):
    lyr = T.layer("line")
    lyr.setRenderer(QgsCategorizedSymbolRenderer("highway", [QgsRendererCategory(v, T.sym_for("line", c), v)
                                                             for v, c in zip(T.ROADS, ["#E67E22", "#8E44AD", "#3498DB", "#95A5A6"])]))
    lyr.setLabelsEnabled(False)
    r = dock_for(base)._publish_one(lyr)
    st = SEEN["styles"][-1]
    assert r["layer"]["id"] == "L1" and st["renderer"] == "categorized" and len(SEEN["styles"]) == 1
    assert "ref" not in [f["name"] for f in st["popup"]["fields"]]


def test_server_refusal_falls_back_to_one_colour_and_logs_why(base, monkeypatch):
    logs = []
    import twinforge_engine_qgis.dock as D

    class _Log:
        @staticmethod
        def logMessage(m, tag="", level=None): logs.append(m)
    monkeypatch.setattr(D, "QgsMessageLog", _Log)
    SEEN["refuse_next"] = 1; n0 = len(SEEN["styles"])
    lyr = T.layer("line"); lyr.setRenderer(T._rule_renderer("line", [("length($geometry) > 10", "#E67E22")]))
    r = dock_for(base)._publish_one(lyr)
    assert r["layer"]["id"] == "L1" and len(SEEN["styles"]) == n0 + 2
    assert SEEN["styles"][-1]["renderer"] == "single" and SEEN["styles"][-1]["single"]["color"] == "#E67E22"
    assert any("test refusal" in m for m in logs) and any("Rule-based" in m for m in logs), logs
