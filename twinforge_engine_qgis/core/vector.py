"""Vector source -> GeoJSON (EPSG:4326) bytes for upload. The server stores it in the project SRID (e.g. 32647)."""
from __future__ import annotations

import os
import tempfile


def file_to_geojson(src: str, layer: str | None = None) -> bytes:
    from osgeo import gdal
    gdal.UseExceptions()
    out = os.path.join(tempfile.mkdtemp(prefix="tf_vec_"), "layer.geojson")
    opts = gdal.VectorTranslateOptions(format="GeoJSON", dstSRS="EPSG:4326", layers=[layer] if layer else None,
                                       layerCreationOptions=["RFC7946=YES", "COORDINATE_PRECISION=7"])
    gdal.VectorTranslate(out, src, options=opts)
    with open(out, "rb") as fh:
        return fh.read()
