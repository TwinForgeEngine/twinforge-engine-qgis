# TwinForge Engine for QGIS — GPL-2.0-or-later
def classFactory(iface):  # noqa: N802 (QGIS API)
    from .plugin import TwinForgePlugin
    return TwinForgePlugin(iface)
