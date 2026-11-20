"""Readable view of a ControllerMappingConfigBean, and validated edits on a copy of it.

Edits always start from an existing, working profile (never from scratch) and only touch the
fields the user asks for. Every value is range-checked; anything unknown is rejected."""

import copy
import math

from . import schema

K = "ControllerKey_"
TARGET_KEYS = [
    "Up",
    "Right",
    "Down",
    "Left",
    "A",
    "B",
    "X",
    "Y",
    "Select",
    "Start",
    "Lb",
    "Rb",
    "Lt",
    "Rt",
    "Thl",
    "Thr",
    "Home",
]
KEY_ALIASES = {
    "LB": "Lb",
    "RB": "Rb",
    "LT": "Lt",
    "RT": "Rt",
    "L3": "Thl",
    "R3": "Thr",
    "LS": "Thl",
    "RS": "Thr",
    "BACK": "Select",
    "VIEW": "Select",
    "MENU": "Start",
    "UP": "Up",
    "DOWN": "Down",
    "LEFT": "Left",
    "RIGHT": "Right",
}
TURBO_MODES = {
    "off": "KeyMapTypeContinuousEnableType_Close",
    "press": "KeyMapTypeContinuousEnableType_Press",
    "click": "KeyMapTypeContinuousEnableType_Click",
}
MOTION_MODES = {
    "off": "MotionMapType_Off",
    "left_stick": "MotionMapType_LeftJoystick",
    "right_stick": "MotionMapType_RightJoystick",
    "mouse": "MotionMapType_Mouse",
}


class ChangeError(ValueError):
    pass


# ------------------------------------------------------------------ helpers


def _e(enum: str, number: int, prefix: str = "") -> str:
    n = schema.enum_name(enum, number)
    return n[len(prefix) :] if prefix and n.startswith(prefix) else n


def key_name(number: int) -> str:
    name = _e("ControllerKey", number, K)
    return f"Reserved{number}" if name.isdigit() else name


def key_number(name: str) -> int:
    n = str(name).strip()
    n = KEY_ALIASES.get(n.upper(), n)
    vals = schema.enum_values("ControllerKey")
    for cand in (K + n, K + n.capitalize(), n):
        if cand in vals:
            return vals[cand]
    raise ChangeError(f"Unknown button: '{name}'. Call list_options to see valid names.")


def keyboard_number(name: str) -> int:
    vals = schema.enum_values("KeyboardKey")
    n = str(name).strip()
    for cand in ("Keyboard_" + n, "Keyboard_" + n.capitalize(), "Keyboard_" + n.upper(), n):
        if cand in vals:
            return vals[cand]
    raise ChangeError(f"Unknown keyboard key: '{name}'. Call list_options to see valid names.")


def _int(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, int | float) or int(v) != v:
        raise ChangeError(f"{what}: must be a whole number (got {v!r}).")
    v = int(v)
    if not lo <= v <= hi:
        raise ChangeError(f"{what}: {v} is out of range [{lo}, {hi}].")
    return v


def _bool(v, what):
    if not isinstance(v, bool):
        raise ChangeError(f"{what}: must be true or false.")
    return v


def _point(v, what):
    if isinstance(v, dict):
        v = [v.get("x"), v.get("y")]
    if not isinstance(v, list | tuple) or len(v) != 2:
        raise ChangeError(f"{what}: use [x, y].")
    return _int(v[0], 0, 127, what + ".x"), _int(v[1], 0, 127, what + ".y")


def _unknown(d: dict, allowed: set, where: str):
    extra = set(d) - allowed
    if extra:
        raise ChangeError(f"{where}: unsupported fields {sorted(extra)}. Allowed: {sorted(allowed)}.")


# ------------------------------------------------------------------ stick curve (port of the app's F())

_PE, _IE, _ZE, _V, _CE = 127, 100, 50, 9, -50


def _jsround(v):
    return math.floor(v + 0.5)


def curve_points(center: int, edge: int, p1: tuple, p2: tuple) -> list[int]:
    """The same 9-point table Space Station computes for a custom stick curve."""
    c = (center if center > 0 else 0, -center if center < 0 else 0)
    e = (_IE - edge if edge > 0 else _IE, _IE if edge > 0 else _IE + edge)
    dx, dy = e[0] - c[0], e[1] - c[1]

    def sc(p):
        return (_jsround(c[0] + dx * (p[0] / _PE)), _jsround(c[1] + dy * (p[1] / _PE))) if p else (0, 0)

    s1, s2 = sc(p1), sc(p2)
    w = [c, s1, s2, e]

    def ev(x):
        if w[0][0] == s1[0] and w[0][1] == 0 and x == w[0][0]:
            return w[0][1]
        res = w[-1][1]
        for i in range(2 if s1[1] == 0 else 1, len(w)):
            a, b = w[i - 1], w[i]
            if x <= b[0]:
                if x == b[0] and i + 1 < len(w) and b[0] == w[i + 1][0] and b[1] < w[i + 1][1]:
                    res = w[i + 1][1]
                    break
                if a[0] == b[0]:
                    res = (a[1] if x < a[0] else b[1]) if (a[1] == 0 and b[1] != 0) else a[1]
                else:
                    res = a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
                break
        return res

    return [max(_CE, min(_IE, _jsround(ev(_IE * i / (_V - 1))))) + _ZE for i in range(_V)]


# ------------------------------------------------------------------ view


def _button_view(kb) -> str:
    t = kb.mapType
    kmt = schema.enum_values("KeyMapType")
    if t == kmt["KeyMapType_Key"]:
        if kb.mapTypeKey.HasField("mapKeyboardKeyId"):
            return "keyboard " + _e("KeyboardKey", kb.mapTypeKey.mapKeyboardKeyId, "Keyboard_")
        tgt = kb.mapTypeKey.mapControllerKeyId if kb.mapTypeKey.HasField("mapControllerKeyId") else kb.keyId
        return key_name(tgt)
    if t == kmt["KeyMapType_Continuous"]:
        c = kb.mapTypeContinuous
        mode = {v: k for k, v in TURBO_MODES.items()}.get(_e("KeyMapTypeContinuousEnableType", c.enableType), "?")
        return f"turbo {key_name(c.mapControllerKeyId)} {c.frequency}/s ({mode})"
    if t == kmt["KeyMapType_Macro"]:
        return "macro"
    if t == kmt["KeyMapType_MultiFunction"]:
        return f"multifunction {kb.mapTypeMultiFunction.mapKeyId}"
    return _e("KeyMapType", t, "KeyMapType_")


def _stick_view(js) -> dict:
    mt = _e("JoystickMapType", js.mapType, "JoystickMapType_")
    v = {"mode": mt}
    if mt == "Joystick":
        j = js.mapTypeJoystick
        sc = j.sensitivityConfig
        v.update(
            {
                "circularity": _e("JoystickCircularityType", j.circularityType, "JoystickCircularityType_"),
                "deadzone_center": j.center,
                "deadzone_edge": j.edge,
                "curve": {
                    "type": _e("JoystickSensitivityType", sc.type, "JoystickSensitivityType_"),
                    "p1": [sc.point1.x, sc.point1.y],
                    "p2": [sc.point2.x, sc.point2.y],
                    "points": list(sc.points),
                },
            }
        )
    elif mt == "Mouse":
        m = js.mapTypeMouse
        v.update({"deadzone": m.deadZone, "sensitivity_x": m.sensitivityX, "sensitivity_y": m.sensitivityY})
    elif mt == "Keyboard":
        k = js.mapTypeKeyboard
        v.update({"deadzone": k.deadZone, "keys": [_e("KeyboardKey", c.mapKeyId, "Keyboard_") for c in k.config]})
    return v


def _trigger_view(t) -> dict:
    return {
        "start": t.Zero,
        "end": t.End,
        "trigger_vibration": t.triggerVibrationConfigBean.enable,
        "travel_used": f"{round(t.Zero / 255 * 100)}% to {round(t.End / 255 * 100)}%",
    }


def _vibration_side(s) -> dict:
    return {"enabled": s.enable, "min": s.min, "max": s.max, "strength": s.scale}


# Derived, read-only summary fields: shown to the user but ignored when computing differences.
_DERIVED = {"remapped_buttons", "travel_used", "stick_settings"}


def view(bean, model=None) -> dict:
    """Readable profile. With a model, only the buttons that controller physically has are listed."""
    from . import models as _models

    vib = bean.vibrationConfigBean
    mo = bean.motionConfigBean
    mj = mo.mappingTypeJoystick
    keep = set(model.buttons) if model else None
    buttons = {}
    for kb in bean.keyConfigBeans.keyConfigBean:
        name = key_name(kb.keyId)
        if name.startswith("Reserved") or (keep is not None and name not in keep):
            continue
        buttons[name] = _button_view(kb)
    remapped = {k: v for k, v in buttons.items() if v != k}
    out = {
        "title": bean.title,
        "remapped_buttons": remapped or "none (every button does its default action)",
        "buttons": buttons,
        "stick_settings": (
            "older protocol: center deadzone only"
            if _models.old_stick_protocol(bean)
            else "deadzones and custom curve available"
        ),
        "sticks": {
            "left": _stick_view(bean.joystickConfigBean.leftJoystickParam),
            "right": _stick_view(bean.joystickConfigBean.rightJoystickParam),
        },
        "triggers": {
            "left": _trigger_view(bean.triggerConfigBean.leftTriggerConfigBean),
            "right": _trigger_view(bean.triggerConfigBean.rightTriggerConfigBean),
        },
        "vibration": {
            "enabled": vib.enable,
            "left": _vibration_side(vib.vibrationLeftConfigBean),
            "right": _vibration_side(vib.vibrationRightConfigBean),
        },
        "motion": {
            "mode": {v: k for k, v in MOTION_MODES.items()}.get(_e("MotionMapType", mo.mappingType), "?"),
            "sensitivity": mj.sensitivity,
            "deadzone": mj.deadZone,
            "activation_keys": [key_name(k) for k in mj.enableKey],
        },
        "led": {"brightness": bean.ledConfigBean.brightness, "mode": bean.ledConfigBean.ledMode},
        "macros": [
            {
                "button": key_name(m.keyId),
                "actions": len(m.actions),
                "repeat": m.count,
                "type": _e("MacroEnableType", m.type, "MacroEnableType_"),
            }
            for m in bean.macroConfigBean.Macros
        ],
    }
    return out


def diff(a: dict, b: dict, path: str = "") -> list[str]:
    out = []
    for k in sorted(set(a) | set(b), key=str):
        if k in _DERIVED:
            continue
        p = f"{path}.{k}" if path else str(k)
        x, y = a.get(k), b.get(k)
        if isinstance(x, dict) and isinstance(y, dict):
            out += diff(x, y, p)
        elif x != y and not p.endswith("curve.points"):
            out.append(f"{p}: {x} → {y}")
    return out


# ------------------------------------------------------------------ human-readable changes

BUTTON_NAMES = {
    "Lb": "LB",
    "Rb": "RB",
    "Lt": "LT",
    "Rt": "RT",
    "Thl": "L3",
    "Thr": "R3",
    "Up": "D-pad up",
    "Down": "D-pad down",
    "Left": "D-pad left",
    "Right": "D-pad right",
}
_FIELDS = {
    "deadzone_center": "center deadzone",
    "deadzone_edge": "edge deadzone",
    "circularity": "circularity",
    "mode": "mode",
    "curve.type": "response curve type",
    "curve.p1": "response curve, point 1",
    "curve.p2": "response curve, point 2",
    "deadzone": "deadzone",
    "sensitivity": "sensitivity",
    "sensitivity_x": "horizontal sensitivity",
    "sensitivity_y": "vertical sensitivity",
    "keys": "keys",
    "start": "start of travel",
    "end": "full-press point",
    "trigger_vibration": "trigger vibration",
    "enabled": "on/off",
    "min": "minimum intensity",
    "max": "maximum intensity",
    "strength": "strength",
    "activation_keys": "activation buttons",
    "brightness": "brightness",
}
_GROUPS = {"sticks": "stick", "triggers": "trigger", "vibration": "vibration motor"}


def _pretty_value(v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, str):
        for raw, nice in BUTTON_NAMES.items():
            v = " ".join(nice if w == raw else w for w in v.split(" "))
        return v.replace("(press)", "while held").replace("(click)", "toggled by a press")
    return v


def describe(path: str, before, after) -> str:
    """One change as a sentence a player understands, e.g. 'Left trigger › full-press point: 255 → 120 (…)'."""
    parts = path.split(".")
    head = parts[0]
    if head == "title":
        label = "Profile name"
    elif head == "buttons":
        label = f"Button {BUTTON_NAMES.get(parts[1], parts[1])}"
    elif head in _GROUPS and len(parts) >= 3:
        side = parts[1].capitalize()
        label = f"{side} {_GROUPS[head]} › {_FIELDS.get('.'.join(parts[2:]), '.'.join(parts[2:]))}"
    elif head == "vibration":
        label = "Vibration › master switch"
    elif head == "motion":
        label = f"Gyro › {_FIELDS.get(parts[1], parts[1])}"
    elif head == "led":
        label = f"LED › {_FIELDS.get(parts[1], parts[1])}"
    else:
        label = path
    text = f"{label}: {_pretty_value(before)} → {_pretty_value(after)}"
    if head == "triggers" and parts[-1] in ("start", "end") and isinstance(before, int) and isinstance(after, int):
        text += f" ({round(before / 255 * 100)}% → {round(after / 255 * 100)}% of travel)"
    return text


_SECTION_ORDER = ["title", "buttons", "sticks", "triggers", "vibration", "motion", "led", "macros"]
_FIELD_ORDER = [
    "mode",
    "deadzone_center",
    "deadzone_edge",
    "curve",
    "circularity",
    "start",
    "end",
    "enabled",
    "strength",
    "min",
    "max",
    "trigger_vibration",
    "sensitivity",
    "deadzone",
]


def _order(line: str):
    parts = line.partition(": ")[0].split(".")
    sec = _SECTION_ORDER.index(parts[0]) if parts[0] in _SECTION_ORDER else 99
    side = {"left": 0, "right": 1}.get(parts[1], 2) if len(parts) > 1 else 0
    field = next((i for i, f in enumerate(_FIELD_ORDER) if f in parts[1:]), 99)
    return sec, side, field, line


def _parse_value(s: str):
    if s in ("True", "False"):
        return s == "True"
    return int(s) if s.lstrip("-").isdigit() else s


def describe_changes(a: dict, b: dict) -> list[str]:
    """Readable version of diff(): every changed setting, in plain words, in a logical order."""
    out = []
    for line in sorted(diff(a, b), key=_order):
        path, _, rest = line.partition(": ")
        before, _, after = rest.partition(" → ")
        out.append(describe(path, _parse_value(before), _parse_value(after)))
    return out


# ------------------------------------------------------------------ edits


def _find_key(bean, number):
    for kb in bean.keyConfigBeans.keyConfigBean:
        if kb.keyId == number:
            return kb
    raise ChangeError(f"This profile has no {key_name(number)} button.")


def _set_button(bean, name, value, model):
    number = key_number(name)
    if key_name(number) not in model.buttons:
        raise ChangeError(
            f"The {model.name} [{model.code}] has no {key_name(number)} button. " f"Its buttons: {model.buttons}."
        )
    kb = _find_key(bean, number)
    kmt = schema.enum_values("KeyMapType")
    if kb.mapType == kmt["KeyMapType_Macro"]:
        raise ChangeError(f"{name} has a macro assigned. Change it in Space Station so the macro is not left orphaned.")
    if kb.mapType == kmt["KeyMapType_MultiFunction"]:
        raise ChangeError(f"{name} is a multifunction button. Change it in Space Station.")
    if isinstance(value, str):
        value = {"to": value}
    if not isinstance(value, dict):
        raise ChangeError(f'buttons.{name}: use "B", {{"keyboard": "Space"}} or {{"turbo": {{...}}}}.')
    _unknown(value, {"to", "keyboard", "turbo"}, f"buttons.{name}")
    if len(value) != 1:
        raise ChangeError(f"buttons.{name}: give exactly one of to / keyboard / turbo.")
    for f in ("mapTypeKey", "mapTypeContinuous", "mapTypeMacro", "mapTypeMultiFunction"):
        kb.ClearField(f)
    if "to" in value:
        tgt = value["to"]
        num = kb.keyId if str(tgt).lower() in ("self", "default", "original") else key_number(tgt)
        if key_name(num) not in TARGET_KEYS and num != kb.keyId:
            raise ChangeError(f"Cannot map to {key_name(num)}. Valid targets: {TARGET_KEYS}.")
        kb.mapType = kmt["KeyMapType_Key"]
        kb.mapTypeKey.mapControllerKeyId = num
    elif "keyboard" in value:
        kb.mapType = kmt["KeyMapType_Key"]
        kb.mapTypeKey.mapKeyboardKeyId = keyboard_number(value["keyboard"])
    else:
        t = value["turbo"]
        if not isinstance(t, dict):
            raise ChangeError(f'buttons.{name}.turbo: use {{"rate": 15, "mode": "press"}}.')
        _unknown(t, {"rate", "mode", "key"}, f"buttons.{name}.turbo")
        mode = t.get("mode", "press")
        if mode not in TURBO_MODES:
            raise ChangeError(f"turbo.mode: use one of {list(TURBO_MODES)}.")
        tgt = key_number(t["key"]) if "key" in t else kb.keyId
        kb.mapType = kmt["KeyMapType_Continuous"]
        c = kb.mapTypeContinuous
        c.mapControllerKeyId = tgt
        c.enableType = schema.enum_values("KeyMapTypeContinuousEnableType")[TURBO_MODES[mode]]
        c.frequency = _int(t.get("rate", 10), 1, 30, f"buttons.{name}.turbo.rate (presses per second)")


def _set_stick(js, side, ch, model, old_protocol):
    if not isinstance(ch, dict):
        raise ChangeError(f"sticks.{side}: must be an object.")
    _unknown(
        ch,
        {
            "deadzone_center",
            "deadzone_edge",
            "curve",
            "circularity",
            "mouse_deadzone",
            "mouse_sensitivity_x",
            "mouse_sensitivity_y",
        },
        f"sticks.{side}",
    )
    who = f"The {model.name} [{model.code}]"
    if "circularity" in ch and not model.circularity:
        raise ChangeError(f"{who} does not offer stick circularity in Space Station.")
    mt = _e("JoystickMapType", js.mapType, "JoystickMapType_")
    if {"deadzone_center", "deadzone_edge", "curve", "circularity"} & set(ch) and mt != "Joystick":
        raise ChangeError(f"The {side} stick is in {mt} mode; deadzones and the curve only apply in Joystick mode.")
    if old_protocol:
        for k in ("deadzone_edge", "curve"):
            if k in ch:
                raise ChangeError(
                    f"{who} uses Space Station's older stick settings: '{k}' is not available. "
                    "Only deadzone_center (0..40) can be changed."
                )
        if "deadzone_center" in ch:
            _int(ch["deadzone_center"], 0, 40, f"sticks.{side}.deadzone_center (this model has no anti-deadzone)")
            js.mapTypeJoystick.center = int(ch["deadzone_center"])
            ch = {k: v for k, v in ch.items() if k != "deadzone_center"}
    mt = _e("JoystickMapType", js.mapType, "JoystickMapType_")
    joy_keys = {"deadzone_center", "deadzone_edge", "curve", "circularity"} & set(ch)
    mouse_keys = {"mouse_deadzone", "mouse_sensitivity_x", "mouse_sensitivity_y"} & set(ch)
    if joy_keys and mt != "Joystick":
        raise ChangeError(f"The {side} stick is in {mt} mode; deadzones and the curve only apply in Joystick mode.")
    if mouse_keys and mt != "Mouse":
        raise ChangeError(f"The {side} stick is not in mouse mode.")
    j = js.mapTypeJoystick
    if "circularity" in ch:
        m = {
            "circular": "JoystickCircularityType_Circular",
            "rectangle": "JoystickCircularityType_Rectangle",
            "square": "JoystickCircularityType_Rectangle",
        }
        if ch["circularity"] not in m:
            raise ChangeError(f"circularity: use one of {list(m)}.")
        j.circularityType = schema.enum_values("JoystickCircularityType")[m[ch["circularity"]]]
    touched_curve = False
    if "deadzone_center" in ch:
        j.center = _int(ch["deadzone_center"], -40, 40, f"sticks.{side}.deadzone_center")
        touched_curve = True
    if "deadzone_edge" in ch:
        j.edge = _int(ch["deadzone_edge"], -40, 40, f"sticks.{side}.deadzone_edge")
        touched_curve = True
    sc = j.sensitivityConfig
    if "curve" in ch:
        cv = ch["curve"]
        if not isinstance(cv, dict):
            raise ChangeError(f'sticks.{side}.curve: use {{"p1": [x, y], "p2": [x, y]}}.')
        _unknown(cv, {"p1", "p2"}, f"sticks.{side}.curve")
        if "p1" in cv:
            sc.point1.x, sc.point1.y = _point(cv["p1"], f"sticks.{side}.curve.p1")
        if "p2" in cv:
            sc.point2.x, sc.point2.y = _point(cv["p2"], f"sticks.{side}.curve.p2")
        if sc.point1.x > sc.point2.x or sc.point1.y > sc.point2.y:
            raise ChangeError(f"sticks.{side}.curve: p1 must be below and to the left of p2.")
        touched_curve = True
    if touched_curve:
        cx, ex = max(j.center, 0), _IE - max(j.edge, 0)
        if cx >= ex - 10:
            raise ChangeError(f"sticks.{side}: the center and edge deadzones are too large together.")
        sc.type = schema.enum_values("JoystickSensitivityType")["JoystickSensitivityType_Custom"]
        pts = curve_points(j.center, j.edge, (sc.point1.x, sc.point1.y), (sc.point2.x, sc.point2.y))
        del sc.points[:]
        sc.points.extend(pts)
    m = js.mapTypeMouse
    if "mouse_deadzone" in ch:
        m.deadZone = _int(ch["mouse_deadzone"], 1, 100, f"sticks.{side}.mouse_deadzone")
    if "mouse_sensitivity_x" in ch:
        m.sensitivityX = _int(ch["mouse_sensitivity_x"], 1, 100, f"sticks.{side}.mouse_sensitivity_x")
    if "mouse_sensitivity_y" in ch:
        m.sensitivityY = _int(ch["mouse_sensitivity_y"], 1, 100, f"sticks.{side}.mouse_sensitivity_y")


def _set_trigger(t, side, ch):
    if not isinstance(ch, dict):
        raise ChangeError(f"triggers.{side}: must be an object.")
    _unknown(ch, {"start", "end", "trigger_vibration"}, f"triggers.{side}")
    if "start" in ch:
        t.Zero = _int(ch["start"], 0, 254, f"triggers.{side}.start")
    if "end" in ch:
        t.End = _int(ch["end"], 1, 255, f"triggers.{side}.end")
    if t.Zero >= t.End:
        raise ChangeError(f"triggers.{side}: start ({t.Zero}) must be lower than end ({t.End}).")
    # Same as the service's SaveTriggerConfig: the curve endpoints follow the travel.
    t.point1.x = t.point1.y = t.Zero
    t.point2.x = t.point2.y = t.End
    if "trigger_vibration" in ch:
        t.triggerVibrationConfigBean.enable = _bool(ch["trigger_vibration"], f"triggers.{side}.trigger_vibration")


def _set_vib_side(s, side, ch):
    if not isinstance(ch, dict):
        raise ChangeError(f"vibration.{side}: must be an object.")
    _unknown(ch, {"enabled", "min", "max", "strength"}, f"vibration.{side}")
    if "enabled" in ch:
        s.enable = _bool(ch["enabled"], f"vibration.{side}.enabled")
    if "min" in ch:
        s.min = _int(ch["min"], 0, 255, f"vibration.{side}.min")
    if "max" in ch:
        s.max = _int(ch["max"], 0, 255, f"vibration.{side}.max")
    if "strength" in ch:
        s.scale = _int(ch["strength"], 1, 100, f"vibration.{side}.strength (%)")
    if s.min > s.max:
        raise ChangeError(f"vibration.{side}: min ({s.min}) is greater than max ({s.max}).")


def _side(k, where):
    if k not in ("left", "right"):
        raise ChangeError(f"{where}: use left / right.")
    return k


def apply_changes(base, changes: dict, model):
    """Return a NEW bean = base + changes for the given controller model (models.Model).
    Raises ChangeError on anything invalid or not available on that model."""
    from . import models as _models

    if not isinstance(changes, dict):
        raise ChangeError("changes must be a JSON object.")
    _unknown(changes, {"title", "buttons", "sticks", "triggers", "vibration", "motion", "led"}, "changes")
    for section in ("buttons", "sticks", "triggers", "vibration", "motion", "led"):
        if section in changes and changes[section] is not None and not isinstance(changes[section], dict):
            raise ChangeError(
                f"{section}: must be an object, for example "
                + {
                    "buttons": '{"A": "B"}',
                    "sticks": '{"left": {"deadzone_center": 5}}',
                    "triggers": '{"left": {"start": 10}}',
                    "vibration": '{"enabled": false}',
                    "motion": '{"mode": "off"}',
                    "led": '{"brightness": 50}',
                }[section]
                + "."
            )
    b = copy.deepcopy(base)
    b.cfgId = 0
    if "title" in changes:
        b.title = check_title(changes["title"])
    for name, val in (changes.get("buttons") or {}).items():
        _set_button(b, name, val, model)
    old = _models.old_stick_protocol(b)
    for side, ch in (changes.get("sticks") or {}).items():
        s = _side(side, "sticks")
        _set_stick(getattr(b.joystickConfigBean, s + "JoystickParam"), side, ch, model, old)
    for side, ch in (changes.get("triggers") or {}).items():
        s = _side(side, "triggers")
        _set_trigger(getattr(b.triggerConfigBean, s + "TriggerConfigBean"), side, ch)
    if "vibration" in changes:
        v = changes["vibration"]
        if not isinstance(v, dict):
            raise ChangeError("vibration: must be an object.")
        _unknown(v, {"enabled", "left", "right"}, "vibration")
        if "enabled" in v:
            b.vibrationConfigBean.enable = _bool(v["enabled"], "vibration.enabled")
        for side in ("left", "right"):
            if side in v:
                _set_vib_side(getattr(b.vibrationConfigBean, f"vibration{side.capitalize()}ConfigBean"), side, v[side])
    if "motion" in changes:
        m = changes["motion"]
        if not isinstance(m, dict):
            raise ChangeError("motion: must be an object.")
        _unknown(m, {"mode", "sensitivity", "deadzone"}, "motion")
        mo = b.motionConfigBean
        if "mode" in m:
            if m["mode"] not in MOTION_MODES:
                raise ChangeError(f"motion.mode: use one of {list(MOTION_MODES)}.")
            mo.mappingType = schema.enum_values("MotionMapType")[MOTION_MODES[m["mode"]]]
        if "sensitivity" in m:
            mo.mappingTypeJoystick.sensitivity = _int(m["sensitivity"], 1, 100, "motion.sensitivity")
        if "deadzone" in m:
            mo.mappingTypeJoystick.deadZone = _int(m["deadzone"], 0, 50, "motion.deadzone")
    if "led" in changes:
        led = changes["led"]
        if not isinstance(led, dict):
            raise ChangeError("led: must be an object.")
        _unknown(led, {"brightness"}, "led")
        if "brightness" in led:
            b.ledConfigBean.brightness = _int(led["brightness"], 0, 100, "led.brightness")
    # Round-trip check: the result must serialize and parse back identically.
    raw = b.SerializeToString()
    if schema.parse("ControllerMappingConfigBean", raw) != b:
        raise ChangeError("Internal check failed while serializing the profile.")
    return b


def check_title(t) -> str:
    if not isinstance(t, str) or not t.strip():
        raise ChangeError("The profile name cannot be empty.")
    t = t.strip()
    if len(t) > 10:
        raise ChangeError(f"The name '{t}' has {len(t)} characters; Space Station allows 10 at most.")
    return t


def validate_bean(bean, reference) -> list[str]:
    """Check a whole profile from an untrusted source (an imported file) against a known-good profile of the
    same controller. Raises ChangeError on anything unsafe; returns non-blocking warnings."""
    problems, warnings = [], []
    if bean.protoVersion != reference.protoVersion:
        problems.append(
            f"profile format version {bean.protoVersion} differs from this controller's " f"({reference.protoVersion})"
        )
    keys = sorted(k.keyId for k in bean.keyConfigBeans.keyConfigBean)
    ref_keys = sorted(k.keyId for k in reference.keyConfigBeans.keyConfigBean)
    if keys != ref_keys:
        problems.append("the button list does not match this controller")
    kmt = schema.enum_values("KeyMapType")
    for kb in bean.keyConfigBeans.keyConfigBean:
        if kb.mapType not in kmt.values():
            problems.append(f"button {key_name(kb.keyId)}: unknown mapping type {kb.mapType}")
        if kb.mapType == kmt["KeyMapType_Continuous"] and not 1 <= kb.mapTypeContinuous.frequency <= 30:
            problems.append(f"button {key_name(kb.keyId)}: turbo rate {kb.mapTypeContinuous.frequency} not in 1..30")
    for side in ("left", "right"):
        js = getattr(bean.joystickConfigBean, side + "JoystickParam")
        j = js.mapTypeJoystick
        sc = j.sensitivityConfig
        if not -50 <= j.center <= 50 or not -50 <= j.edge <= 50:
            problems.append(f"{side} stick: deadzones {j.center}/{j.edge} outside -50..50")
        for p in (sc.point1, sc.point2):
            if not (0 <= p.x <= 127 and 0 <= p.y <= 127):
                problems.append(f"{side} stick: curve point ({p.x}, {p.y}) outside 0..127")
        if sc.points and (len(sc.points) != _V or any(not 0 <= x <= _IE + _ZE for x in sc.points)):
            problems.append(f"{side} stick: curve table is malformed")
        elif sc.points:
            expect = curve_points(j.center, j.edge, (sc.point1.x, sc.point1.y), (sc.point2.x, sc.point2.y))
            if max(abs(a - b) for a, b in zip(expect, sc.points, strict=False)) > 1:
                warnings.append(f"{side} stick: curve table does not match its curve points; it will be recomputed")
                del sc.points[:]
                sc.points.extend(expect)
        m = js.mapTypeMouse
        if js.HasField("mapTypeMouse") and not (
            0 <= m.deadZone <= 100 and -1 <= m.sensitivityX <= 100 and -1 <= m.sensitivityY <= 100
        ):
            problems.append(f"{side} stick: mouse settings out of range")
    for side in ("left", "right"):
        t = getattr(bean.triggerConfigBean, side + "TriggerConfigBean")
        if not 0 <= t.Zero < t.End <= 255:
            problems.append(f"{side} trigger: travel {t.Zero}..{t.End} is invalid")
    vib = bean.vibrationConfigBean
    for side in ("Left", "Right"):
        s = getattr(vib, f"vibration{side}ConfigBean")
        if not (0 <= s.min <= s.max <= 255 and 0 <= s.scale <= 100):
            problems.append(f"{side.lower()} vibration: values out of range")
    if not 0 <= bean.ledConfigBean.brightness <= 100:
        problems.append("LED brightness out of range")
    mj = bean.motionConfigBean.mappingTypeJoystick
    if not (0 <= mj.sensitivity <= 100 and 0 <= mj.deadZone <= 100):
        problems.append("gyro settings out of range")
    if bean.macroConfigBean.Macros:
        warnings.append(
            f"contains {len(bean.macroConfigBean.Macros)} macro(s); check them in Space Station " "before applying"
        )
    if problems:
        raise ChangeError("This profile was rejected: " + "; ".join(problems) + ".")
    return warnings


def to_share_data(bean) -> str:
    """Format the service expects in DownloadSharedLocalConfig: hex bytes joined with '-'."""
    return "-".join(f"{x:02X}" for x in bean.SerializeToString())
