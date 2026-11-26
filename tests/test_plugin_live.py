"""Headless QGIS 3.40 LTR tests of "TwinForge Engine for QGIS" 0.2.0.
Unit parts always run. Live parts run against TF_LIVE_BASE (default https://twinforgeengine.online) when TF_LIVE_TOKENS
points to a JSON file {"full": tft_ (gis:read+gis:publish), "read": tft_ (gis:read), "expired": tft_} of a throwaway test account.
Tokens are read from that file only and never printed.
Run: QT_QPA_PLATFORM=offscreen python3 -m pytest -q qgis-plugin/tests/test_plugin_live.py"""
from __future__ import annotations

import configparser
import json
import math
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
PLUG = ROOT
sys.path.insert(0, str(PLUG))
from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsClassificationEqualInterval, QgsFillSymbol,  # noqa: E402
                       QgsGraduatedSymbolRenderer, QgsProject, QgsRasterLayer, QgsRendererCategory, QgsRuleBasedRenderer,
                       QgsVectorLayer)

APP = QgsApplication.instance()
from qgis.PyQt.QtCore import Qt  # noqa: E402
from twinforge_engine_qgis import i18n  # noqa: E402
from twinforge_engine_qgis.core.client import NexusClient, VERSION  # noqa: E402
from twinforge_engine_qgis.core.style_export import export_style  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "data"


def _make_raster():  # synthetic surface temperature, plain (non-COG) GeoTIFF
    fp = SAMPLES / "not_a_cog.tif"
    if fp.exists():
        return
    from osgeo import gdal, osr
    n = 256; ds = gdal.GetDriverByName("GTiff").Create(str(fp), n, n, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((100.52, 0.02 / n, 0, 13.745, 0, -0.02 / n)); sr = osr.SpatialReference(); sr.ImportFromEPSG(4326); ds.SetProjection(sr.ExportToWkt())
    b = ds.GetRasterBand(1); b.WriteRaster(0, 0, n, n, bytes(__import__("array").array("f", [28 + 8 * ((x * y) % n) / n for y in range(n) for x in range(n)]))); ds = None


_make_raster()
SHOTS = Path(os.environ.get("TF_SHOTS", str(PLUG / "shots"))); SHOTS.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("TF_LIVE_BASE", "https://twinforgeengine.online")
TOKF = os.environ.get("TF_LIVE_TOKENS", "")
TOK = json.loads(Path(TOKF).read_text()) if TOKF and Path(TOKF).exists() else None
live = pytest.mark.skipif(TOK is None, reason="no live test tokens")
COLORS = {"residential": "#2BB59A", "commercial": "#4C8DDE", "mixed": "#E3B341", "public": "#A77BD8", "industrial": "#8AA8A1"}
LABELS = {"residential": "ที่อยู่อาศัย", "commercial": "พาณิชยกรรม", "mixed": "ผสม", "public": "สาธารณะ", "industrial": "อุตสาหกรรม"}
STATE: dict = {}


def buildings_layer():
    lyr = QgsVectorLayer(str(SAMPLES / "buildings.geojson"), "QGIS smoke buildings", "ogr")
    assert lyr.isValid()
    cats = [QgsRendererCategory(v, QgsFillSymbol.createSimple({"color": c, "outline_color": "#0D2420"}), LABELS[v]) for v, c in COLORS.items()]
    lyr.setRenderer(QgsCategorizedSymbolRenderer("typ_code", cats))
    return lyr


# ------------------------------------------------------------------ unit
def test_categorized_export_matches_qgis():
    lyr = buildings_layer()
    st = export_style(lyr.renderer(), extrusion_field="height_m", label_field="name")
    assert st["renderer"] == "categorized" and st["field"] == "typ_code"
    assert {c["value"]: c["color"] for c in st["classes"]} == COLORS
    assert st["classes"][0]["label"] == "ที่อยู่อาศัย" and st["classes"][0]["outline"] == "#0D2420" and st["reduced"] == []


def test_graduated_export_matches_qgis():
    lyr = QgsVectorLayer(str(SAMPLES / "districts.geojson"), "Districts", "ogr")
    r = QgsGraduatedSymbolRenderer("pop_density"); r.setClassificationMethod(QgsClassificationEqualInterval()); r.updateClasses(lyr, 4)
    lyr.setRenderer(r)
    st = export_style(lyr.renderer())
    assert st["renderer"] == "graduated" and len(st["ranges"]) == 4


def test_rule_based_is_reduced_not_failed():
    lyr = buildings_layer()
    root = QgsRuleBasedRenderer.Rule(None)
    root.appendChild(QgsRuleBasedRenderer.Rule(QgsFillSymbol.createSimple({"color": "#123456"}), filterExp='"floors" > 10'))
    lyr.setRenderer(QgsRuleBasedRenderer(root))
    st = export_style(lyr.renderer())
    assert st["renderer"] == "single" and st["reduced"]


def test_three_languages_complete_and_clean(monkeypatch):
    for L in ("th", "en", "ja"):
        monkeypatch.setenv("TWINFORGE_LANG", L)
        assert i18n.lang() == L
        for k in i18n.T["en"]:
            s = i18n.tr(k, name="x", n=1, m=2, file="a.gpkg")
            assert s and "\u00b7" not in s, (L, k)
        assert i18n.err_text("token_expired") != i18n.ERRORS["en"]["network"]
    monkeypatch.setenv("TWINFORGE_LANG", "de")
    assert i18n.lang() == "en"


def test_zip_and_metadata_ready_for_repository():
    zp = ROOT / f"dist-plugin/twinforge_engine_qgis-{VERSION}.zip"
    assert zp.exists(), "run build_zip.sh first"
    z = zipfile.ZipFile(zp); names = z.namelist()
    assert all(n.startswith("twinforge_engine_qgis/") for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    for need in ("__init__.py", "metadata.txt", "icon.png", "LICENSE", "README.md", "plugin.py", "dock.py", "i18n.py", "core/client.py"):
        assert "twinforge_engine_qgis/" + need in names, need
    cp = configparser.ConfigParser(); cp.read_string(z.read("twinforge_engine_qgis/metadata.txt").decode())
    g = cp["general"]
    for k in ("name", "qgisMinimumVersion", "description", "about", "version", "author", "email", "homepage", "tracker", "repository", "license", "icon"):
        assert g.get(k), k
    assert g["version"] == VERSION and g["experimental"] == "False"
    blob = b"".join(z.read(n) for n in names if n.endswith((".py", ".txt")))
    assert b"tft_" + b"A" * 8 not in blob and "\u00b7".encode() not in blob


# ------------------------------------------------------------------ live
class _Bar:
    def __init__(self): self.msgs = []
    def pushMessage(self, title, text, level=0, duration=0): self.msgs.append(text)


class FakeIface:
    def __init__(self): self.bar = _Bar()
    def messageBar(self): return self.bar


def wait_tasks(timeout=180):
    t0 = time.time()
    while QgsApplication.taskManager().countActiveTasks() and time.time() - t0 < timeout:
        APP.processEvents(); time.sleep(0.05)
    for _ in range(20):
        APP.processEvents(); time.sleep(0.02)


def new_dock(lang):
    os.environ["TWINFORGE_LANG"] = lang
    from twinforge_engine_qgis.dock import TwinForgeDock
    d = TwinForgeDock(FakeIface()); d.base.setText(BASE); d.resize(400, 980)
    return d


@pytest.fixture(scope="module")
def project_layers(tmp_path_factory):
    os.environ["QGIS_AUTH_DB_DIR_PATH"] = str(tmp_path_factory.mktemp("auth"))
    QgsApplication.authManager().setMasterPassword("box-local-test-only", True)
    QgsProject.instance().clear()
    QgsProject.instance().addMapLayer(buildings_layer())
    raw = QgsRasterLayer(str(SAMPLES / "not_a_cog.tif"), "QGIS smoke surface temp"); assert raw.isValid()
    QgsProject.instance().addMapLayer(raw)
    return True


@live
def test_live_read_only_and_expired_tokens(project_layers):
    d = new_dock("th")
    d.key.setText(TOK["read"]); d.on_connect()
    assert d.client is not None and not d.can_publish() and "อ่านอย่างเดียว" in d.status.text(), d.status.text()
    assert not d.publish_btn.isEnabled()
    d.key.setText(TOK["expired"]); d.on_connect()
    assert d.client is None and "หมดอายุ" in d.status.text(), d.status.text()
    d.key.setText("tft_" + "x" * 43); d.on_connect()
    assert d.client is None and "ไม่ถูกต้อง" in d.status.text()


@live
def test_live_connect_creates_personal_project_and_publishes(project_layers):
    d = new_dock("th")
    d.key.setText(TOK["full"]); d.on_connect()
    assert d.client is not None and d.can_publish(), d.status.text()
    assert d.project.count() == 1, d.status.text()
    STATE["pid"] = d.project.currentData()
    for i in range(d.layers.count()):
        d.layers.item(i).setCheckState(Qt.CheckState.Checked)
    d.layers.setCurrentRow(0); d._fill_fields()
    idx = d.extrude.findData("height_m"); assert idx > 0; d.extrude.setCurrentIndex(idx)
    d.on_publish(); wait_tasks()
    assert "เผยแพร่ 2 เลเยอร์แล้ว" in d.status.text(), (d.status.text(), repr(d.last_error))
    assert d.url.text().startswith(BASE + "/api/stream/v1/gis/s/")
    APP.processEvents(); d.grab().save(str(SHOTS / "dock_th_published.png"))
    c = NexusClient(TOK["full"], BASE)
    names = {l["name"]: l for l in c.layers(STATE["pid"])}
    b = names["qgis_smoke_buildings"]; r = names["qgis_smoke_surface_temp"]
    assert b["featureCount"] == 279 and b["style"]["classes"][0]["color"] == "#2BB59A" and b["style"]["extrusionField"] == "height_m"
    assert r["kind"] == "raster"
    STATE.update(b=b, r=r)
    # a second connect does not create a second project
    d2 = new_dock("en"); d2.key.setText(TOK["full"]); d2.on_connect()
    assert d2.project.count() == 1 and d2.project.currentData() == STATE["pid"]
    assert d2.remote.count() == 2
    APP.processEvents(); d2.grab().save(str(SHOTS / "dock_en_connected.png"))
    d3 = new_dock("ja"); d3.key.setText(TOK["full"]); d3.on_connect()
    APP.processEvents(); d3.grab().save(str(SHOTS / "dock_ja_connected.png"))


def _tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TwinForgeEngineQGIS-test"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


@live
def test_live_signed_links_stream(project_layers):
    c = NexusClient(TOK["full"], BASE)
    b = STATE["b"]; lon = (b["bbox"][0] + b["bbox"][2]) / 2; lat = (b["bbox"][1] + b["bbox"][3]) / 2
    u = c.stream_link(b["id"])["urls"]
    x, y = _tile(lon, lat, 15)
    st, ct, body = _get(u["mvt"].replace("{z}", "15").replace("{x}", str(x)).replace("{y}", str(y)))
    assert st == 200 and len(body) > 100, (st, ct, len(body))
    st, ct, body = _get(u["features"] + "?limit=10")
    assert st == 200 and len(json.loads(body)["features"]) == 10
    st, ct, body = _get(u["legend"]); assert st == 200
    ur = c.stream_link(STATE["r"]["id"])["urls"]; rb = STATE["r"]["bbox"]
    x, y = _tile((rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2, 13)
    st, ct, body = _get(ur["xyz"].replace("{z}", "13").replace("{x}", str(x)).replace("{y}", str(y)))
    assert st == 200 and body[:4] == b"\x89PNG", (st, ct)


@live
def test_live_add_twinforge_layers_back_into_qgis(project_layers):
    d = new_dock("en"); d.key.setText(TOK["full"]); d.on_connect()
    info = {d.remote.item(i).data(0x0100)["name"]: d.remote.item(i).data(0x0100) for i in range(d.remote.count())}
    v = d.remote_layer(info["qgis_smoke_buildings"]); assert v.isValid() and v.featureCount() == 279, v.featureCount()
    r = d.remote_layer(info["qgis_smoke_surface_temp"]); assert r.isValid()
    n0 = len(QgsProject.instance().mapLayers())
    for i in range(d.remote.count()):
        d.remote.setCurrentRow(i); d.on_add_remote()
    assert len(QgsProject.instance().mapLayers()) == n0 + 2
    d.refresh_layers()
    assert d.layers.count() == 2   # remote copies are not offered for publishing again


@live
def test_live_key_not_in_project_or_settings(project_layers, tmp_path):
    p = tmp_path / "proj.qgz"; QgsProject.instance().write(str(p))
    blob = b"".join(zipfile.ZipFile(p).read(n) for n in zipfile.ZipFile(p).namelist())
    for t in (TOK["full"], TOK["read"], TOK["expired"]):
        assert t.encode() not in blob
    from qgis.core import QgsSettings
    assert "tft_" not in str(QgsSettings().value("twinforge_engine/authcfg", ""))
    Path(os.environ.get("TF_LIVE_STATE", "tf_live_state.json")).write_text(json.dumps({"pid": STATE["pid"], "layers": [STATE["b"]["id"], STATE["r"]["id"]]}))


def test_dock_and_plugin_open_without_network():
    """Opening the panel from the toolbar (plugin._toggle) builds the whole dock; this is where QGIS 4 failed in 0.2.2."""
    from qgis.PyQt.QtWidgets import QLineEdit, QMainWindow, QToolBar
    from twinforge_engine_qgis.plugin import TwinForgePlugin

    class Iface(FakeIface):
        def __init__(self): super().__init__(); self.w = QMainWindow(); self.tb = QToolBar()
        def mainWindow(self): return self.w
        def addToolBarIcon(self, a): self.tb.addAction(a)
        def removeToolBarIcon(self, a): self.tb.removeAction(a)
        def addPluginToWebMenu(self, m, a): pass
        def removePluginWebMenu(self, m, a): pass
        def addDockWidget(self, area, d): self.w.addDockWidget(area, d)
        def removeDockWidget(self, d): self.w.removeDockWidget(d)

    lyr = buildings_layer(); QgsProject.instance().addMapLayer(lyr)
    try:
        p = TwinForgePlugin(Iface()); p.initGui(); p.action.setChecked(True)
        d = p.dock
        assert d is not None and not d.isHidden() and d.key.echoMode() == QLineEdit.EchoMode.Password
        d.refresh_layers()
        names = [d.layers.item(i).text() for i in range(d.layers.count())]
        assert "QGIS smoke buildings" in names and d.layers.item(names.index("QGIS smoke buildings")).checkState() == Qt.CheckState.Unchecked
        p.unload(); assert p.dock is None
    finally:
        QgsProject.instance().removeMapLayer(lyr.id())
