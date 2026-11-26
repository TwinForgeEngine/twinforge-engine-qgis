"""Raster -> Cloud Optimized GeoTIFF on the user's machine before upload (spec §11.2).
Prefers rio-cogeo (as specified); falls back to GDAL's COG driver, which ships with QGIS."""
from __future__ import annotations

import os
import tempfile


def to_cog(src_path: str, dst_path: str | None = None) -> str:
    dst = dst_path or os.path.join(tempfile.mkdtemp(prefix="tf_cog_"), os.path.splitext(os.path.basename(src_path))[0] + "_cog.tif")
    try:
        from rio_cogeo.cogeo import cog_translate
        from rio_cogeo.profiles import cog_profiles
        cog_translate(src_path, dst, cog_profiles.get("deflate"), quiet=True, overview_resampling="average")
        return dst
    except ImportError:
        pass
    from osgeo import gdal
    gdal.UseExceptions()
    gdal.Translate(dst, src_path, format="COG", creationOptions=["COMPRESS=DEFLATE", "BLOCKSIZE=512", "OVERVIEWS=AUTO", "RESAMPLING=AVERAGE"])
    return dst


def is_cog(path: str) -> bool:
    from osgeo import gdal
    gdal.UseExceptions()
    ds = gdal.Open(path)
    return (ds.GetMetadata("IMAGE_STRUCTURE") or {}).get("LAYOUT") == "COG"
