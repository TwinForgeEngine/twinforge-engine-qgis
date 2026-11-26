"""Every renderer / symbol type -> TwinForge Style JSON, validated with the server's own rules (core/tfstyle.py
+ the server's field inference on the exported GeoJSON). Runs on QGIS 3.x (Qt5) and QGIS 4.x (Qt6)."""
import json, os, sys, tempfile
from pathlib import Path
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication
APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()
from qgis.core import (Qgs25DRenderer, QgsArrowSymbolLayer, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransformContext, QgsFeature, QgsFillSymbol, QgsGeometry, QgsGeometryGeneratorSymbolLayer,
                       QgsGradientFillSymbolLayer, QgsGraduatedSymbolRenderer, QgsHeatmapRenderer, QgsInvertedPolygonRenderer,
                       QgsLinePatternFillSymbolLayer, QgsLineSymbol, QgsMarkerLineSymbolLayer, QgsMarkerSymbol, QgsNullSymbolRenderer,
                       QgsPointClusterRenderer, QgsPointDisplacementRenderer, QgsProperty, QgsRendererCategory, QgsRendererRange,
                       QgsRuleBasedRenderer, QgsShapeburstFillSymbolLayer, QgsSingleSymbolRenderer, QgsSVGFillSymbolLayer,
                       QgsSvgMarkerSymbolLayer, QgsSymbolLayer, QgsVectorFileWriter, QgsVectorLayer, QgsGradientColorRamp)
from qgis.PyQt.QtGui import QColor
from twinforge_engine_qgis.core import tfstyle
from twinforge_engine_qgis.core.style_export import export_style, minimal_style, server_fields

ROADS = ["primary", "secondary", "residential", "service"]


def layer(kind):
    geom = {"line": "LineString", "point": "Point", "poly": "Polygon"}[kind]
    lyr = QgsVectorLayer(f"{geom}?crs=epsg:4326&field=highway:string&field=Name:string&field=Road Type:string&field=ref:string"
                         f"&field=lanes:integer&field=maxspeed:double", f"roads_{kind}", "memory")
    feats = []
    for i in range(12):
        x, y = 100.5 + i * 0.001, 13.7 + (i % 3) * 0.001
        g = {"line": f"LINESTRING({x} {y}, {x + 0.0008} {y + 0.0005})", "point": f"POINT({x} {y})",
             "poly": f"POLYGON(({x} {y}, {x + 0.0005} {y}, {x + 0.0005} {y + 0.0005}, {x} {y + 0.0005}, {x} {y}))"}[kind]
        f = QgsFeature(lyr.fields()); f.setGeometry(QgsGeometry.fromWkt(g))
        f.setAttributes([ROADS[i % 4], f"Road {i}", "Main", None, 1 + i % 4, 30.0 + 10 * (i % 5)])   # ref is always NULL
        feats.append(f)
    lyr.dataProvider().addFeatures(feats); lyr.updateExtents()
    return lyr


def geojson(lyr):
    out = os.path.join(tempfile.mkdtemp(), "l.geojson")
    opt = QgsVectorFileWriter.SaveVectorOptions(); opt.driverName = "GeoJSON"; opt.layerOptions = ["RFC7946=YES"]
    QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out, QgsCoordinateTransformContext(), opt)
    return Path(out).read_bytes()


def sym_for(kind, color="#E67E22"):
    return {"line": QgsLineSymbol.createSimple({"color": color, "width": "0.8"}),
            "point": QgsMarkerSymbol.createSimple({"color": color, "outline_color": "#222222"}),
            "poly": QgsFillSymbol.createSimple({"color": color, "outline_color": "#222222"})}[kind]


def prop(name):
    P = QgsSymbolLayer.Property
    return getattr(P, name)


def check(lyr, renderer, **kw):
    """Export like the plugin does and validate exactly like the server does."""
    lyr.setRenderer(renderer)
    data = geojson(lyr); avail = server_fields(data)
    st = export_style(lyr.renderer(), popup_fields=[(f.name(), f.name()) for f in lyr.fields()], available_fields=avail, **kw)
    json.dumps(st)                                   # must be JSON
    norm = tfstyle.normalize(st, sorted(avail))      # must be accepted by the server
    return st, norm, avail


# ------------------------------------------------------------------ root cause (0.2.3)
def test_null_only_field_was_refused_by_server_and_is_now_dropped():
    lyr = layer("line"); data = geojson(lyr); avail = server_fields(data)
    assert "ref" not in avail and "road_type" in avail and "name" in avail
    old = {"version": 1, "renderer": "single", "single": {"color": "#E67E22", "outline": "#E67E22"},
           "popup": {"fields": [{"name": f.name().lower(), "label": f.name()} for f in lyr.fields() if f.name().islower()]}}
    with pytest.raises(tfstyle.StyleError, match="ref"):
        tfstyle.normalize(old, sorted(avail))
    st, norm, _ = check(lyr, QgsSingleSymbolRenderer(sym_for("line")))
    names = [f["name"] for f in norm["popup"]["fields"]]
    assert "ref" not in names and "road_type" in names and "name" in names


# ------------------------------------------------------------------ renderers on lines / points / polygons
@pytest.mark.parametrize("kind", ["line", "point", "poly"])
def test_single(kind):
    st, n, _ = check(layer(kind), QgsSingleSymbolRenderer(sym_for(kind)))
    assert n["renderer"] == "single" and n["single"]["color"] == "#E67E22"


@pytest.mark.parametrize("kind", ["line", "point", "poly"])
def test_categorized_with_null_and_list_categories(kind):
    cats = [QgsRendererCategory(v, sym_for(kind, c), v) for v, c in zip(ROADS[:3], ["#E67E22", "#8E44AD", "#3498DB"])]
    cats.append(QgsRendererCategory(["service", "track"], sym_for(kind, "#16A085"), "minor"))
    cats.append(QgsRendererCategory(None, sym_for(kind, "#999999"), "other"))
    st, n, _ = check(layer(kind), QgsCategorizedSymbolRenderer("highway", cats))
    assert n["renderer"] == "categorized" and n["field"] == "highway"
    assert {c["value"]: c["color"] for c in n["classes"]} == {"primary": "#E67E22", "secondary": "#8E44AD", "residential": "#3498DB",
                                                            "service": "#16A085", "track": "#16A085"}
    assert n["fallback"]["color"] == "#999999"


def test_categorized_on_field_with_capitals_and_spaces():
    lyr = layer("line")
    st, n, _ = check(lyr, QgsCategorizedSymbolRenderer("Road Type", [QgsRendererCategory("Main", sym_for("line"), "Main")]))
    assert n["renderer"] == "categorized" and n["field"] == "road_type"
    st, n, _ = check(lyr, QgsCategorizedSymbolRenderer("Name", [QgsRendererCategory("Road 1", sym_for("line"), "R1")]))
    assert n["field"] == "name"


def test_categorized_on_expression_falls_back_to_single_with_note():
    st, n, _ = check(layer("line"), QgsCategorizedSymbolRenderer("upper(\"highway\")", [QgsRendererCategory("PRIMARY", sym_for("line"), "P")]))
    assert n["renderer"] == "single" and any("expression" in r for r in st["reduced"])


def test_categorized_on_null_only_field_falls_back():
    st, n, _ = check(layer("line"), QgsCategorizedSymbolRenderer("ref", [QgsRendererCategory("A1", sym_for("line"), "A1")]))
    assert n["renderer"] == "single" and any("ref" in r for r in st["reduced"])


@pytest.mark.parametrize("kind", ["line", "point", "poly"])
def test_graduated(kind):
    rngs = [QgsRendererRange(0, 2, sym_for(kind, "#FFEDA0"), "1–2"), QgsRendererRange(2, 4, sym_for(kind, "#F03B20"), "3–4"),
            QgsRendererRange(float("nan"), 5, sym_for(kind), "bad")]
    st, n, _ = check(layer(kind), QgsGraduatedSymbolRenderer("lanes", rngs))
    assert n["renderer"] == "graduated" and len(n["ranges"]) == 2 and n["ranges"][1]["color"] == "#F03B20"


def _rule_renderer(kind, exprs):
    root = QgsRuleBasedRenderer.Rule(None)
    for i, (e, c) in enumerate(exprs):
        r = QgsRuleBasedRenderer.Rule(sym_for(kind, c), 0, 0, e or "", f"rule {i}")
        if e is None:
            r.setIsElse(True)
        root.appendChild(r)
    return QgsRuleBasedRenderer(root)


@pytest.mark.parametrize("kind", ["line", "point", "poly"])
def test_rule_based_simple_rules_become_categories(kind):
    st, n, _ = check(layer(kind), _rule_renderer(kind, [("\"highway\" = 'primary'", "#E67E22"), ("highway = 'secondary'", "#8E44AD"),
                                                        ("\"lanes\" = 2", "#000000"), (None, "#7F8C8D")]))
    # mixed fields -> not all simple on one field -> single colour from the first rule, ELSE becomes fallback
    assert n["renderer"] == "single" and n["single"]["color"] == "#E67E22" and n["fallback"]["color"] == "#7F8C8D"
    st, n, _ = check(layer(kind), _rule_renderer(kind, [("\"highway\" = 'primary'", "#E67E22"), ("\"highway\" = 'secondary'", "#8E44AD"),
                                                        (None, "#7F8C8D")]))
    assert n["renderer"] == "categorized" and n["field"] == "highway"
    assert [c["value"] for c in n["classes"]] == ["primary", "secondary"] and n["fallback"]["color"] == "#7F8C8D"


def test_rule_based_with_expressions_and_nested_rules():
    root = QgsRuleBasedRenderer.Rule(None)
    parent = QgsRuleBasedRenderer.Rule(None, 0, 0, "\"lanes\" > 1", "wide")
    parent.appendChild(QgsRuleBasedRenderer.Rule(sym_for("line", "#C0392B"), 0, 0, "\"maxspeed\" >= 50", "fast"))
    root.appendChild(parent)
    off = QgsRuleBasedRenderer.Rule(sym_for("line", "#00FF00"), 0, 0, "", "off"); off.setActive(False); root.appendChild(off)
    st, n, _ = check(layer("line"), QgsRuleBasedRenderer(root))
    assert n["renderer"] == "single" and n["single"]["color"] == "#C0392B" and any("Rule-based" in r for r in st["reduced"])


def test_line_symbol_layers_arrow_marker_line_geometry_generator_and_data_defined():
    sym = QgsLineSymbol()
    sym.deleteSymbolLayer(0)
    ml = QgsMarkerLineSymbolLayer.create({}); ml.setSubSymbol(QgsMarkerSymbol.createSimple({"color": "#8E44AD"}))
    sym.appendSymbolLayer(ml)
    sym.appendSymbolLayer(QgsArrowSymbolLayer.create({}))
    gg = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": "buffer($geometry, 0.0001)", "SymbolType": "Fill"})
    sym.appendSymbolLayer(gg)
    st, n, _ = check(layer("line"), QgsSingleSymbolRenderer(sym))
    assert n["single"]["color"] == "#8E44AD"
    s2 = QgsLineSymbol.createSimple({"color": "#E67E22"})
    s2.symbolLayer(0).setDataDefinedProperty(prop("StrokeColor"), QgsProperty.fromExpression("if(\"lanes\">2,'red','blue')"))
    st, n, _ = check(layer("line"), QgsSingleSymbolRenderer(s2))
    assert n["single"]["color"] == "#E67E22" and any("data-defined" in r for r in st["reduced"])


def test_fill_symbol_layers_gradient_shapeburst_svg_line_pattern():
    for sl, expect in [(QgsGradientFillSymbolLayer.create({"color": "#112233", "gradient_color2": "#445566"}), "#112233"),
                       (QgsShapeburstFillSymbolLayer.create({"color": "#223344"}), "#223344"),
                       (QgsSVGFillSymbolLayer.create({"color": "#334455"}), None),
                       (QgsLinePatternFillSymbolLayer.create({"color": "#445566"}), None)]:
        sym = QgsFillSymbol(); sym.deleteSymbolLayer(0); sym.appendSymbolLayer(sl)
        st, n, _ = check(layer("poly"), QgsSingleSymbolRenderer(sym))
        assert n["renderer"] == "single" and (expect is None or n["single"]["color"] == expect), (sl.layerType(), n)


def test_svg_marker_and_point_renderers():
    sym = QgsMarkerSymbol(); sym.deleteSymbolLayer(0); svg = QgsSvgMarkerSymbolLayer.create({}); svg.setColor(QColor("#1ABC9C")); sym.appendSymbolLayer(svg)
    st, n, _ = check(layer("point"), QgsSingleSymbolRenderer(sym))
    assert n["single"]["color"] == "#1ABC9C"
    cats = QgsCategorizedSymbolRenderer("highway", [QgsRendererCategory("primary", sym_for("point", "#E67E22"), "p")])
    for wrap in (QgsPointDisplacementRenderer(), QgsPointClusterRenderer()):
        wrap.setEmbeddedRenderer(cats.clone())
        st, n, _ = check(layer("point"), wrap)
        assert n["renderer"] == "categorized" and n["classes"][0]["color"] == "#E67E22"
    hm = QgsHeatmapRenderer(); hm.setColorRamp(QgsGradientColorRamp(QColor("#FFFFFF"), QColor("#D35400")))
    st, n, _ = check(layer("point"), hm)
    assert n["renderer"] == "single" and n["single"]["color"] == "#D35400"


def test_polygon_renderers_25d_inverted_and_null():
    r = Qgs25DRenderer(); r.setRoofColor(QColor("#B03A2E")); r.setWallColor(QColor("#7B241C"))
    st, n, _ = check(layer("poly"), r)
    assert n["single"] == {"color": "#B03A2E", "outline": "#7B241C"}
    grad = QgsGraduatedSymbolRenderer("maxspeed", [QgsRendererRange(0, 100, sym_for("poly", "#2E86C1"), "all")])
    inv = QgsInvertedPolygonRenderer(grad)
    st, n, _ = check(layer("poly"), inv)
    assert n["renderer"] == "graduated" and n["field"] == "maxspeed"
    st, n, _ = check(layer("poly"), QgsNullSymbolRenderer())
    assert n["renderer"] == "single"


def test_labels_extrusion_and_expression_labels():
    st, n, _ = check(layer("poly"), QgsSingleSymbolRenderer(sym_for("poly")), label_field="Name", extrusion_field="lanes", title_field="Name")
    assert n["labelField"] == "name" and n["extrusionField"] == "lanes" and n["popup"]["title"] == "name"
    st, n, _ = check(layer("poly"), QgsSingleSymbolRenderer(sym_for("poly")), label_field="\"Name\" || ' ' || \"ref\"",
                     label_is_expression=True, title_field="\"Name\" || ' ' || \"ref\"", extrusion_field="ref")
    assert "labelField" not in n and "extrusionField" not in n and "title" not in n["popup"]


def test_minimal_style_is_always_accepted():
    st = export_style(None)
    assert tfstyle.normalize(minimal_style(st, "x"), [])["renderer"] == "single"
