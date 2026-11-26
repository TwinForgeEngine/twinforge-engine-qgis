"""Plugin entry: adds the "TwinForge Engine" dock on the right of QGIS."""
from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dock import TwinForgeDock


class TwinForgePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):  # noqa: N802
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "TwinForge Engine", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.toggled.connect(self._toggle)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToWebMenu("TwinForge Engine", self.action)

    def _toggle(self, on: bool):
        if self.dock is None:
            self.dock = TwinForgeDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            self.dock.visibilityChanged.connect(lambda v: self.action.setChecked(v))
        self.dock.setVisible(on)

    def unload(self):
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock.shutdown()
            self.dock = None
        if self.action:
            self.iface.removePluginWebMenu("TwinForge Engine", self.action)
            self.iface.removeToolBarIcon(self.action)
