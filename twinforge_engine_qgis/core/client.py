"""TwinForge Engine GIS client. Auth = a tft_ access token from the TwinForge Engine account (no separate login, no DB password)."""
from __future__ import annotations

import json
import mimetypes
import re
import urllib.error
import urllib.request
import uuid
from typing import Any

KEY_RE = re.compile(r"^tft_[A-Za-z0-9_-]{40,50}$")
DEFAULT_BASE = "https://twinforgeengine.online"

VERSION = "0.2.3"


def _qgis_available() -> bool:
    try:
        from qgis.core import QgsApplication
        return QgsApplication.instance() is not None
    except Exception:
        return False


class NexusError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    @property
    def text(self) -> str:
        """Message in the QGIS interface language (Thai, English or Japanese)."""
        try:
            from ..i18n import err_text
            return err_text(self.code)
        except Exception:
            return self.message or self.code

    thai = text  # 0.1 name


class NexusClient:
    """transport="qgis" (default inside QGIS) goes through QgsNetworkAccessManager, so the QGIS proxy and SSL settings apply.
    transport="urllib" is used outside QGIS (scripts, tests)."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE, timeout: int = 120, transport: str | None = None):
        if not KEY_RE.match(api_key or ""):
            raise NexusError(401, "token_invalid", "bad key format")
        self._key = api_key            # kept in memory only; persisted by QgsAuthManager, never in the .qgz
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport or ("qgis" if _qgis_available() else "urllib")

    def __repr__(self) -> str:        # never leak the key in logs
        return f"NexusClient(base={self.base!r}, key=tft_***)"

    # ---------------------------------------------------------------- transport
    def _headers(self, ctype: str | None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._key}", "User-Agent": f"TwinForgeEngineQGIS/{VERSION}", "Accept": "application/json"}
        if ctype:
            h["Content-Type"] = ctype
        return h

    @staticmethod
    def _detail(raw: bytes) -> str:
        try:
            d = json.loads(raw).get("detail", "")
            return d if isinstance(d, str) else ""
        except Exception:
            return ""

    def _req(self, method: str, path: str, body: bytes | None = None, ctype: str | None = None) -> Any:
        if self.transport == "qgis":
            return self._req_qgis(method, self.base + path, body, self._headers(ctype))
        return self._req_urllib(method, self.base + path, body, self._headers(ctype))

    def _req_qgis(self, method: str, url: str, body: bytes | None, headers: dict[str, str]) -> Any:
        from qgis.core import QgsBlockingNetworkRequest
        from qgis.PyQt.QtCore import QByteArray, QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest

        req = QNetworkRequest(QUrl(url))
        for k, v in headers.items():
            req.setRawHeader(k.encode(), v.encode())
        try:
            req.setTransferTimeout(int(self.timeout * 1000))
        except AttributeError:
            pass
        br = QgsBlockingNetworkRequest()
        if method == "GET":
            err = br.get(req, True)
        elif method == "POST":
            err = br.post(req, QByteArray(body or b""), True)
        elif method == "PUT":
            err = br.put(req, QByteArray(body or b""))
        elif method == "DELETE":
            err = br.deleteResource(req)
        else:
            raise ValueError(method)
        rep = br.reply()
        status = rep.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        raw = bytes(rep.content())
        if status is not None and 200 <= int(status) < 300 and err == QgsBlockingNetworkRequest.ErrorCode.NoError:
            return json.loads(raw) if raw else None
        if status:
            code = bytes(rep.rawHeader(b"X-TF-Error")).decode() or "error"
            raise NexusError(int(status), code, self._detail(raw))
        raise NexusError(0, "network", "network error")

    def _req_urllib(self, method: str, url: str, body: bytes | None, headers: dict[str, str]) -> Any:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 (https base URL from the user)
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise NexusError(e.code, e.headers.get("X-TF-Error") or "error", self._detail(e.read())) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            raise NexusError(0, "network", "network error") from None

    @staticmethod
    def _multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes]]) -> tuple[bytes, str]:
        b = uuid.uuid4().hex
        out = bytearray()
        for k, v in fields.items():
            out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        for k, (fn, data) in files.items():
            ct = mimetypes.guess_type(fn)[0] or "application/octet-stream"
            out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode()
            out += data + b"\r\n"
        out += f"--{b}--\r\n".encode()
        return bytes(out), f"multipart/form-data; boundary={b}"

    # ---------------------------------------------------------------- API
    def me(self) -> dict[str, Any]:
        return self._req("GET", "/api/v1/gis/me")

    def projects(self) -> list[dict[str, Any]]:
        return self._req("GET", "/api/v1/gis/projects")["projects"]

    def personal_project(self) -> dict[str, Any]:
        """Create (first time) or return the caller's own project. Needs gis:publish."""
        return self._req("POST", "/api/v1/gis/projects/personal", b"{}", "application/json")

    def stream_link(self, layer_id: str) -> dict[str, Any]:
        """Fresh signed links (about 1 hour) for one layer: mvt / features / xyz / style / legend."""
        return self._req("POST", "/api/v1/gis/stream-tokens", json.dumps({"layerId": layer_id}).encode(), "application/json")

    def layers(self, project_id: str) -> list[dict[str, Any]]:
        return self._req("GET", f"/api/v1/gis/projects/{project_id}/layers")["layers"]

    def publish_vector(self, project_id: str, name: str, title: str, geojson: bytes, style: dict[str, Any]) -> dict[str, Any]:
        body, ct = self._multipart({"name": name, "title": title, "style": json.dumps(style, ensure_ascii=False)},
                                   {"file": (f"{name}.geojson", geojson)})
        return self._req("POST", f"/api/v1/gis/projects/{project_id}/layers/vector", body, ct)

    def publish_raster(self, project_id: str, name: str, title: str, cog_path: str, render: dict[str, Any]) -> dict[str, Any]:
        with open(cog_path, "rb") as fh:
            data = fh.read()
        body, ct = self._multipart({"name": name, "title": title, "render": json.dumps(render)}, {"file": (f"{name}.tif", data)})
        return self._req("POST", f"/api/v1/gis/projects/{project_id}/layers/raster", body, ct)

    def bind(self, layer_id: str, scene_id: str) -> dict[str, Any]:
        return self._req("POST", f"/api/v1/gis/layers/{layer_id}/bind", json.dumps({"sceneId": scene_id}).encode(), "application/json")

    def layer(self, layer_id: str) -> dict[str, Any]:
        return self._req("GET", f"/api/v1/gis/layers/{layer_id}")


def safe_layer_name(title: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", (title or "").lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "layer_" + s
    return s[:40]
