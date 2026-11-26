"""QGIS renderer -> TwinForge Style JSON v1 (classes, colours, legend, popup).

Never raises: every renderer, category, range, rule and symbol is read on its own, and whatever cannot be
carried over falls back for that part only, with a note in `reduced` (shown in the QGIS log panel).
Field names are written the way the server stores them (lower case, a-z 0-9 _), and only fields that really
exist in the uploaded GeoJSON are referenced, so the server never refuses the style.

Supported: single symbol, categorized, graduated, rule-based (simple `"field" = value` rules become
categories), 2.5D, heatmap, point displacement / cluster, inverted polygon and merged features (their inner
renderer), null symbol. Fill, line and marker symbols, including marker line, arrow, geometry generator,
SVG, gradient and shapeburst layers (base colours)."""
from __future__ import annotations

import json
import math
import re
from typing import Any, Callable, Iterable

FIELD = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
FALLBACK = {"color": "#8AA8A1", "outline": "#1A3D38"}
SKIP_FIELDS = ("gid", "geom", "updated_at", "updated_by")
MAX_CLASSES = 64


# ------------------------------------------------------------------ fields as the server sees them
def server_name(name: Any) -> str:
    return re.sub(r"[^a-z0-9_]", "_", str(name).lower())[:40]


def server_fields(geojson: bytes | str | dict) -> set[str]:
    """Same rule as the TwinForge Engine server: names normalised, only fields with at least one
    text / number / boolean value in the first 2000 features."""
    try:
        d = json.loads(geojson) if isinstance(geojson, (bytes, str)) else geojson
        feats = d.get("features") or []
    except Exception:
        return set()
    out: set[str] = set()
    for f in feats[:2000]:
        for k, v in ((f or {}).get("properties") or {}).items():
            k2 = server_name(k)
            if re.match(r"^[a-z_]", k2) and k2 not in SKIP_FIELDS and isinstance(v, (str, int, float, bool)):
                out.add(k2)
    return out


# ------------------------------------------------------------------ colours and symbols
def _hex(qcolor: Any) -> str | None:
    try:
        if qcolor is None or (hasattr(qcolor, "isValid") and not qcolor.isValid()):
            return None
        n = str(qcolor.name())
        return n.upper() if re.match(r"^#[0-9a-fA-F]{6}$", n) else None
    except Exception:
        return None


def _call(obj: Any, name: str) -> Any:
    try:
        f = getattr(obj, name, None)
        return f() if callable(f) else None
    except Exception:
        return None


def _layer_colors(sl: Any, note: Callable[[str], None], where: str) -> tuple[str | None, str | None]:
    """(fill/line colour, outline colour) of one symbol layer; sub-symbols (marker line, arrow, geometry
    generator, centroid fill, ...) are followed."""
    lt = str(_call(sl, "layerType") or "")
    if _call(_call(sl, "dataDefinedProperties"), "hasActiveProperties"):
        note(f"{where}: data-defined properties ({lt or 'symbol layer'}) use the base colour.")
    sub = _call(sl, "subSymbol")
    fill = _hex(_call(sl, "fillColor")) or _hex(_call(sl, "color"))
    stroke = _hex(_call(sl, "strokeColor"))
    if sub is not None and (fill is None or lt in ("MarkerLine", "HashLine", "GeometryGenerator", "ArrowLine", "CentroidFill",
                                                   "PointPatternFill", "RandomMarkerFill", "LinePatternFill")):
        sf, so = _symbol_colors_raw(sub, note, f"{where} > {lt}")
        fill, stroke = sf or fill, so or stroke
    if lt in ("GradientFill", "ShapeburstFill", "RasterFill", "SVGFill", "LinePatternFill", "PointPatternFill"):
        note(f"{where}: {lt} is shown as one colour.")
    return fill, stroke


def _symbol_colors_raw(sym: Any, note: Callable[[str], None], where: str) -> tuple[str | None, str | None]:
    fill = stroke = None
    n = _call(sym, "symbolLayerCount") or 0
    for i in range(int(n)):
        try:
            sl = sym.symbolLayer(i)
        except Exception:
            continue
        if sl is None or _call(sl, "enabled") is False:
            continue
        f, s = _layer_colors(sl, note, where)
        fill, stroke = fill or f, stroke or s
        if fill and stroke:
            break
    if fill is None:
        fill = _hex(_call(sym, "color"))
    return fill, stroke


def symbol_colors(sym: Any, note: Callable[[str], None] = lambda m: None, where: str = "symbol") -> dict[str, str]:
    if sym is None:
        note(f"{where}: no symbol; the default colour is used.")
        return dict(FALLBACK)
    try:
        fill, stroke = _symbol_colors_raw(sym, note, where)
    except Exception as e:  # pragma: no cover - defensive
        note(f"{where}: could not be read ({type(e).__name__}); the default colour is used.")
        return dict(FALLBACK)
    if fill is None:
        note(f"{where}: colour could not be read; the default colour is used.")
        fill = FALLBACK["color"]
    return {"color": fill, "outline": stroke or fill}


def _opacity(sym: Any) -> float:
    try:
        v = float(sym.opacity())
        return round(v, 2) if 0 <= v <= 1 else 0.85
    except Exception:
        return 0.85


def _json_value(v: Any) -> Any:
    """Category values -> JSON (QVariant NULL, dates, Decimal, ... become text or None)."""
    try:
        if v is None or (hasattr(v, "isNull") and v.isNull()):
            return None
    except Exception:
        pass
    if isinstance(v, bool) or isinstance(v, str):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    try:
        return str(v.toString()) if hasattr(v, "toString") else str(v)
    except Exception:
        return None


# ------------------------------------------------------------------ renderers
RULE = re.compile(r"""^\s*"?([A-Za-z_][\w ]*?)"?\s*(?:=|\bIS\b)\s*(?:'((?:[^']|'')*)'|(-?\d+(?:\.\d+)?)|(TRUE|FALSE))\s*$""", re.I)


def _categorized(renderer, field, note, out):
    classes = []
    for i, cat in enumerate(_call(renderer, "categories") or []):
        try:
            if _call(cat, "renderState") is False:
                continue
            val = _call(cat, "value")
            if isinstance(val, (list, tuple)):
                note(f"Category {i + 1} groups several values; each value becomes its own class.")
                vals = [_json_value(x) for x in val]
            else:
                vals = [_json_value(val)]
            cols = symbol_colors(_call(cat, "symbol"), note, f"category '{_call(cat, 'label') or val}'")
            for v in vals:
                if v in (None, ""):
                    out["fallback"] = cols          # "all other values"
                    continue
                classes.append({"value": v, "label": str(_call(cat, "label") or v)[:80], **cols})
        except Exception as e:
            note(f"Category {i + 1} could not be read ({type(e).__name__}); skipped.")
    return classes


def _graduated(renderer, note):
    rngs = []
    for i, r in enumerate(_call(renderer, "ranges") or []):
        try:
            if _call(r, "renderState") is False:
                continue
            lo, hi = float(r.lowerValue()), float(r.upperValue())
            if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
                note(f"Range {i + 1} has no valid bounds; skipped.")
                continue
            rngs.append({"min": lo, "max": hi, "label": str(_call(r, "label") or f"{lo:g}–{hi:g}")[:80],
                         **symbol_colors(_call(r, "symbol"), note, f"range '{_call(r, 'label')}'")})
        except Exception as e:
            note(f"Range {i + 1} could not be read ({type(e).__name__}); skipped.")
    return rngs


def _rules(renderer, note):
    """Flatten active rules. Returns (field, classes, else_colors, first_colors)."""
    root = _call(renderer, "rootRule")
    flat: list[Any] = []

    def walk(rule):
        for ch in _call(rule, "children") or []:
            if _call(ch, "active") is False:
                continue
            if _call(ch, "symbol") is not None:
                flat.append(ch)
            walk(ch)
    if root is not None:
        walk(root)
    field = None; classes = []; else_cols = None; first = None; simple = True
    for ch in flat:
        cols = symbol_colors(_call(ch, "symbol"), note, f"rule '{_call(ch, 'label') or _call(ch, 'filterExpression')}'")
        first = first or cols
        if _call(ch, "isElse"):
            else_cols = cols
            continue
        m = RULE.match(str(_call(ch, "filterExpression") or ""))
        if not m:
            simple = False
            continue
        f = m.group(1).strip()
        if field not in (None, f):
            simple = False
            continue
        field = f
        v = m.group(2).replace("''", "'") if m.group(2) is not None else (float(m.group(3)) if "." in m.group(3) else int(m.group(3))) \
            if m.group(3) is not None else m.group(4).upper() == "TRUE"
        classes.append({"value": v, "label": str(_call(ch, "label") or v)[:80], **cols})
    return field, classes, else_cols, first, simple, len(flat)


def _inner(renderer):
    emb = _call(renderer, "embeddedRenderer")
    return emb


def _render(renderer, out, note, fields_ok, depth=0):
    rtype = str(_call(renderer, "type") or "singleSymbol") if renderer is not None else "singleSymbol"
    if rtype in ("pointDisplacement", "pointCluster", "invertedPolygonRenderer", "mergedFeatureRenderer") and depth < 3:
        inner = _inner(renderer)
        note(f"Renderer '{rtype}' is drawn with its inner renderer.")
        if inner is not None:
            return _render(inner, out, note, fields_ok, depth + 1)
    if rtype == "categorizedSymbol":
        field = fields_ok(_call(renderer, "classAttribute"), "Categories")
        classes = _categorized(renderer, field, note, out)
        if field and classes:
            if len(classes) > MAX_CLASSES:
                note(f"Only the first {MAX_CLASSES} classes are kept.")
            out.update(renderer="categorized", field=field, classes=classes[:MAX_CLASSES])
            out["opacity"] = _opacity(_call((_call(renderer, "categories") or [None])[0], "symbol"))
            return
    elif rtype == "graduatedSymbol":
        field = fields_ok(_call(renderer, "classAttribute"), "Ranges")
        rngs = _graduated(renderer, note)
        if field and rngs:
            out.update(renderer="graduated", field=field, ranges=rngs[:MAX_CLASSES])
            out["opacity"] = _opacity(_call((_call(renderer, "ranges") or [None])[0], "symbol"))
            return
    elif rtype == "RuleRenderer":
        field, classes, else_cols, first, simple, n = _rules(renderer, note)
        if else_cols:
            out["fallback"] = else_cols
        f = fields_ok(field, "Rules") if field else None
        if simple and f and classes:
            note(f"Rule-based style ({n} rules) carried over as categories on '{f}'.")
            out.update(renderer="categorized", field=f, classes=classes[:MAX_CLASSES])
            return
        note(f"Rule-based style with expressions ({n} rules) is shown in one colour (เร็วๆ นี้).")
        out.update(renderer="single", single=first or dict(out["fallback"]))
        return
    elif rtype == "25dRenderer":
        roof = _hex(_call(renderer, "roofColor")); wall = _hex(_call(renderer, "wallColor"))
        note("2.5D renderer: roof colour is used; turn on extrusion for 3D.")
        if roof:
            out.update(renderer="single", single={"color": roof, "outline": wall or roof})
            return
    elif rtype == "heatmapRenderer":
        ramp = _call(renderer, "colorRamp")
        c = _hex(_call(ramp, "color2")) or _hex(_call(ramp, "color1"))
        note("Heatmap is shown as points in one colour (เร็วๆ นี้).")
        if c:
            out.update(renderer="single", single={"color": c, "outline": c})
            return
    elif rtype == "nullSymbol":
        note("Layer has no symbols (no symbols renderer); the default colour is used.")
    elif rtype == "singleSymbol":
        sym = _call(renderer, "symbol")
        out.update(renderer="single", single=symbol_colors(sym, note, "single symbol"), opacity=_opacity(sym))
        return
    else:
        note(f"Renderer '{rtype}' is not carried over yet (เร็วๆ นี้); using one colour.")
    # fallback for this renderer only: first symbol we can find, else the fallback colour
    sym = None
    try:
        from qgis.core import QgsRenderContext
        syms = renderer.symbols(QgsRenderContext()) if renderer is not None and hasattr(renderer, "symbols") else []
        sym = syms[0] if syms else None
    except Exception:
        sym = None
    out.update(renderer="single", single=symbol_colors(sym, note, f"{rtype} symbol") if sym is not None else dict(out["fallback"]))


def export_style(renderer: Any, *, label_field: str | None = None, extrusion_field: str | None = None,
                 popup_fields: Iterable[tuple[str, str]] | None = None, title_field: str | None = None,
                 available_fields: Iterable[str] | None = None, label_is_expression: bool = False) -> dict[str, Any]:
    """`available_fields`: field names the server will see (server_fields(geojson)); when given, any style
    reference to another field is dropped with a note instead of making the server refuse the style."""
    reduced: list[str] = []
    note = lambda m: (m not in reduced) and reduced.append(m)  # noqa: E731
    avail = set(available_fields) if available_fields is not None else None

    def fields_ok(name: Any, what: str) -> str | None:
        if not name:
            return None
        raw = str(name).strip()
        if raw.startswith('"') and raw.endswith('"') and raw.count('"') == 2:
            raw = raw[1:-1]
        if re.search(r"[()$'+*/|<>=,\"]", raw) or not raw:
            note(f"{what} use an expression ({str(name)[:60]}); a plain field is needed, so it is not carried over.")
            return None
        f = server_name(raw)
        if not FIELD.match(f):
            note(f"{what}: field '{raw}' cannot be used; not carried over.")
            return None
        if avail is not None and f not in avail:
            note(f"{what}: field '{raw}' has no values in the exported data; not carried over.")
            return None
        return f

    out: dict[str, Any] = {"version": 1, "fallback": dict(FALLBACK), "opacity": 0.85}
    try:
        _render(renderer, out, note, fields_ok)
    except Exception as e:  # last resort, should not happen
        note(f"Style could not be read ({type(e).__name__}: {e}); one colour is used.")
        out.update(renderer="single", single=dict(out["fallback"]))
    out.setdefault("renderer", "single")
    if out["renderer"] == "single":
        out.setdefault("single", dict(out["fallback"]))
    if label_field and not label_is_expression:
        lf = fields_ok(label_field, "Labels")
        if lf:
            out["labelField"] = lf
    elif label_field:
        note("Labels use an expression; not carried over.")
    if extrusion_field:
        ef = fields_ok(extrusion_field, "Extrusion")
        if ef:
            out["extrusionField"] = ef
    if popup_fields or title_field:
        pf, seen = [], set()
        for n, lbl in popup_fields or []:
            f = server_name(n)
            if FIELD.match(f) and (avail is None or f in avail) and f not in seen:
                seen.add(f); pf.append({"name": f, "label": str(lbl or n)[:80]})
        out["popup"] = {"fields": pf[:30]}
        t = server_name(title_field) if title_field and not label_is_expression else None
        if t and FIELD.match(t) and (avail is None or t in avail):
            out["popup"]["title"] = t
    out["reduced"] = reduced[:20]
    return out


def minimal_style(base: dict[str, Any], why: str) -> dict[str, Any]:
    """Last-resort style the server always accepts: one colour, no field references."""
    single = base.get("single") or (base.get("classes") or base.get("ranges") or [base.get("fallback") or FALLBACK])[0]
    col = {"color": single.get("color", FALLBACK["color"]), "outline": single.get("outline", single.get("color", FALLBACK["outline"]))}
    return {"version": 1, "renderer": "single", "single": col, "fallback": dict(FALLBACK), "opacity": base.get("opacity", 0.85),
            "reduced": (list(base.get("reduced") or []) + [why])[:20]}
