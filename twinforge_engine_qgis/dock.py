"""Dock widget "TwinForge Engine": token -> project -> publish QGIS layers, or add TwinForge Engine layers to QGIS."""
from __future__ import annotations

import os
import tempfile
import webbrowser
from urllib.parse import quote

from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsCoordinateTransformContext,
                       QgsMapLayer, QgsMessageLog, QgsProject, QgsRasterLayer, QgsTask, QgsVectorFileWriter, QgsVectorLayer)
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (QApplication, QCheckBox, QComboBox, QDockWidget, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                 QListWidget, QListWidgetItem, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from . import keystore
from .core.client import DEFAULT_BASE, NexusClient, NexusError, safe_layer_name
from .core.cog import is_cog, to_cog
from .core.style_export import export_style, minimal_style, server_fields
from .i18n import tr

PRIMARY = ("QPushButton{background:#2BB59A;color:#04201A;border:0;border-radius:6px;padding:7px 12px;font-weight:600}"
           "QPushButton:disabled{background:#7FBFB1}")
SECONDARY = "QPushButton{background:transparent;border:1px solid #6E8F88;border-radius:6px;padding:6px 10px}"
SOON = "color:#9A7B1E"
HEAD = "font-weight:600;margin-top:6px"
LOG = "TwinForge Engine"
FEATURE_LIMIT = 5000   # server cap of the signed features endpoint


class TwinForgeDock(QDockWidget):
    def __init__(self, iface):
        super().__init__("TwinForge Engine")
        self.iface = iface
        self.client: NexusClient | None = None
        self.scopes: list[str] = []
        self.last_urls: dict | None = None
        self.last_layer_id: str | None = None
        self.last_error = None
        self._dirty: set[str] = set()
        self.setObjectName("TwinForgeEngineDock")
        w = QWidget(); v = QVBoxLayout(w)

        # 1) connect with a tft_ access token
        self.base = QLineEdit(DEFAULT_BASE)
        self.key = QLineEdit(); self.key.setEchoMode(QLineEdit.EchoMode.Password); self.key.setPlaceholderText(tr("key_ph"))
        self.connect_btn = QPushButton(tr("connect")); self.connect_btn.setStyleSheet(PRIMARY)
        self.forget_btn = QPushButton(tr("forget")); self.forget_btn.setStyleSheet(SECONDARY)
        self.status = QLabel(tr("not_connected")); self.status.setWordWrap(True)
        f = QFormLayout(); f.addRow(tr("server"), self.base); f.addRow(tr("key"), self.key); v.addLayout(f)
        h = QHBoxLayout(); h.addWidget(self.connect_btn); h.addWidget(self.forget_btn); v.addLayout(h)
        v.addWidget(self.status)

        # 2) project + optional Engine scene
        self.project = QComboBox(); self.scene = QLineEdit(); self.scene.setPlaceholderText(tr("scene_ph"))
        f2 = QFormLayout(); f2.addRow(tr("project"), self.project); f2.addRow(tr("scene"), self.scene); v.addLayout(f2)

        # 3) publish QGIS layers
        lbl = QLabel(tr("pick")); lbl.setStyleSheet(HEAD); v.addWidget(lbl)
        self.layers = QListWidget(); self.layers.setMinimumHeight(110); v.addWidget(self.layers)
        self.extrude = QComboBox(); self.extrude.addItem(tr("no_extrude"), "")
        f3 = QFormLayout(); f3.addRow(tr("extrude"), self.extrude); v.addLayout(f3)
        self.publish_btn = QPushButton(tr("publish")); self.publish_btn.setStyleSheet(PRIMARY)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        v.addWidget(self.publish_btn); v.addWidget(self.progress)

        # 4) result
        self.url = QLineEdit(); self.url.setReadOnly(True); self.url.setPlaceholderText(tr("url_ph"))
        self.copy_btn = QPushButton(tr("copy")); self.copy_btn.setStyleSheet(SECONDARY)
        self.open_btn = QPushButton(tr("open_engine")); self.open_btn.setStyleSheet(SECONDARY)
        self.map_btn = QPushButton(tr("open_map")); self.map_btn.setStyleSheet(SECONDARY)
        v.addWidget(self.url); v.addWidget(self.copy_btn)
        h2 = QHBoxLayout(); h2.addWidget(self.open_btn); h2.addWidget(self.map_btn); v.addLayout(h2)
        self.autosync = QCheckBox(tr("autosync_short")); self.autosync.setToolTip(tr("autosync")); v.addWidget(self.autosync)

        # 5) layers already in TwinForge Engine -> QGIS (gis:read)
        lbl2 = QLabel(tr("remote")); lbl2.setStyleSheet(HEAD); v.addWidget(lbl2)
        self.remote = QListWidget(); self.remote.setMinimumHeight(90); v.addWidget(self.remote)
        h3 = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("refresh")); self.refresh_btn.setStyleSheet(SECONDARY)
        self.add_btn = QPushButton(tr("add_qgis")); self.add_btn.setStyleSheet(SECONDARY)
        h3.addWidget(self.refresh_btn); h3.addWidget(self.add_btn); v.addLayout(h3)

        note = QLabel(tr("note")); note.setWordWrap(True); note.setStyleSheet(SOON); v.addWidget(note)
        v.addStretch(1)
        for le in (self.base, self.key, self.scene, self.url):
            le.setMinimumWidth(80)
        for cb in (self.project, self.extrude):
            cb.setMinimumContentsLength(8); cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); sc.setWidget(w)
        self.setWidget(sc)

        self.connect_btn.clicked.connect(self.on_connect)
        self.forget_btn.clicked.connect(self.on_forget)
        self.publish_btn.clicked.connect(lambda: self.on_publish())
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.url.text()))
        self.open_btn.clicked.connect(self.on_open)
        self.map_btn.clicked.connect(self.on_open_map)
        self.refresh_btn.clicked.connect(self.refresh_remote)
        self.add_btn.clicked.connect(self.on_add_remote)
        self.project.currentIndexChanged.connect(lambda *_: self.refresh_remote())
        self.layers.itemSelectionChanged.connect(self._fill_fields)
        QgsProject.instance().layersAdded.connect(lambda *_: self.refresh_layers())
        QgsProject.instance().layersRemoved.connect(lambda *_: self.refresh_layers())
        self.timer = QTimer(self); self.timer.setInterval(60_000); self.timer.timeout.connect(self._sync_tick); self.timer.start()
        self.refresh_layers()
        saved = keystore.load_key()
        if saved:
            self.key.setText(saved)

    # -------------------------------------------------------------- helpers
    def say(self, text: str, level=Qgis.MessageLevel.Info):
        self.status.setText(text)
        self.iface.messageBar().pushMessage("TwinForge Engine", text, level=level, duration=6)

    def can_publish(self) -> bool:
        return "gis:publish" in self.scopes

    def refresh_layers(self):
        self.layers.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.type() not in (Qgis.LayerType.Vector, Qgis.LayerType.Raster):
                continue
            if lyr.customProperty("twinforge/remote"):
                continue   # layers added from TwinForge Engine are not published back
            it = QListWidgetItem(lyr.name()); it.setData(Qt.ItemDataRole.UserRole, lyr.id())
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable); it.setCheckState(Qt.CheckState.Unchecked)
            self.layers.addItem(it)
            if isinstance(lyr, QgsVectorLayer):
                try:
                    lyr.afterCommitChanges.connect(lambda lid=lyr.id(): self._dirty.add(lid))
                except TypeError:
                    pass

    def _fill_fields(self):
        self.extrude.clear(); self.extrude.addItem(tr("no_extrude"), "")
        items = self.layers.selectedItems()
        if not items:
            return
        lyr = QgsProject.instance().mapLayer(items[0].data(Qt.ItemDataRole.UserRole))
        if isinstance(lyr, QgsVectorLayer):
            for fld in lyr.fields():
                if fld.isNumeric():
                    self.extrude.addItem(fld.name(), fld.name())

    def _base(self) -> str:
        return (self.base.text().strip() or DEFAULT_BASE).rstrip("/")

    # -------------------------------------------------------------- connect
    def on_connect(self):
        try:
            self.client = NexusClient(self.key.text().strip(), self._base())
            me = self.client.me()                       # needs gis:read
            self.scopes = list(me.get("scopes", []))
            keystore.save_key(self.key.text().strip())
            self.project.blockSignals(True); self.project.clear()
            projects = self.client.projects()
            writable = [p for p in projects if p.get("role") in ("owner", "editor")]
            made = None
            if self.can_publish() and not writable:
                made = self.client.personal_project()   # first use: the account gets its own project
                projects = self.client.projects()
            show = [p for p in projects if p.get("role") in ("owner", "editor")] if self.can_publish() else projects
            for p in show:
                self.project.addItem(p["name"], p["id"])
            self.project.blockSignals(False)
            self.publish_btn.setEnabled(self.can_publish())
            msg = tr("connected", name=me.get("name", ""))
            if made:
                msg += "\n" + tr("personal", name=made.get("name", ""))
            if not self.can_publish():
                msg += "\n" + tr("read_only")
            self.say(msg)
            self.refresh_remote()
        except NexusError as e:
            self.client = None; self.scopes = []
            self.project.blockSignals(False)
            self.say(e.text, Qgis.MessageLevel.Warning)

    def on_forget(self):
        keystore.forget_key(); self.key.clear(); self.client = None; self.scopes = []
        self.project.clear(); self.remote.clear()
        self.say(tr("forgot"))

    # -------------------------------------------------------------- publish
    def _checked(self):
        out = []
        for i in range(self.layers.count()):
            it = self.layers.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                lyr = QgsProject.instance().mapLayer(it.data(Qt.ItemDataRole.UserRole))
                if lyr:
                    out.append(lyr)
        return out

    def _export_vector(self, lyr: QgsVectorLayer) -> bytes:
        out = os.path.join(tempfile.mkdtemp(prefix="tf_pub_"), "layer.geojson")
        opt = QgsVectorFileWriter.SaveVectorOptions()
        opt.driverName = "GeoJSON"
        opt.fileEncoding = "UTF-8"
        opt.layerOptions = ["RFC7946=YES", "COORDINATE_PRECISION=7"]
        opt.ct = QgsCoordinateTransform(lyr.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance())
        QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out, QgsCoordinateTransformContext(), opt)
        with open(out, "rb") as fh:
            return fh.read()

    def _publish_one(self, lyr) -> dict:
        assert self.client is not None
        pid = self.project.currentData()
        name = safe_layer_name(lyr.name())
        if isinstance(lyr, QgsVectorLayer):
            data = self._export_vector(lyr)
            avail = server_fields(data)
            label, label_expr = None, False
            try:
                if lyr.labelsEnabled() and lyr.labeling() is not None and hasattr(lyr.labeling(), "settings"):
                    st = lyr.labeling().settings(); label, label_expr = st.fieldName, bool(st.isExpression)
            except Exception:
                label = None
            style = export_style(lyr.renderer(), label_field=label, label_is_expression=label_expr,
                                 extrusion_field=self.extrude.currentData() or None,
                                 popup_fields=[(f.name(), lyr.attributeDisplayName(i)) for i, f in enumerate(lyr.fields())][:12],
                                 title_field=label, available_fields=avail)
            for x in style.get("reduced", []):
                QgsMessageLog.logMessage(f"{lyr.name()}: style: {x}", LOG, Qgis.MessageLevel.Info)
            try:
                return self.client.publish_vector(pid, name, lyr.name(), data, style)
            except NexusError as e:
                if e.code != "style_invalid":
                    raise
                QgsMessageLog.logMessage(f"{lyr.name()}: server refused the style ({e.message}); publishing with one colour.",
                                         LOG, Qgis.MessageLevel.Warning)
                return self.client.publish_vector(pid, name, lyr.name(), data,
                                                  minimal_style(style, f"Server refused the style: {e.message}"))
        src = lyr.source()
        cog = src if is_cog(src) else to_cog(src)
        render = {}
        if lyr.bandCount() == 1:
            stats = lyr.dataProvider().bandStatistics(1)
            render = {"rescale": f"{stats.minimumValue:g},{stats.maximumValue:g}", "colormap_name": "viridis"}
        return self.client.publish_raster(pid, name, lyr.name(), cog, render)

    def on_publish(self, layers=None):
        if not self.client or self.project.currentData() is None or not self.can_publish():
            return self.say(tr("need_connect") if self.can_publish() or not self.client else tr("read_only"), Qgis.MessageLevel.Warning)
        todo = layers or self._checked()
        if not todo:
            return self.say(tr("need_layer"), Qgis.MessageLevel.Warning)
        self.publish_btn.setEnabled(False); self.progress.setVisible(True); self.progress.setRange(0, 100)

        def run(task):
            res = []
            for i, lyr in enumerate(todo):
                res.append(self._publish_one(lyr))
                task.setProgress(100 * (i + 1) / len(todo))
            return res

        def done(exc, res=None):
            self.publish_btn.setEnabled(True); self.progress.setVisible(False)
            self.last_error = exc
            if exc:
                QgsMessageLog.logMessage(f"publish failed: {type(exc).__name__}: {getattr(exc, 'code', '')} {getattr(exc, 'message', '') or exc}", LOG, Qgis.MessageLevel.Warning)
                return self.say(exc.text if isinstance(exc, NexusError) else tr("fail"), Qgis.MessageLevel.Warning)
            last = res[-1]
            self.last_layer_id = last["layer"]["id"]
            self.last_urls = last["stream"]["urls"]
            self.url.setText(self.last_urls.get("mvt") or self.last_urls.get("xyz") or "")
            reduced = [x for r in res for x in (r.get("styleReduced") or [])]
            if self.scene.text().strip():
                for r in res:
                    self.client.bind(r["layer"]["id"], self.scene.text().strip())
            msg = tr("published", n=len(res))
            if reduced:
                msg += "\n" + tr("reduced", n=len(reduced))
            self.say(msg)
            self.refresh_remote()

        task = QgsTask.fromFunction(tr("publish_task"), run, on_finished=done)
        QgsApplication.taskManager().addTask(task)
        self._task = task

    def on_open(self):
        if not (self.client and self.last_layer_id and self.scene.text().strip()):
            return self.say(tr("need_scene"), Qgis.MessageLevel.Warning)
        r = self.client.bind(self.last_layer_id, self.scene.text().strip())
        webbrowser.open(r["openInEngine"])

    def on_open_map(self):
        webbrowser.open(self._base() + "/map-app/")

    # -------------------------------------------------------------- TwinForge Engine -> QGIS
    def refresh_remote(self):
        self.remote.clear()
        pid = self.project.currentData()
        if not (self.client and pid):
            return
        try:
            ls = self.client.layers(pid)
        except NexusError as e:
            return self.say(e.text, Qgis.MessageLevel.Warning)
        if not ls:
            it = QListWidgetItem(tr("no_remote")); it.setFlags(Qt.ItemFlag.NoItemFlags); self.remote.addItem(it); return
        for L in ls:
            kind = "Raster" if L.get("kind") == "raster" else (L.get("geometryType") or "Vector")
            it = QListWidgetItem(f"{L.get('title') or L['name']}  ({kind})")
            it.setData(Qt.ItemDataRole.UserRole, L)
            self.remote.addItem(it)

    def remote_layer(self, info: dict):
        """Build a QGIS layer for one TwinForge Engine layer from fresh signed links (valid about 1 hour)."""
        assert self.client is not None
        urls = self.client.stream_link(info["id"])["urls"]
        name = info.get("title") or info["name"]
        if info.get("kind") == "raster":
            uri = f"type=xyz&url={quote(urls['xyz'], safe=':/{}')}&zmin=0&zmax=20"
            lyr = QgsRasterLayer(uri, name, "wms")
        elif (info.get("featureCount") or 0) <= FEATURE_LIMIT and urls.get("features"):
            lyr = QgsVectorLayer(f"{urls['features']}?limit={FEATURE_LIMIT}", name, "ogr")
        else:
            from qgis.core import QgsVectorTileLayer
            lyr = QgsVectorTileLayer(f"type=xyz&url={quote(urls['mvt'], safe=':/{}')}&zmin=0&zmax=14", name)
        lyr.setCustomProperty("twinforge/remote", info["id"])
        return lyr

    def on_add_remote(self):
        items = self.remote.selectedItems()
        if not (self.client and items and items[0].data(Qt.ItemDataRole.UserRole)):
            return self.say(tr("need_connect"), Qgis.MessageLevel.Warning)
        info = items[0].data(Qt.ItemDataRole.UserRole)
        try:
            lyr = self.remote_layer(info)
        except NexusError as e:
            return self.say(e.text, Qgis.MessageLevel.Warning)
        if not lyr.isValid():
            return self.say(tr("add_failed"), Qgis.MessageLevel.Warning)
        QgsProject.instance().addMapLayer(lyr)
        self.say(tr("added", name=lyr.name()))

    # -------------------------------------------------------------- auto sync
    def _sync_tick(self):
        if not (self.autosync.isChecked() and self.client and self._dirty):
            return
        layers = [QgsProject.instance().mapLayer(i) for i in list(self._dirty)]
        self._dirty.clear()
        self.on_publish([l for l in layers if l])

    def shutdown(self):
        self.timer.stop()
