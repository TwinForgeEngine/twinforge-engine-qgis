#!/usr/bin/env bash
# Package the plugin: dist-plugin/twinforge_engine_qgis-<version>.zip (+ .sha256). Same zip for "Install from ZIP" and the QGIS plugin repository.
set -euo pipefail
cd "$(dirname "$0")"
VER=$(sed -n 's/^version=//p' twinforge_engine_qgis/metadata.txt)
mkdir -p dist-plugin
OUT=dist-plugin/twinforge_engine_qgis-$VER.zip
rm -f "$OUT" "$OUT.sha256"
python3 - "$OUT" <<'PY'
import os, sys, zipfile
out = sys.argv[1]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk("twinforge_engine_qgis"):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(files):
            if f.endswith((".pyc", ".pyo")):
                continue
            p = os.path.join(root, f)
            zi = zipfile.ZipInfo(p, date_time=(2026, 11, 26, 0, 0, 0))
            zi.external_attr = 0o644 << 16; zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(p, "rb").read())
PY
(cd dist-plugin && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
echo "$OUT"; cat "$OUT.sha256"
