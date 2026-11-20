"""Synthetic Space Station data folder for tests: no real user data and no Flydigi files.

build(root) creates the folder layout the plugin reads (Configs/Controller/<model>/..., resources/app.asar)
with generated profiles and a synthetic app built from tests/schema_stub.py, then points the plugin at it
through FLYDIGI_DATA_DIR, FLYDIGI_BACKUP_DIR, FLYDIGI_EXPORT_DIR and FLYDIGI_CACHE_DIR."""

import json
import os
import struct

from flydigi import profile, schema

MODEL = "f5"
# Profile format version per model, as found in each model's factory profiles (768 = older stick protocol).
PROTO = {"f5": 770, "f4": 769, "k2": 768, "f3p": 768, "fp4": 769}  # most APEX 4 editions are 768
UID = "0000000000000000000000test"
VERSION = "4.2.3.1"
# The 32 button slots an f5 profile carries (ids from the ControllerKey enum; 26 and 29-31 are reserved).
KEY_IDS = list(range(0, 32))


def bean(title: str, cfg_id: int = 0, center: int = 5, edge: int = 0, p1=(63, 63), model: str = MODEL):
    b = schema.msg("ControllerMappingConfigBean")()
    old = PROTO[model] < 769
    if old:  # the older protocol has no edge deadzone and no curve table
        edge, center = 0, abs(center)
    b.cfgId, b.protoVersion, b.packageCount, b.dataVersion, b.title = cfg_id, PROTO[model], 77, 65535, title
    kmt = schema.enum_values("KeyMapType")
    for k in KEY_IDS:
        kb = b.keyConfigBeans.keyConfigBean.add()
        kb.keyId = k
        kb.mapType = kmt["KeyMapType_Key"]
        kb.mapTypeKey.mapControllerKeyId = k
    for side in ("left", "right"):
        js = getattr(b.joystickConfigBean, side + "JoystickParam")
        js.End = 127
        j = js.mapTypeJoystick
        j.circularityType = schema.enum_values("JoystickCircularityType")["JoystickCircularityType_Circular"]
        j.center, j.edge = center, edge
        sc = j.sensitivityConfig
        sc.point1.x, sc.point1.y = p1
        sc.point2.x, sc.point2.y = 127, 127
        if not old:
            sc.type = schema.enum_values("JoystickSensitivityType")["JoystickSensitivityType_Custom"]
            sc.points.extend(profile.curve_points(center, edge, p1, (127, 127)))
    for side in ("left", "right"):
        t = getattr(b.triggerConfigBean, side + "TriggerConfigBean")
        t.Zero, t.End = 0, 255
        t.point2.x = t.point2.y = 255
        t.triggerVibrationConfigBean.enable = True
    v = b.vibrationConfigBean
    v.enable = True
    for s, mn in ((v.vibrationLeftConfigBean, 60), (v.vibrationRightConfigBean, 80)):
        s.enable, s.min, s.max, s.scale = True, mn, 255, 50
    mj = b.motionConfigBean.mappingTypeJoystick
    mj.sensitivity, mj.deadZone = 25, 4
    mj.enableKey.extend([12, 0])
    b.ledConfigBean.brightness = 100
    return b


def _write(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _asar(path: str, files: dict[str, bytes]):
    """Minimal Electron asar archive; file names may contain '/' for folders."""
    root, payload, offset = {"files": {}}, b"", 0
    for name, data in files.items():
        node = root
        *folders, leaf = name.split("/")
        for folder in folders:
            node = node["files"].setdefault(folder, {"files": {}})
        node["files"][leaf] = {"size": len(data), "offset": str(offset)}
        payload += data
        offset += len(data)
    js = json.dumps(root).encode()
    pad = (4 - len(js) % 4) % 4
    pickle = struct.pack("<II", 4 + len(js) + pad, len(js)) + js + b"\0" * pad
    _write(path, struct.pack("<II", 4, len(pickle)) + pickle + payload)


# Our own UI wording for the synthetic app (the plugin reads the real labels from the installed app).
UI_LABELS = {
    "en": [
        "Inactive Configs",
        "Onboard configs",
        "Apply to onboard configs",
        "Duplicate",
        "Rename",
        "Delete",
        "Share",
        "Import",
    ],
    "es": [
        "Configuraciones inactivas",
        "Configuraciones integradas",
        "Aplicar a configuraciones integradas",
        "Duplicar",
        "Cambiar nombre",
        "Eliminar",
        "Compartir",
        "Importar",
    ],
    "de": [
        "Inaktive Profile",
        "Profile im Controller",
        "Auf den Controller anwenden",
        "Duplizieren",
        "Umbenennen",
        "Löschen",
        "Teilen",
        "Importieren",
    ],
    "ja": ["未使用の設定", "本体の設定", "本体に適用", "複製", "名前の変更", "削除", "共有", "インポート"],
    "pol": [
        "Profile nieaktywne",
        "Profile w kontrolerze",
        "Zastosuj w kontrolerze",
        "Duplikuj",
        "Zmień nazwę",
        "Usuń",
        "Udostępnij",
        "Importuj",
    ],
    "pt": [
        "Perfis inativos",
        "Perfis no comando",
        "Aplicar ao comando",
        "Duplicar",
        "Renomear",
        "Excluir",
        "Compartilhar",
        "Importar",
    ],
    "zh-Hans": ["未启用的配置", "手柄内的配置", "应用到手柄", "复制", "重命名", "删除", "分享", "导入"],
    "zh-Hant": ["未啟用的設定", "手把內的設定", "套用到手把", "複製", "重新命名", "刪除", "分享", "匯入"],
}


def write_app(data: str, version: str = VERSION):
    """Synthetic resources/app.asar laid out like Space Station's: package.json, a main.js embedding the message
    format the way the app does (base64 descriptors), and per-language translation files."""
    import base64

    import schema_stub
    from flydigi import extract

    files = {"package.json": json.dumps({"version": version}).encode()}
    b64 = base64.b64encode(schema_stub.build()).decode()
    files[".vite/build/main.js"] = f'"use strict";const s=load("{b64}");'.encode()
    keys = list(extract.UI_KEYS.values())
    for lang, words in UI_LABELS.items():
        files[f".vite/build/locales/{lang}/translation.json"] = json.dumps(
            dict(zip(keys, words, strict=True)), ensure_ascii=False
        ).encode("utf-8")
    _asar(os.path.join(data, "resources", "app.asar"), files)


FACTORY_ID = {"f5": "144", "f4": "105", "k2": "84", "f3p": "80", "fp4": "132"}


def _controller(data: str, code: str):
    ctl = os.path.join(data, "Configs", "Controller", code)
    slots = schema.msg("ControllerMappingConfigBeans")()
    for i, (t, c, e, p) in enumerate(
        [
            ("Slot A", 2, 0, (65, 64)),
            ("Slot B", 5, 0, (63, 63)),
            ("Slot C", 5, 25, (67, 96)),
            ("Slot D", 12, 8, (63, 63)),
        ]
    ):
        slots.controllerMappingConfigBean.add().CopyFrom(bean(t, i, c, e, p, code))
    _write(os.path.join(ctl, "onboard", UID + code + ".dat"), slots.SerializeToString())
    factory = schema.msg("ControllerMappingConfigBeans")()
    for i in range(4):
        factory.controllerMappingConfigBean.add().CopyFrom(bean(f"Config {i + 1}", i, model=code))
    _write(os.path.join(ctl, "default", f"default_mapping_{FACTORY_ID[code]}.dat"), factory.SerializeToString())
    index = schema.msg("LocalConfigs")()
    index.deviceCode = code
    for fn, t in (("1000000000001", "Local One"), ("1000000000002", "Local Two")):
        _write(os.path.join(ctl, "local", fn + ".dat"), bean(t, 0, -10, 5, (67, 77), code).SerializeToString())
        e = index.deviceConfig.add()
        e.id, e.title, e.version, e.fileName = -1, t, 65535, fn
    _write(os.path.join(ctl, "local", "index.dat"), index.SerializeToString())


def build(root: str, version: str = VERSION, model_codes=(MODEL,)) -> str:
    data = os.path.join(root, "Space Station")
    os.makedirs(os.path.join(data, "Configs", "Controller"), exist_ok=True)
    os.environ["FLYDIGI_DATA_DIR"] = data
    os.environ["FLYDIGI_BACKUP_DIR"] = os.path.join(root, "backups")
    os.environ["FLYDIGI_EXPORT_DIR"] = os.path.join(root, "exports")
    os.environ["FLYDIGI_CACHE_DIR"] = os.path.join(root, "cache")
    write_app(data, version)  # first: the message format is read from it
    for code in model_codes:
        _controller(data, code)
    macro = schema.msg("MacroItem")()
    macro.keyId, macro.count = 32, 2
    macro.type = schema.enum_values("MacroEnableType")["MacroEnableType_Once"]
    a = macro.actions.add()
    a.keyId, a.duration = 4, 50
    a.event = schema.enum_values("MacroActionEvent")["MacroActionEvent_Press"]
    mac = os.path.join(data, "Configs", "Controller", "macro")
    _write(os.path.join(mac, "2000000000001.dat"), macro.SerializeToString())
    mi = schema.msg("LocalConfigs")()
    e = mi.deviceConfig.add()
    e.title, e.fileName = "Test macro", "2000000000001"
    _write(os.path.join(mac, "index.dat"), mi.SerializeToString())
    return data
