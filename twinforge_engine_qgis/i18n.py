"""Dock text in Thai, English and Japanese. Picks the QGIS interface language; anything else falls back to English."""
from __future__ import annotations

T = {
    "en": {
        "server": "Server", "key": "Access token", "key_ph": "tft_ token from Account, API keys",
        "connect": "Connect", "forget": "Forget token", "not_connected": "Not connected",
        "project": "Project", "scene": "Engine scene (optional)", "scene_ph": "Scene id, for example scn_8f2c",
        "pick": "QGIS layers to publish", "extrude": "Extrude by field", "no_extrude": "No extrusion",
        "publish": "Publish to TwinForge Engine", "url_ph": "The stream URL appears here",
        "copy": "Copy stream URL", "open_engine": "Open in Engine", "open_map": "Open TwinForge Map",
        "autosync": "Auto sync (checks every 60 seconds after you save edits)", "autosync_short": "Auto sync after saving edits",
        "gpkg_btn": "Publish a GeoPackage file", "gpkg_pick": "Choose a GeoPackage", "gpkg_none": "This GeoPackage has no layers with geometry", "gpkg_task": "Uploading GeoPackage to TwinForge Engine", "gpkg_done": "Published {n} of {m} layers from {file}", "gpkg_failed": "{n} layer(s) could not be published, see the log",
        "note": "Sent with each layer: classes, colours, legend, labels and pop-ups. A GeoPackage file can be published as it is, with all its layers.",
        "remote": "Layers in TwinForge Engine", "refresh": "Refresh", "add_qgis": "Add to QGIS",
        "connected": "Connected with token \u201c{name}\u201d", "read_only": "Connected read-only. Add gis:publish to the token to publish.",
        "personal": "Created your project \u201c{name}\u201d",
        "need_connect": "Connect with your access token and choose a project first", "need_layer": "Tick at least one layer",
        "published": "Published {n} layer(s)", "reduced": "Simplified styling in {n} place(s), see the log",
        "need_scene": "Publish a layer and enter a scene id first", "forgot": "Token removed from this computer",
        "added": "Added \u201c{name}\u201d to QGIS", "add_failed": "Could not add this layer to QGIS", "no_remote": "No layers in this project yet",
        "publish_task": "Publishing to TwinForge Engine", "fail": "Publishing failed. Please try again.",
    },
    "th": {
        "server": "เซิร์ฟเวอร์", "key": "โทเค็นการเข้าถึง", "key_ph": "โทเค็น tft_ จากหน้าบัญชี เมนู API keys",
        "connect": "เชื่อมต่อ", "forget": "ลืมโทเค็น", "not_connected": "ยังไม่ได้เชื่อมต่อ",
        "project": "โครงการ", "scene": "ฉากใน Engine (ไม่บังคับ)", "scene_ph": "รหัสฉาก เช่น scn_8f2c",
        "pick": "เลือกเลเยอร์ QGIS ที่จะเผยแพร่", "extrude": "ยืดความสูงตามฟิลด์", "no_extrude": "ไม่ยืดความสูง",
        "publish": "เผยแพร่ไปยัง TwinForge Engine", "url_ph": "Stream URL จะแสดงที่นี่",
        "copy": "คัดลอก Stream URL", "open_engine": "เปิดใน Engine", "open_map": "เปิด TwinForge Map",
        "autosync": "ซิงก์อัตโนมัติ (ตรวจทุก 60 วินาที หลังบันทึกการแก้ไข)", "autosync_short": "ซิงก์อัตโนมัติหลังบันทึก",
        "gpkg_btn": "เผยแพร่ไฟล์ GeoPackage", "gpkg_pick": "เลือกไฟล์ GeoPackage", "gpkg_none": "ไฟล์ GeoPackage นี้ไม่มีเลเยอร์ที่มีรูปทรง", "gpkg_task": "กำลังอัปโหลด GeoPackage ไปยัง TwinForge Engine", "gpkg_done": "เผยแพร่ {n} จาก {m} เลเยอร์ใน {file} แล้ว", "gpkg_failed": "เผยแพร่ไม่สำเร็จ {n} เลเยอร์ ดูรายละเอียดในบันทึก",
        "note": "ส่งไปพร้อมกับเลเยอร์: คลาส สี คำอธิบายสัญลักษณ์ ป้ายชื่อ และป๊อปอัป ไฟล์ GeoPackage เผยแพร่ได้ทั้งไฟล์พร้อมทุกเลเยอร์",
        "remote": "เลเยอร์ใน TwinForge Engine", "refresh": "รีเฟรช", "add_qgis": "เพิ่มลงใน QGIS",
        "connected": "เชื่อมต่อแล้วด้วยโทเค็น \u201c{name}\u201d", "read_only": "เชื่อมต่อแบบอ่านอย่างเดียว เพิ่มสิทธิ์ gis:publish ให้โทเค็นเพื่อเผยแพร่",
        "personal": "สร้างโครงการ \u201c{name}\u201d ให้คุณแล้ว",
        "need_connect": "เชื่อมต่อด้วยโทเค็นและเลือกโครงการก่อน", "need_layer": "เลือกอย่างน้อยหนึ่งเลเยอร์",
        "published": "เผยแพร่ {n} เลเยอร์แล้ว", "reduced": "สไตล์ถูกลดทอน {n} จุด ดูรายละเอียดในบันทึก",
        "need_scene": "เผยแพร่และใส่รหัสฉากก่อน", "forgot": "ลบโทเค็นออกจากเครื่องนี้แล้ว",
        "added": "เพิ่ม \u201c{name}\u201d ลงใน QGIS แล้ว", "add_failed": "เพิ่มเลเยอร์นี้ลงใน QGIS ไม่ได้", "no_remote": "ยังไม่มีเลเยอร์ในโครงการนี้",
        "publish_task": "เผยแพร่ไปยัง TwinForge Engine", "fail": "เผยแพร่ไม่สำเร็จ ลองอีกครั้ง",
    },
    "ja": {
        "server": "サーバー", "key": "アクセストークン", "key_ph": "アカウントの API keys で作成した tft_ トークン",
        "connect": "接続", "forget": "トークンを削除", "not_connected": "未接続",
        "project": "プロジェクト", "scene": "Engine のシーン（任意）", "scene_ph": "シーン ID（例: scn_8f2c）",
        "pick": "公開する QGIS レイヤー", "extrude": "高さに使うフィールド", "no_extrude": "高さなし",
        "publish": "TwinForge Engine に公開", "url_ph": "ここにストリーム URL が表示されます",
        "copy": "ストリーム URL をコピー", "open_engine": "Engine で開く", "open_map": "TwinForge Map を開く",
        "autosync": "自動同期（編集を保存すると 60 秒ごとに確認）", "autosync_short": "保存後に自動同期",
        "gpkg_btn": "GeoPackage ファイルを公開", "gpkg_pick": "GeoPackage を選択", "gpkg_none": "この GeoPackage にはジオメトリのあるレイヤーがありません", "gpkg_task": "GeoPackage を TwinForge Engine にアップロード中", "gpkg_done": "{file} の {m} レイヤー中 {n} レイヤーを公開しました", "gpkg_failed": "{n} レイヤーを公開できませんでした（ログを参照）",
        "note": "レイヤーと一緒に送信: クラス、色、凡例、ラベル、ポップアップ。GeoPackage はファイルのまま、すべてのレイヤーを公開できます。",
        "remote": "TwinForge Engine のレイヤー", "refresh": "更新", "add_qgis": "QGIS に追加",
        "connected": "トークン\u300c{name}\u300dで接続しました", "read_only": "読み取り専用で接続しました。公開するにはトークンに gis:publish を追加してください。",
        "personal": "プロジェクト\u300c{name}\u300dを作成しました",
        "need_connect": "先にトークンで接続し、プロジェクトを選んでください", "need_layer": "レイヤーを 1 つ以上選んでください",
        "published": "{n} 件のレイヤーを公開しました", "reduced": "{n} か所のスタイルを簡略化しました（ログを参照）",
        "need_scene": "先にレイヤーを公開し、シーン ID を入力してください", "forgot": "このコンピューターからトークンを削除しました",
        "added": "\u300c{name}\u300dを QGIS に追加しました", "add_failed": "このレイヤーを QGIS に追加できませんでした", "no_remote": "このプロジェクトにはまだレイヤーがありません",
        "publish_task": "TwinForge Engine に公開中", "fail": "公開できませんでした。もう一度お試しください。",
    },
}

ERRORS = {
    "en": {"token_required": "Enter your access token first", "token_invalid": "This token is not valid. Check that you copied all of it",
           "token_expired": "This token has expired. Create a new one in Account, API keys", "token_revoked": "This token was revoked",
           "scope_missing": "This token is missing a permission. It needs gis:read, and gis:publish to publish",
           "origin_not_allowed": "This token is limited to certain websites and cannot be used from QGIS",
           "forbidden": "Your account cannot edit this project", "project_not_found": "Project not found, or you have no access",
           "too_large": "The file is larger than the limit", "geometry_mixed": "This layer mixes geometry types. Split it into one type per layer",
           "geojson_invalid": "The layer could not be read as GeoJSON", "name_invalid": "Rename the layer using letters and numbers",
           "not_cog": "The raster is not a COG yet", "style_invalid": "The style could not be read, a single colour is used instead",
           "rate_limited": "Too many requests. Wait a moment and try again", "gis_unavailable": "Map layers are not available right now. Try again later",
           "network": "Cannot reach the server. Check your internet connection and try again"},
    "th": {"token_required": "ใส่โทเค็นการเข้าถึงก่อน", "token_invalid": "โทเค็นไม่ถูกต้อง ตรวจว่าคัดลอกครบทั้งโทเค็น",
           "token_expired": "โทเค็นนี้หมดอายุแล้ว สร้างใหม่ที่หน้าบัญชี เมนู API keys", "token_revoked": "โทเค็นนี้ถูกยกเลิกแล้ว",
           "scope_missing": "โทเค็นนี้ไม่มีสิทธิ์ที่ต้องใช้ ต้องมี gis:read และต้องมี gis:publish เพื่อเผยแพร่",
           "origin_not_allowed": "โทเค็นนี้จำกัดเว็บไซต์ไว้ ใช้กับ QGIS ไม่ได้",
           "forbidden": "บัญชีนี้ไม่มีสิทธิ์แก้ไขโครงการนี้", "project_not_found": "ไม่พบโครงการ หรือไม่มีสิทธิ์เข้าถึง",
           "too_large": "ไฟล์ใหญ่เกินกำหนด", "geometry_mixed": "ชั้นนี้มีรูปทรงหลายชนิดปนกัน แยกเป็นชั้นละชนิดก่อนเผยแพร่",
           "geojson_invalid": "อ่านเลเยอร์เป็น GeoJSON ไม่ได้", "name_invalid": "เปลี่ยนชื่อเลเยอร์ให้ใช้ตัวอักษรและตัวเลข",
           "not_cog": "ไฟล์แรสเตอร์ยังไม่ใช่ COG", "style_invalid": "อ่านสไตล์ไม่ได้ ระบบจะใช้สีเดียวแทน",
           "rate_limited": "ส่งคำขอถี่เกินไป รอสักครู่แล้วลองใหม่", "gis_unavailable": "ตอนนี้ยังใช้เลเยอร์แผนที่ไม่ได้ ลองใหม่ภายหลัง",
           "network": "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ตรวจอินเทอร์เน็ตแล้วลองอีกครั้ง"},
    "ja": {"token_required": "先にアクセストークンを入力してください", "token_invalid": "トークンが正しくありません。全体をコピーしたか確認してください",
           "token_expired": "トークンの有効期限が切れています。アカウントの API keys で新しく作成してください", "token_revoked": "このトークンは取り消されています",
           "scope_missing": "トークンの権限が不足しています。gis:read と、公開には gis:publish が必要です",
           "origin_not_allowed": "このトークンは特定のサイト専用のため QGIS では使えません",
           "forbidden": "このアカウントではこのプロジェクトを編集できません", "project_not_found": "プロジェクトが見つからないか、アクセス権がありません",
           "too_large": "ファイルが上限を超えています", "geometry_mixed": "ジオメトリの種類が混在しています。種類ごとにレイヤーを分けてください",
           "geojson_invalid": "レイヤーを GeoJSON として読み込めませんでした", "name_invalid": "レイヤー名を英数字に変更してください",
           "not_cog": "ラスターがまだ COG ではありません", "style_invalid": "スタイルを読み込めなかったため単色で表示します",
           "rate_limited": "リクエストが多すぎます。少し待ってから再試行してください", "gis_unavailable": "現在マップレイヤーを利用できません。後でもう一度お試しください",
           "network": "サーバーに接続できません。インターネット接続を確認してください"},
}


def lang() -> str:
    """Language of the QGIS interface (QgsApplication.locale()); TWINFORGE_LANG overrides it for tests."""
    import os
    loc = os.environ.get("TWINFORGE_LANG", "")
    if not loc:
        try:
            from qgis.core import QgsApplication
            loc = QgsApplication.locale() or ""
        except Exception:
            loc = ""
    loc = loc.lower()[:2]
    return loc if loc in T else "en"


def tr(key: str, **kw) -> str:
    s = T[lang()].get(key) or T["en"][key]
    return s.format(**kw) if kw else s


def err_text(code: str) -> str:
    L = lang()
    return ERRORS[L].get(code) or ERRORS["en"].get(code) or T[L]["fail"]
