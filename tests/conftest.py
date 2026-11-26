"""One QgsApplication for the whole test session (QGIS 3.x and 4.x)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication  # noqa: E402

APP = QgsApplication.instance()
if APP is None:
    APP = QgsApplication([], True)
    APP.initQgis()
