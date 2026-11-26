"""TwinForge Style JSON (v1) — validation, legend, and MapLibre Style JSON conversion.

Shared by the Nexus GIS router (server) and the "TwinForge Engine for QGIS" plugin (client).
Scope promised in phase 1: classes, colours, legend, popup. Anything else is reduced with a note.

Style JSON v1:
{
  "version": 1,
  "renderer": "single" | "categorized" | "graduated",
  "field": "typ_code",                 # categorized / graduated
  "labelField": "name",                # optional simple labels
  "extrusionField": "height_m",        # optional, metres above ground
  "opacity": 0.85,
  "single":  {"color": "#2BB59A", "outline": "#0D4F3C"},
  "classes": [{"value": "residential", "label": "ที่อยู่อาศัย", "color": "#2BB59A", "outline": "#0D4F3C"}],
  "ranges":  [{"min": 0, "max": 10, "label": "0–10", "color": "#..."}],
  "fallback": {"color": "#8AA8A1", "outline": "#1A3D38"},
  "popup": {"title": "name", "fields": [{"name": "height_m", "label": "Height (m)"}]},
  "reduced": ["..."]                   # what could not be carried over from QGIS
}
"""
from __future__ import annotations

import re
from typing import Any

HEX = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
FIELD = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
DEFAULT_FALLBACK = {"color": "#8AA8A1", "outline": "#1A3D38"}
MAX_CLASSES = 64


class StyleError(ValueError):
    pass


def _color(v: Any, where: str) -> str:
    if not isinstance(v, str) or not HEX.match(v):
        raise StyleError(f"{where}: colour must be #RRGGBB")
    return v[:7].upper()


def _field(v: Any, where: str, required: bool = True) -> str | None:
    if v is None and not required:
        return None
    if not isinstance(v, str) or not FIELD.match(v):
        raise StyleError(f"{where}: bad field name")
    return v


def normalize(style: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
    """Validate + normalise. Unknown keys are dropped (never stored), with a 'reduced' note."""
    if not isinstance(style, dict):
        raise StyleError("style must be an object")
    if style.get("version", 1) != 1:
        raise StyleError("unsupported style version")
    r = style.get("renderer", "single")
    if r not in ("single", "categorized", "graduated"):
        raise StyleError("renderer must be single, categorized or graduated")
    reduced = [str(x)[:200] for x in style.get("reduced", []) if isinstance(x, (str, int, float))][:20]
    out: dict[str, Any] = {"version": 1, "renderer": r}
    fb = style.get("fallback") or DEFAULT_FALLBACK
    out["fallback"] = {"color": _color(fb.get("color", DEFAULT_FALLBACK["color"]), "fallback"),
                       "outline": _color(fb.get("outline", DEFAULT_FALLBACK["outline"]), "fallback")}
    op = style.get("opacity", 0.85)
    out["opacity"] = max(0.0, min(1.0, float(op))) if isinstance(op, (int, float)) else 0.85
    for k in ("labelField", "extrusionField"):
        if style.get(k) is not None:
            out[k] = _field(style[k], k)
    if r == "single":
        s = style.get("single") or out["fallback"]
        out["single"] = {"color": _color(s.get("color"), "single"), "outline": _color(s.get("outline", s.get("color")), "single")}
    elif r == "categorized":
        out["field"] = _field(style.get("field"), "field")
        cl = style.get("classes") or []
        if not cl:
            raise StyleError("categorized style needs classes")
        if len(cl) > MAX_CLASSES:
            reduced.append(f"Only the first {MAX_CLASSES} classes are kept.")
        out["classes"] = [{"value": c.get("value"), "label": str(c.get("label", c.get("value")))[:80],
                           "color": _color(c.get("color"), f"classes[{i}]"),
                           "outline": _color(c.get("outline", c.get("color")), f"classes[{i}]")}
                          for i, c in enumerate(cl[:MAX_CLASSES])]
    else:
        out["field"] = _field(style.get("field"), "field")
        rg = style.get("ranges") or []
        if not rg:
            raise StyleError("graduated style needs ranges")
        rr = []
        for i, c in enumerate(rg[:MAX_CLASSES]):
            lo, hi = c.get("min"), c.get("max")
            if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)) or hi < lo:
                raise StyleError(f"ranges[{i}]: min/max must be numbers, min <= max")
            rr.append({"min": float(lo), "max": float(hi), "label": str(c.get("label", f"{lo}–{hi}"))[:80],
                       "color": _color(c.get("color"), f"ranges[{i}]"),
                       "outline": _color(c.get("outline", c.get("color")), f"ranges[{i}]")})
        out["ranges"] = sorted(rr, key=lambda x: x["min"])
    pp = style.get("popup") or {}
    if pp:
        out["popup"] = {"title": _field(pp.get("title"), "popup.title", required=False),
                        "fields": [{"name": _field(f.get("name"), "popup.fields"), "label": str(f.get("label", f.get("name")))[:80]}
                                   for f in (pp.get("fields") or [])[:30]]}
        if out["popup"]["title"] is None:
            out["popup"].pop("title")
    if fields is not None:
        used = [out.get("field"), out.get("labelField"), out.get("extrusionField")] + [f["name"] for f in out.get("popup", {}).get("fields", [])]
        missing = sorted({u for u in used if u and u not in fields})
        if missing:
            raise StyleError("style uses fields the layer does not have: " + ", ".join(missing))
    out["reduced"] = reduced
    return out


def legend(style: dict[str, Any], title: str = "") -> dict[str, Any]:
    r = style["renderer"]
    if r == "single":
        items = [{"label": title or "—", "color": style["single"]["color"], "outline": style["single"]["outline"]}]
    elif r == "categorized":
        items = [{"label": c["label"], "value": c["value"], "color": c["color"], "outline": c["outline"]} for c in style["classes"]]
    else:
        items = [{"label": c["label"], "min": c["min"], "max": c["max"], "color": c["color"], "outline": c["outline"]} for c in style["ranges"]]
    return {"title": title, "renderer": r, "field": style.get("field"), "items": items,
            "fallback": style["fallback"], "reduced": style.get("reduced", [])}


def _fill_expr(style: dict[str, Any], key: str = "color") -> Any:
    r = style["renderer"]
    fb = style["fallback"][key]
    if r == "single":
        return style["single"][key]
    if r == "categorized":
        expr: list[Any] = ["match", ["to-string", ["get", style["field"]]]]
        for c in style["classes"]:
            expr += [str(c["value"]), c[key]]
        return expr + [fb]
    # graduated -> step on min values
    rg = style["ranges"]
    expr = ["step", ["to-number", ["get", style["field"]], -1e308], fb]
    for c in rg:
        expr += [c["min"], c[key]]
    return expr


def to_maplibre(style: dict[str, Any], tiles_url: str, source_layer: str, geometry_type: str | None,
                name: str = "layer") -> dict[str, Any]:
    """MapLibre Style JSON (spec v8) with one vector source. tiles_url is a signed {z}/{x}/{y} template."""
    g = (geometry_type or "").upper()
    layers: list[dict[str, Any]] = []
    base = {"source": "tf", "source-layer": source_layer}
    if "POLYGON" in g or not g or g == "GEOMETRY":
        if style.get("extrusionField"):
            layers.append({**base, "id": f"{name}-extrusion", "type": "fill-extrusion",
                           "paint": {"fill-extrusion-color": _fill_expr(style), "fill-extrusion-opacity": style["opacity"],
                                     "fill-extrusion-height": ["to-number", ["get", style["extrusionField"]], 0]}})
        else:
            layers.append({**base, "id": f"{name}-fill", "type": "fill",
                           "paint": {"fill-color": _fill_expr(style), "fill-opacity": style["opacity"]}})
            layers.append({**base, "id": f"{name}-outline", "type": "line",
                           "paint": {"line-color": _fill_expr(style, "outline"), "line-width": 1}})
    if "LINE" in g:
        layers.append({**base, "id": f"{name}-line", "type": "line",
                       "paint": {"line-color": _fill_expr(style), "line-width": 2, "line-opacity": style["opacity"]}})
    if "POINT" in g:
        layers.append({**base, "id": f"{name}-circle", "type": "circle",
                       "paint": {"circle-color": _fill_expr(style), "circle-radius": 5,
                                 "circle-stroke-color": _fill_expr(style, "outline"), "circle-stroke-width": 1}})
    if style.get("labelField"):
        layers.append({**base, "id": f"{name}-label", "type": "symbol", "minzoom": 14,
                       "layout": {"text-field": ["get", style["labelField"]], "text-size": 12},
                       "paint": {"text-color": "#E6F2EF", "text-halo-color": "#0B1412", "text-halo-width": 1}})
    return {"version": 8, "name": name,
            "sources": {"tf": {"type": "vector", "tiles": [tiles_url], "minzoom": 0, "maxzoom": 22}},
            "layers": layers}
