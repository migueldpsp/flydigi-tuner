# /// script
# requires-python = ">=3.10"
# dependencies = ["protobuf>=5.26,<7"]
# ///
"""Offline tests on SYNTHETIC data (tests/fixtures.py): no Space Station needed, nothing outside a temp folder
is touched. This is what CI runs. Run: uv run --script tests/test_offline.py"""

import base64
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

from flydigi import compat, ipc, models, ops, profile, schema, share, store, ui  # noqa: E402
import fixtures  # noqa: E402


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


TMP = tempfile.mkdtemp(prefix="flydigi-test-")
fixtures.build(TMP)
passed = 0
F5 = models.get("f5")


def check(cond, msg):
    global passed
    if not cond:
        raise AssertionError(msg)
    passed += 1


def rejects(fn, needle, label):
    try:
        fn()
    except (profile.ChangeError, ops.OpError, compat.SchemaDrift, LookupError) as e:
        check(needle.lower() in str(e).lower(), f"{label}: unexpected message: {e}")
        return
    raise AssertionError(f"{label}: should have been rejected")


# 1. Stick curve: values produced by Space Station itself for two real curves.
check(profile.curve_points(-10, 5, (67, 77), (127, 127)) == [60, 74, 88, 101, 115, 125, 134, 144, 150], "curve 1")
check(profile.curve_points(2, 0, (64, 63), (127, 127)) == [48, 61, 73, 86, 99, 112, 124, 137, 150], "curve 2")

# 2. Reading
ov = ops.overview()["controllers"][0]
check(ov["device_code"] == "f5" and len(ov["controller_slots_read_only"]) == 4, "overview slots")
check([p["title"] for p in ov["local_profiles_editable"]] == ["Local One", "Local Two"], "overview locals")
_, b0, label = ops.load_source("slot:1")
v = profile.view(b0)
check(v["title"] == "Slot A" and v["buttons"]["A"] == "A", "view")
check(not any(k.isdigit() for k in v["buttons"]), "button names are never bare numbers")
check(ops.find_local("f5", "2").title == "Local Two", "find by position")
check(len(ops.macros()) == 1 and ops.macros()[0]["actions"], "macro library")
for bad, msg in (
    ("slot:9", "there is no slot 9"),
    ("cloud:1", "invalid source"),
    ("local:Nope", "not found"),
    ("factory:999", "not available"),
):
    rejects(lambda b=bad: ops.load_source(b), msg, bad)

# 3. Valid changes produce the expected diff and leave the base untouched
before = b0.SerializeToString()
new = profile.apply_changes(
    b0,
    {
        "title": "Test",
        "buttons": {"A": "B", "RB": {"turbo": {"rate": 15}}, "M1": {"keyboard": "Space"}},
        "sticks": {"left": {"deadzone_center": -5, "curve": {"p1": [60, 60]}}},
        "triggers": {"left": {"start": 10, "end": 120}},
        "vibration": {"enabled": False, "left": {"strength": 40}},
        "motion": {"mode": "right_stick", "sensitivity": 30},
        "led": {"brightness": 20},
    },
    F5,
)
check(b0.SerializeToString() == before, "base must not change")
d = profile.diff(profile.view(b0), profile.view(new))
for want in (
    "buttons.A: A → B",
    "buttons.Rb: Rb → turbo Rb 15/s (press)",
    "buttons.M1: M1 → keyboard Space",
    "sticks.left.deadzone_center: 2 → -5",
    "triggers.left.end: 255 → 120",
    "vibration.enabled: True → False",
    "motion.mode: off → right_stick",
    "led.brightness: 100 → 20",
    "title: Slot A → Test",
):
    check(want in d, f"diff should contain {want!r}; got {d}")
j = new.joystickConfigBean.leftJoystickParam.mapTypeJoystick
check(list(j.sensitivityConfig.points) == profile.curve_points(-5, 0, (60, 60), (127, 127)), "curve recomputed")
t = new.triggerConfigBean.leftTriggerConfigBean
check((t.point1.x, t.point1.y, t.point2.x, t.point2.y) == (10, 10, 120, 120), "trigger points follow travel")
check(new.cfgId == 0, "cfgId reset")

# 4. Invalid changes are rejected with a clear message
for change, msg in [
    ({"title": "WayTooLongProfileName"}, "10 at most"),
    ({"title": "  "}, "cannot be empty"),
    ({"buttons": {"A": "M1"}}, "cannot map to m1"),
    ({"buttons": {"Q": "A"}}, "unknown button"),
    ({"buttons": {"A": {"keyboard": "NotAKey"}}}, "unknown keyboard key"),
    ({"buttons": {"RB": {"turbo": {"rate": 99}}}}, "out of range"),
    ({"buttons": {"A": {"to": "B", "turbo": {}}}}, "exactly one"),
    ({"sticks": {"left": {"deadzone_center": 90}}}, "out of range"),
    ({"sticks": {"left": {"curve": {"p1": [120, 120], "p2": [10, 10]}}}}, "below and to the left"),
    ({"sticks": {"middle": {}}}, "left / right"),
    ({"sticks": {"left": {"mouse_deadzone": 5}}}, "not in mouse mode"),
    ({"triggers": {"left": {"start": 250, "end": 100}}}, "must be lower"),
    ({"vibration": {"left": {"strength": 0}}}, "out of range"),
    ({"vibration": {"left": {"min": 200, "max": 100}}}, "greater than"),
    ({"motion": {"mode": "fly"}}, "motion.mode"),
    ({"led": {"color": "red"}}, "unsupported"),
    ({"firmware": {}}, "unsupported"),
    ({"sticks": {"left": {"deadzone_center": True}}}, "whole number"),
]:
    rejects(lambda c=change: profile.apply_changes(b0, c, F5), msg, json.dumps(change))

# 5. Dry runs never write
locals_before = [e.fileName for e in store.read_local_index("f5").deviceConfig]
r = ops.create("slot:3", "Dry", {"sticks": {"left": {"deadzone_center": 3}}}, dry_run=True)
check("dry_run" in r and "created" not in r, "dry run create")
r = ops.edit("Local One", {"led": {"brightness": 5}}, dry_run=True)
check("dry_run" in r, "dry run edit")
check([e.fileName for e in store.read_local_index("f5").deviceConfig] == locals_before, "dry runs wrote nothing")

# 6. Safety: commands that write to the controller can never be sent
c = ipc.Client.__new__(ipc.Client)
for cmd in sorted(ipc.FORBIDDEN):
    try:
        c.call(cmd, {})
        raise AssertionError("not blocked: " + cmd)
    except PermissionError:
        passed += 1
check(not (ipc.ALLOWED & ipc.FORBIDDEN), "allow/forbid lists are disjoint")

# 7. Share format round-trips
data = profile.to_share_data(new)
check(bytes(int(x, 16) for x in data.split("-")) == new.SerializeToString(), "share format")

# 8. Backups: unique names even within the same millisecond, and pruning
b1, b2 = store.backup("selftest"), store.backup("selftest")
check(b1 != b2 and os.path.isdir(b1) and os.path.isdir(b2), "two quick backups must not collide")
for _ in range(store.MAX_BACKUPS + 5):
    store.backup("prune")
check(len(store.list_backups()) == store.MAX_BACKUPS, "backups are pruned")

# 9. Compatibility: version, untested version, schema drift
rep = compat.report()
check(rep["space_station_version"] == "4.2.3.1" and rep["version_tested"] and rep["schema_ok"], f"compat {rep}")
check(compat.ensure_writable() is None, "tested version writes without warning")
fixtures.write_app(os.environ["FLYDIGI_DATA_DIR"], "9.9.9")
check(not compat.report()["version_tested"] and "warning" in compat.report(), "untested version is reported")
check("untested" in (compat.ensure_writable() or ""), "untested version warns but allows writes")
local_one = os.path.join(store.controller_dir("f5"), "local", "1000000000001.dat")
original = read_bytes(local_one)
with open(local_one, "ab") as fh:
    fh.write(b"\xf8\x3e\x01")  # field 999 (varint): a field this schema does not know
check(not compat.report()["schema_ok"], "schema drift detected")
rejects(compat.ensure_writable, "writes are blocked", "drift blocks writes")
rejects(lambda: ops.rename("Local One", "X"), "writes are blocked", "drift blocks rename")
with open(local_one, "wb") as fh:
    # The extra field genuine files carry (macroConfigBean field 4) must be tolerated and preserved.
    fh.write(original + b"\x62\x02\x20\x01")
check(compat.report()["schema_ok"], "known extra field is tolerated")
_, known_extra, _ = ops.load_source("local:Local One")
copy_ = profile.apply_changes(known_extra, {"led": {"brightness": 7}}, F5)
check(compat.unknown_fields(copy_) == compat.KNOWN_EXTRA_FIELDS, "known extra field survives an edit")
with open(local_one, "wb") as fh:
    fh.write(original)
fixtures.write_app(os.environ["FLYDIGI_DATA_DIR"])
check(compat.report()["schema_ok"], "drift cleared")


# 9b. The installed app's format must contain everything the plugin uses (read from the app, not shipped)
def reload_app(**stub_args):
    import schema_stub  # noqa: F401  (tests/ is on sys.path)

    from flydigi import extract

    extract._memo.clear()
    for f in (schema._file, schema.pool, schema.msg, schema.enum_values):
        f.cache_clear()
    if stub_args:
        import base64

        import schema_stub as stub

        data = os.environ["FLYDIGI_DATA_DIR"]
        files = {"package.json": b'{"version": "4.2.3.1"}'}
        files[".vite/build/main.js"] = f'x("{base64.b64encode(stub.build(**stub_args)).decode()}")'.encode()
        for lang, words in fixtures.UI_LABELS.items():
            files[f".vite/build/locales/{lang}/translation.json"] = json.dumps(
                dict(zip(extract.UI_KEYS.values(), words, strict=True)), ensure_ascii=False
            ).encode()
        fixtures._asar(os.path.join(data, "resources", "app.asar"), files)
    else:
        fixtures.write_app(os.environ["FLYDIGI_DATA_DIR"])


check(compat.format_problems() == [], "full format: no problems")
reload_app(drop=(("KeyConfigBean", "keyId"), ("TriggerConfigBean", "Zero")))
problems = compat.format_problems()
check(
    "KeyConfigBean.keyId is missing" in problems and "TriggerConfigBean.Zero is missing" in problems,
    f"missing fields reported: {problems}",
)
check(not compat.report()["schema_ok"], "a format missing fields is not ok")
rejects(compat.ensure_writable, "writes are blocked", "missing fields block writes")
reload_app()
check(compat.format_problems() == [] and compat.report()["schema_ok"], "format restored")

# 10. Export / import
ex = share.export("slot:3")
path = ex["file"]
doc = json.loads(read_bytes(path).decode("utf-8"))
check(doc["format"] == share.FORMAT and doc["device_code"] == "f5" and doc["summary"]["title"] == "Slot C", "export")
check(path.endswith(".f5.json") and share.export("slot:3")["file"] != path, "export never overwrites")
r = share.import_file(path, "Shared", dry_run=True)
check(r["title"] == "Shared" and "dry_run" in r and "differences" in r, f"import dry run {r}")
rejects(lambda: share.export("slot:1", os.path.join(TMP, "x.txt")), "must end in .json", "export path")


def write_doc(name, mutate):
    d2 = json.loads(read_bytes(path).decode("utf-8"))
    mutate(d2)
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d2, fh)
    return p


def crafted(edit_bean):
    """A file with a valid checksum whose profile values were tampered with."""

    def m(d2):
        b = schema.parse("ControllerMappingConfigBean", base64.b64decode(d2["data"]))
        edit_bean(b)
        raw = b.SerializeToString()
        d2["data"] = base64.b64encode(raw).decode()
        import hashlib

        d2["sha256"] = hashlib.sha256(raw).hexdigest()

    return m


bad_files = [
    (write_doc("sum.json", lambda d2: d2.update(sha256="0" * 64)), "checksum"),
    (write_doc("model.json", lambda d2: d2.update(device_code="k2")), "the apex 4 [k2]"),
    (write_doc("fmt.json", lambda d2: d2.update(format="other")), "not a flydigi station profile"),
    (write_doc("ver.json", lambda d2: d2.update(format_version=2)), "unsupported file version"),
    (write_doc("b64.json", lambda d2: d2.update(data="!!!")), "missing or corrupted"),
    (
        write_doc(
            "stick.json",
            crafted(lambda b: setattr(b.joystickConfigBean.leftJoystickParam.mapTypeJoystick, "center", 120)),
        ),
        "deadzones",
    ),
    (
        write_doc("trig.json", crafted(lambda b: setattr(b.triggerConfigBean.leftTriggerConfigBean, "Zero", 255))),
        "travel",
    ),
    (write_doc("keys.json", crafted(lambda b: b.keyConfigBeans.keyConfigBean.pop())), "button list"),
    (write_doc("proto.json", crafted(lambda b: setattr(b, "protoVersion", 999))), "format version"),
    (
        write_doc(
            "turbo.json",
            crafted(
                lambda b: (
                    setattr(b.keyConfigBeans.keyConfigBean[4], "mapType", 1),
                    setattr(b.keyConfigBeans.keyConfigBean[4].mapTypeContinuous, "frequency", 200),
                )
            ),
        ),
        "turbo rate",
    ),
]
notjson = os.path.join(TMP, "notjson.json")
write_text(notjson, "hello")
bad_files.append((notjson, "not valid json"))
big = os.path.join(TMP, "big.json")
write_text(big, " " * (share.MAX_FILE_BYTES + 1))
bad_files.append((big, "too large"))
bad_files.append((os.path.join(TMP, "missing.json"), "not found"))
for p, msg in bad_files:
    rejects(lambda p=p: share.import_file(p, dry_run=True), msg, os.path.basename(p))

stale = write_doc(
    "stale.json",
    crafted(
        lambda b: b.joystickConfigBean.leftJoystickParam.mapTypeJoystick.sensitivityConfig.points.__setitem__(4, 10)
    ),
)
r = share.import_file(stale, dry_run=True)
check(any("recomputed" in w for w in r.get("warnings", [])), "stale curve table is repaired with a warning")

# 11a. Clear output in any language: readable change lines, and Space Station's own UI names per language
lines = profile.describe_changes(profile.view(b0), profile.view(new))
for want in (
    "Profile name: Slot A → Test",
    "Button A: A → B",
    "Button RB: RB → turbo RB 15/s while held",
    "Left stick › center deadzone: 2 → -5",
    "Left trigger › start of travel: 0 → 10 (0% → 4% of travel)",
    "Left trigger › full-press point: 255 → 120 (100% → 47% of travel)",
    "Vibration › master switch: on → off",
    "Gyro › mode: off → right_stick",
    "LED › brightness: 100 → 20",
):
    check(want in lines, f"readable change {want!r} missing from {lines}")
check(
    lines[0].startswith("Profile name")
    and lines.index("Left trigger › start of travel: 0 → 10 (0% → 4% of travel)")
    < lines.index("Left trigger › full-press point: 255 → 120 (100% → 47% of travel)"),
    "logical order",
)
check(not any("deadzone_center" in x or "triggers." in x for x in lines), "no technical paths in readable lines")
check(ui.languages() == sorted(fixtures.UI_LABELS), f"UI languages read from the app: {ui.languages()}")
for code, want in (
    ("es", "es"),
    ("es-MX", "es"),
    ("ES_es", "es"),
    ("pt-BR", "pt"),
    ("pl", "pol"),
    ("zh-TW", "zh-Hant"),
    ("zh", "zh-Hans"),
    ("ja", "ja"),
    ("", "en"),
    ("sv", "en"),
):
    check(ui.resolve(code) == want, f"language {code!r} -> {ui.resolve(code)!r}, expected {want!r}")
check(
    ui.labels("es")["labels"]["duplicate"] == "Duplicar"
    and ui.labels("es")["labels"]["inactive_configs"] == "Configuraciones inactivas",
    "Spanish labels are the app's own",
)
check(ui.labels("en")["labels"]["apply_to_onboard"] == "Apply to onboard configs", "English labels")
check("note" in ui.labels("sv") and "note" not in ui.labels("es"), "missing language explained")
for lang in ui.languages():
    check(all(ui.labels(lang)["labels"].values()), f"{lang}: every label present")

# 11b. Undo: each backup is the state before a change; undo walks back one change at a time
import shutil  # noqa: E402

shutil.rmtree(store.backup_root(), ignore_errors=True)
local_dir = os.path.join(store.controller_dir("f5"), "local")
index_path = os.path.join(local_dir, "index.dat")
state0 = read_bytes(index_path)
rejects(ops.undo, "nothing to undo", "undo with no backups")


def simulate_change(reason, title):
    store.backup(reason)  # what every real write does first
    idx = store.read_local_index("f5")
    idx.deviceConfig[0].title = title
    with open(index_path, "wb") as fh:
        fh.write(idx.SerializeToString())
    return read_bytes(index_path)


state1 = simulate_change("rename", "Step One")
state2 = simulate_change("rename", "Step Two")
r = ops.undo()
check(read_bytes(index_path) == state1 and "renaming a profile" in r["undone"], f"first undo {r}")
check(r["remaining_undo_steps"] == 1 and "restore_backup(" in r["redo"], "undo reports redo and remaining steps")
r = ops.undo()
check(read_bytes(index_path) == state0, "second undo goes one more step back")
rejects(ops.undo, "nothing to undo", "no more undo steps")
redo = r["redo"].split("'")[1]
ops.restore(redo)
check(read_bytes(index_path) == state1, "redo through restore_backup")
desc = ops.backups()["backups"]
check(all({"name", "taken_at", "taken_before", "undone"} <= set(d) for d in desc), "readable backup list")
check(any(d["undone"] for d in desc) and any(d["taken_before"] == "restoring a backup" for d in desc), "backup labels")
with open(index_path, "wb") as fh:
    fh.write(state0)

# 11c. A stale copy of the controller's slots is flagged
import time  # noqa: E402

ov_now = ops.overview()["controllers"][0]
check("slots_copy_note" not in ov_now, "fresh copy: no note")
onboard_file = os.path.join(store.controller_dir("f5"), "onboard", fixtures.UID + "f5.dat")
old_time = time.time() - 30 * 86400
os.utime(onboard_file, (old_time, old_time))
check("30 days old" in ops.overview()["controllers"][0].get("slots_copy_note", ""), "stale copy noted in overview")
check("base_note" in ops.create("slot:1", "Stale", None, True), "stale copy noted when used as a base")
check("base_note" not in ops.create("local:Local One", "Stale", None, True), "no note for local bases")
os.utime(onboard_file, None)

# 11. Several models on one PC: VADER 5 Pro, VADER 4 Pro, APEX 4, VADER 3 Pro, plus an unsupported Direwolf 4
TMP2 = tempfile.mkdtemp(prefix="flydigi-models-")
fixtures.build(TMP2, model_codes=("f5", "f4", "k2", "f3p", "fp4"))
ov = {c["device_code"]: c for c in ops.overview()["controllers"]}
check(
    {c: ov[c]["model"] for c in ov}
    == {"f5": "VADER 5 Pro", "f4": "VADER 4 Pro", "k2": "APEX 4", "f3p": "VADER 3 Pro", "fp4": "Direwolf 4"},
    f"model names {ov.keys()}",
)
check(
    "tested on a physical controller" in ov["f5"]["support"]
    and "not yet tested" in ov["f4"]["support"]
    and "read-only" in ov["fp4"]["support"],
    "support levels",
)
rejects(lambda: ops.load_source("slot:1"), "ask the user which one", "several controllers need an explicit model")
check(models.label("f4") == "VADER 4 Pro [f4]", "unambiguous label")

for code in ("f5", "f4", "k2", "f3p"):
    m = models.get(code)
    opts = ops.options(code)
    check(opts["controller"] == models.label(code) and opts["buttons_you_can_remap"] == m.buttons, f"{code} options")
    r = ops.create(
        "slot:1",
        "Dry",
        {"buttons": {"A": "B", "M1": "X"}, "triggers": {"left": {"end": 200}}},
        dry_run=True,
        device_code=code,
    )
    check(r["controller"] == models.label(code) and "Button M1: M1 → X" in r["changes"], f"{code} dry run")
    ex = share.export("slot:2", device_code=code)
    check(
        share.import_file(ex["file"], "Again", dry_run=True, device_code=code)["controller"] == models.label(code),
        f"{code} export/import",
    )
    for other in ("f5", "f4", "k2", "f3p"):
        if other != code:
            rejects(
                lambda: share.import_file(ex["file"], dry_run=True, device_code=other),
                "cannot be moved between controller models",
                f"{code} file into {other}",
            )

_, b4, _ = ops.load_source("slot:1", "f4")
rejects(lambda: profile.apply_changes(b4, {"buttons": {"M5": "A"}}, models.get("f4")), "has no M5", "VADER 4 Pro M5")
profile.apply_changes(b4, {"buttons": {"C": "A"}, "sticks": {"left": {"circularity": "rectangle"}}}, models.get("f4"))
passed += 1

_, bk2, _ = ops.load_source("slot:1", "k2")
rejects(lambda: profile.apply_changes(bk2, {"buttons": {"C": "A"}}, models.get("k2")), "has no C", "APEX 4 C")
rejects(
    lambda: profile.apply_changes(bk2, {"sticks": {"left": {"circularity": "circular"}}}, models.get("k2")),
    "circularity",
    "APEX 4 circularity",
)
rejects(
    lambda: profile.apply_changes(bk2, {"sticks": {"left": {"curve": {"p1": [40, 70]}}}}, models.get("k2")),
    "not available",
    "APEX 4 (older protocol) has no custom curve",
)
wukong = schema.msg("ControllerMappingConfigBean")()
wukong.CopyFrom(bk2)
wukong.protoVersion = 769  # the Black Myth WuKong edition uses the current stick protocol
ok_k2 = profile.apply_changes(
    wukong, {"sticks": {"left": {"deadzone_center": -5, "curve": {"p1": [40, 70]}}}}, models.get("k2")
)
check(
    len(ok_k2.joystickConfigBean.leftJoystickParam.mapTypeJoystick.sensitivityConfig.points) == 9,
    "APEX 4 WuKong edition: custom curve works",
)

_, b3, _ = ops.load_source("slot:1", "f3p")
m3 = models.get("f3p")
check(models.old_stick_protocol(b3), "VADER 3 Pro uses the older stick protocol")
for change, msg in [
    ({"sticks": {"left": {"deadzone_edge": 5}}}, "not available"),
    ({"sticks": {"left": {"curve": {"p1": [60, 60]}}}}, "not available"),
    ({"sticks": {"left": {"deadzone_center": -5}}}, "no anti-deadzone"),
    ({"sticks": {"left": {"circularity": "circular"}}}, "circularity"),
    ({"buttons": {"M6": "A"}}, "has no M6"),
]:
    rejects(lambda c=change: profile.apply_changes(b3, c, m3), msg, f"VADER 3 Pro {change}")
ok3 = profile.apply_changes(b3, {"sticks": {"left": {"deadzone_center": 10}}, "buttons": {"C": "A"}}, m3)
j3 = ok3.joystickConfigBean.leftJoystickParam.mapTypeJoystick
check(j3.center == 10 and not j3.sensitivityConfig.points, "VADER 3 Pro deadzone changes without a curve table")
check(ops.options("f3p")["sticks"]["deadzone_edge"] == "not available on this model", "VADER 3 Pro options")

# Model-aware view: only the buttons each controller physically has, remapped ones highlighted, no noise.
for code in ("f5", "f4", "k2", "f3p"):
    m = models.get(code)
    _, base_b, _ = ops.load_source("slot:1", code)
    vw = profile.view(base_b, m)
    check(list(vw["buttons"]) == [b for b in vw["buttons"] if b in m.buttons], f"{code}: only physical buttons")
    check(set(vw["buttons"]) == set(m.buttons), f"{code}: every physical button listed")
    check(not any(b.startswith("Reserved") for b in vw["buttons"]), f"{code}: no reserved slots")
check("M5" not in profile.view(b4, models.get("f4"))["buttons"], "VADER 4 Pro view has no M5")
check("C" not in profile.view(bk2, models.get("k2"))["buttons"], "APEX 4 view has no C")
check(profile.view(b3, m3)["stick_settings"].startswith("older protocol"), "VADER 3 Pro view explains its sticks")
remap = profile.apply_changes(b4, {"buttons": {"A": "B", "M1": "X"}}, models.get("f4"))
rv = profile.view(remap, models.get("f4"))
check(rv["remapped_buttons"] == {"A": "B", "M1": "X"}, f"remapped summary {rv['remapped_buttons']}")
check(str(profile.view(b4, models.get("f4"))["remapped_buttons"]).startswith("none"), "no remaps explained")
check(rv["triggers"]["left"]["travel_used"] == "0% to 100%", "trigger travel in percent")
check(
    profile.describe_changes(profile.view(b4, models.get("f4")), rv) == ["Button A: A → B", "Button M1: M1 → X"],
    "derived summary fields never appear as changes",
)

check("Direwolf 4" in json.dumps(ops.overview()), "unsupported model is listed")
ops.load_source("slot:1", "fp4")
passed += 1
rejects(lambda: ops.create("slot:1", "X", None, True, "fp4"), "can be read but not edited", "Direwolf 4 create")
rejects(lambda: ops.options("fp4"), "can be read but not edited", "Direwolf 4 options")

print(f"OK: {passed} checks (synthetic data in {TMP} and {TMP2})")
