# /// script
# requires-python = ">=3.10"
# dependencies = ["protobuf>=5.26,<7"]
# ///
"""Read-only checks against the REAL Space Station install on this PC (skipped if there is none).
Confirms the plugin's assumptions still hold for the user's data. Writes nothing.
Run: uv run --script tests/test_real_data.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
sys.stdout.reconfigure(encoding="utf-8")

from flydigi import compat, ops, profile, store  # noqa: E402

try:
    dev = store.resolve_device()
except (FileNotFoundError, LookupError) as e:
    print("SKIPPED:", e)
    sys.exit(0)

passed = 0


def check(cond, msg):
    global passed
    if not cond:
        raise AssertionError(msg)
    passed += 1


rep = compat.report()
print(
    "Space Station", rep["space_station_version"], "| tested:", rep["version_tested"], "| schema ok:", rep["schema_ok"]
)
check(rep["schema_ok"], f"schema problems: {rep.get('schema_problems')}")

beans = list(store.read_onboard(dev.code, dev.uids[0]).controllerMappingConfigBean) if dev.uids else []
beans += [store.read_local(dev.code, e.fileName) for e in store.read_local_index(dev.code).deviceConfig]
check(beans, "no profiles found")

# Stick curves: the plugin's formula reproduces what the app stored (the app itself drifts by up to 1).
exact = close = 0
for b in beans:
    for js in (b.joystickConfigBean.leftJoystickParam, b.joystickConfigBean.rightJoystickParam):
        j, sc = js.mapTypeJoystick, js.mapTypeJoystick.sensitivityConfig
        if not sc.points:
            continue
        got = profile.curve_points(j.center, j.edge, (sc.point1.x, sc.point1.y), (sc.point2.x, sc.point2.y))
        worst = max(abs(x - y) for x, y in zip(got, sc.points, strict=False))
        check(worst <= 1, f"curve mismatch in '{b.title}': {got} vs {list(sc.points)}")
        exact += worst == 0
        close += worst == 1
print(f"stick curves: {exact} exact, {close} within ±1")

# Trigger rule the plugin copies from the service: point1 = (start, start), point2 = (end, end).
for b in beans:
    for t in (b.triggerConfigBean.leftTriggerConfigBean, b.triggerConfigBean.rightTriggerConfigBean):
        check(
            (t.point1.x, t.point1.y, t.point2.x, t.point2.y) == (t.Zero, t.Zero, t.End, t.End),
            f"trigger rule broken in '{b.title}'",
        )

# Every real profile passes the import validator (no false rejections).
_, ref, _ = ops.load_source("slot:1" if dev.uids else f"factory:{dev.factory_ids[0]}")
for b in beans:
    profile.validate_bean(b, ref)
    passed += 1

# Views work on everything.
for b in beans:
    profile.view(b)
    passed += 1

# Real factory profiles that Space Station ships for every supported model (they are on disk even without
# owning the controller): read, validate and edit them with each model's rules, without writing anything.
from flydigi import models  # noqa: E402

typical = {
    "buttons": {"A": "B", "M1": "X", "M2": "Rb"},
    "triggers": {"left": {"start": 10, "end": 120}},
    "vibration": {"enabled": False},
    "led": {"brightness": 30},
}
for code, model in models.SUPPORTED.items():
    fdir = os.path.join(store.controller_dir(code), "default")
    if not os.path.isdir(fdir):
        print(f"  {models.label(code)}: no factory files, skipped")
        continue
    ids = sorted(f[len("default_mapping_") : -4] for f in os.listdir(fdir) if f.startswith("default_mapping_"))
    for fid in ids:
        slots = list(store.read_factory(code, fid).controllerMappingConfigBean)
        check(len(slots) == 4, f"{code} {fid}: 4 slots")
        check(not compat._has_unknown_fields(slots[0]), f"{code} {fid}: format known")
        for b in slots:
            profile.view(b)
            profile.validate_bean(b, slots[0])
        old = models.old_stick_protocol(slots[0])
        sticks = (
            {"left": {"deadzone_center": 8}}
            if old
            else {"left": {"deadzone_center": -3, "deadzone_edge": 10, "curve": {"p1": [60, 70]}}}
        )
        new = profile.apply_changes(slots[0], {**typical, "sticks": sticks}, model)
        profile.validate_bean(new, slots[0])
        passed += 1
    print(
        f"  {models.label(code)}: {len(ids)} factory profiles OK "
        f"(format {slots[0].protoVersion}, {'older' if old else 'current'} stick protocol)"
    )

print(f"OK: {passed} checks on {len(beans)} real profiles ({models.label(dev.code)}) and the factory profiles")
