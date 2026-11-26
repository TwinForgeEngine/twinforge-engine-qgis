"""QGIS renderer -> TwinForge Style JSON v1 (classes, colours, legend, popup only).

Works on real QgsFeatureRenderer objects and on duck-typed fakes in unit tests:
  renderer.type()                       -> 'singleSymbol' | 'categorizedSymbol' | 'graduatedSymbol' | other
  renderer.symbol() / .categories() / .ranges() / .classAttribute()
  symbol.color().name()  (#rrggbb)  ;  symbol.symbolLayer(0).strokeColor().name() when available
Anything QGIS can draw but phase 1 can't carry (rule-based, expressions, gradients, hatching, data-defined
sizes, …) is reduced to a single colour with a note — publishing never fails because of style."""
from __future__ import annotations

import re
from typing import Any

FIELD = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
FALLBACK = {"color": "#8AA8A1", "outline": "#1A3D38"}


def _hex(qcolor: Any, default: str) -> str:
    try:
        n = qcolor.name()
        return n.upper() if re.match(r"^#[0-9a-fA-F]{6}$", n) else default
    except Exception:
        return default


def _symbol_colors(sym: Any) -> dict[str, str]:
    fill = _hex(sym.color(), FALLBACK["color"]) if sym is not None else FALLBACK["color"]
    outline = fill
    try:
        sl = sym.symbolLayer(0)
        if hasattr(sl, "strokeColor"):
            outline = _hex(sl.strokeColor(), fill)
    except Exception:
        pass
    return {"color": fill, "outline": outline}


def _opacity(sym: Any) -> float:
    try:
        return round(float(sym.opacity()), 2)
    except Exception:
        return 0.85


def _field(name: str | None, reduced: list[str], what: str) -> str | None:
    if not name:
        return None
    f = name.strip().strip('"').lower()
    if FIELD.match(f):
        return f
    reduced.append(f"{what} uses an expression ({name}); phase 1 needs a plain field.")
    return None


def export_style(renderer: Any, *, label_field: str | None = None, extrusion_field: str | None = None,
                 popup_fields: list[tuple[str, str]] | None = None, title_field: str | None = None) -> dict[str, Any]:
    reduced: list[str] = []
    rtype = renderer.type() if renderer is not None else "singleSymbol"
    out: dict[str, Any] = {"version": 1, "fallback": dict(FALLBACK)}
    if rtype == "categorizedSymbol":
        field = _field(renderer.classAttribute(), reduced, "Categories")
        classes = []
        for cat in renderer.categories():
            if hasattr(cat, "renderState") and not cat.renderState():
                continue
            val = cat.value()
            if val is None or val == "" or (isinstance(val, (list, tuple))):
                if isinstance(val, (list, tuple)):
                    reduced.append("A category groups several values; only the first value is kept.")
                    val = val[0] if val else None
                if val in (None, ""):        # QGIS "all other values" -> fallback colour
                    out["fallback"] = _symbol_colors(cat.symbol())
                    continue
            classes.append({"value": val, "label": cat.label() or str(val), **_symbol_colors(cat.symbol())})
        if field and classes:
            out.update(renderer="categorized", field=field, classes=classes, opacity=_opacity(renderer.categories()[0].symbol()))
        else:
            out.update(renderer="single", single=dict(out["fallback"]))
    elif rtype == "graduatedSymbol":
        field = _field(renderer.classAttribute(), reduced, "Ranges")
        rngs = [{"min": float(r.lowerValue()), "max": float(r.upperValue()), "label": r.label() or f"{r.lowerValue()}–{r.upperValue()}",
                 **_symbol_colors(r.symbol())} for r in renderer.ranges() if not hasattr(r, "renderState") or r.renderState()]
        if field and rngs:
            out.update(renderer="graduated", field=field, ranges=rngs, opacity=_opacity(renderer.ranges()[0].symbol()))
        else:
            out.update(renderer="single", single=dict(out["fallback"]))
    else:
        sym = renderer.symbol() if rtype == "singleSymbol" and renderer is not None else None
        if rtype != "singleSymbol":
            reduced.append(f"Renderer '{rtype}' is not carried over yet (เร็วๆ นี้); using one colour.")
            try:
                syms = renderer.symbols(None) if hasattr(renderer, "symbols") else []
                sym = syms[0] if syms else None
            except Exception:
                sym = None
        cols = _symbol_colors(sym) if sym is not None else dict(FALLBACK)
        out.update(renderer="single", single=cols, opacity=_opacity(sym) if sym is not None else 0.85)
    if label_field:
        lf = _field(label_field, reduced, "Labels")
        if lf:
            out["labelField"] = lf
    if extrusion_field:
        ef = _field(extrusion_field, reduced, "Extrusion")
        if ef:
            out["extrusionField"] = ef
    if popup_fields or title_field:
        pf = [{"name": n.lower(), "label": lbl} for n, lbl in (popup_fields or []) if FIELD.match(n.lower())]
        out["popup"] = {"fields": pf, **({"title": title_field.lower()} if title_field and FIELD.match(title_field.lower()) else {})}
    out["reduced"] = reduced
    return out
