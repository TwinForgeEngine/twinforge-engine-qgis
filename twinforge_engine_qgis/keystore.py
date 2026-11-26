"""API key storage in the QGIS authentication database (encrypted by the QGIS master password).
The key is never written to the .qgz project or to QSettings in clear text; QSettings holds only the authcfg id."""
from __future__ import annotations

from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsSettings

SETTINGS_KEY = "twinforge_engine/authcfg"
HEADER = "X-TF-Key"


def save_key(api_key: str) -> str:
    am = QgsApplication.authManager()
    cfg = QgsAuthMethodConfig("APIHeader")
    cfg.setName("TwinForge Engine API key")
    cfg.setConfig(HEADER, api_key)
    old = QgsSettings().value(SETTINGS_KEY, "")
    if old:
        cfg.setId(old)
        am.updateAuthenticationConfig(cfg)
    else:
        am.storeAuthenticationConfig(cfg)
    QgsSettings().setValue(SETTINGS_KEY, cfg.id())
    return cfg.id()


def load_key() -> str | None:
    cid = QgsSettings().value(SETTINGS_KEY, "")
    if not cid:
        return None
    cfg = QgsAuthMethodConfig()
    QgsApplication.authManager().loadAuthenticationConfig(cid, cfg, True)
    return cfg.config(HEADER) or None


def forget_key() -> None:
    cid = QgsSettings().value(SETTINGS_KEY, "")
    if cid:
        QgsApplication.authManager().removeAuthenticationConfig(cid)
    QgsSettings().remove(SETTINGS_KEY)
