"""High-level operations. Reads use files; writes only create/rename/reorder/delete LOCAL profiles
through the service's own commands. Nothing here can write to the controller."""

from . import compat, ipc, models, profile, schema, store


class OpError(RuntimeError):
    pass


NEXT_STEP = (
    "Open Space Station, find the profile under 'Inactive Configs', review it and, if you want, "
    "use 'Apply to onboard configs' to put it on a controller slot."
)


# ------------------------------------------------------------------ resolving sources


def _local_entries(code):
    return list(store.read_local_index(code).deviceConfig)


def _read_local_titled(code, entry):
    """The service renames in index.dat only (and uses that name when applying), so the index title wins."""
    b = store.read_local(code, entry.fileName)
    b.title = entry.title
    return b


def find_local(code: str, ref: str):
    """ref = file_name, exact title, or 1-based position in the list."""
    ents = _local_entries(code)
    ref = str(ref).strip()
    for e in ents:
        if e.fileName == ref:
            return e
    by_title = [e for e in ents if e.title == ref]
    if len(by_title) == 1:
        return by_title[0]
    if len(by_title) > 1:
        raise OpError(
            f"There are {len(by_title)} local profiles named '{ref}'. Use the file_name instead: "
            f"{[e.fileName for e in by_title]}"
        )
    if ref.isdigit() and 1 <= int(ref) <= len(ents):
        return ents[int(ref) - 1]
    raise OpError(f"Local profile '{ref}' not found. Local profiles: {[e.title for e in ents]}")


def _number(text: str, what: str) -> int:
    t = str(text).strip()
    if not t.isdigit():
        raise OpError(f"{what} must be a number, got '{t}'. Example: 'slot:1'.")
    return int(t)


# Slots are numbered 1-4, exactly as Space Station shows them (it stores them as 0-3 internally).
def load_source(source: str, device_code: str = ""):
    """Return (device, bean, label). source: slot:1-4 | local:<name> | factory:<id>[:slot 1-4]."""
    dev = store.resolve_device(device_code)
    kind, _, rest = str(source).partition(":")
    kind = kind.strip().lower()
    if kind in ("slot", "onboard"):
        if not dev.uids:
            raise OpError(
                "No copy of the controller's slots on this PC. Connect the controller and open Space Station once."
            )
        n = _number(rest, "The slot")
        beans = store.read_onboard(dev.code, dev.uids[0]).controllerMappingConfigBean
        for b in beans:
            if b.cfgId + 1 == n:
                upd = store.onboard_updated(dev.code, dev.uids[0])
                return dev, b, f"controller slot {n} '{b.title}' (copy saved by Space Station on {upd})"
        raise OpError(
            f"There is no slot {n}. Slots are numbered {min(b.cfgId for b in beans) + 1}-"
            f"{max(b.cfgId for b in beans) + 1}, as in Space Station."
        )
    if kind == "local":
        e = find_local(dev.code, rest)
        return dev, _read_local_titled(dev.code, e), f"local profile '{e.title}' ({e.fileName})"
    if kind in ("factory", "default"):
        fid, _, slot = rest.partition(":")
        fid = fid or (dev.factory_ids[0] if dev.factory_ids else "")
        if fid not in dev.factory_ids:
            raise OpError(f"Factory profile '{fid}' is not available. Available: {dev.factory_ids}")
        beans = store.read_factory(dev.code, fid).controllerMappingConfigBean
        i = _number(slot or "1", "The factory slot")
        if not 1 <= i <= len(beans):
            raise OpError(f"Factory profile {fid} has slots 1-{len(beans)}; there is no slot {i}.")
        return dev, beans[i - 1], f"factory profile {fid}, slot {i}"
    raise OpError("Invalid source. Use 'slot:N', 'local:<name>' or 'factory:<id>'.")


# ------------------------------------------------------------------ overview


def overview(device_code: str = "") -> dict:
    out = []
    for d in store.devices():
        if device_code and d.code != device_code:
            continue
        slots = []
        if d.uids:
            for b in store.read_onboard(d.code, d.uids[0]).controllerMappingConfigBean:
                slots.append({"slot": b.cfgId + 1, "title": b.title})
        locs = [
            {"position": i + 1, "title": e.title, "file_name": e.fileName} for i, e in enumerate(_local_entries(d.code))
        ]
        out.append(
            {
                "model": models.name(d.code),
                "device_code": d.code,
                "support": models.support_level(d.code),
                "model_notes": list(models.SUPPORTED[d.code].notes) if d.code in models.SUPPORTED else [],
                "uid": d.uids[0] if d.uids else None,
                "controller_slots_read_only": slots,
                "slots_copy_updated": d.onboard_updated,
                **({"slots_copy_note": n} if d.uids and (n := store.stale_note(d.code, d.uids[0])) else {}),
                "local_profiles_editable": locs,
                "factory_profiles": d.factory_ids,
            }
        )
    return {"controllers": out}


# ------------------------------------------------------------------ writes (local only)


def _uid(dev):
    return dev.uids[0] if dev.uids else ""


def _import(cli, dev, bean) -> str:
    before = {e.fileName for e in _local_entries(dev.code)}
    r = cli.call(
        "IpcCommandEnum_DownloadSharedLocalConfig",
        {
            "downloadSharedLocalConfigParam": {
                "deviceCode": dev.code,
                "uid": _uid(dev),
                "data": profile.to_share_data(bean),
                "title": bean.title,
            }
        },
    )
    if not r.state:
        raise OpError("The service rejected the profile. Nothing was created.")
    new = [e.fileName for e in _local_entries(dev.code) if e.fileName not in before]
    if len(new) != 1:
        raise OpError("The service reported success, but no new profile appeared. Check Space Station.")
    # Verify that what landed on disk is exactly what we built.
    if store.read_local(dev.code, new[0]).SerializeToString() != bean.SerializeToString():
        raise OpError(f"The saved profile ({new[0]}) does not match the prepared one. Check it in Space Station.")
    return new[0]


def _sort(cli, dev, file_name, position0):
    r = cli.call(
        "IpcCommandEnum_UpdateLocalConfigSort",
        {
            "updateLocalConfigSortParam": {
                "deviceCode": dev.code,
                "uid": _uid(dev),
                "fileName": file_name,
                "newSort": position0,
            }
        },
    )
    if not r.state:
        raise OpError("Could not change the order.")


def _delete(cli, dev, file_name):
    r = cli.call(
        "IpcCommandEnum_DeleteLocalConfig",
        {"deleteLocalConfigParam": {"deviceCode": dev.code, "uid": _uid(dev), "fileName": file_name}},
    )
    if not r.state:
        raise OpError("The service could not delete the profile.")


def create(source: str, title: str, changes: dict | None, dry_run: bool, device_code: str = "") -> dict:
    dev, base, label = load_source(source, device_code)
    ch = dict(changes or {})
    ch["title"] = title
    model = models.get(dev.code)
    new = profile.apply_changes(base, ch, model)
    d = profile.describe_changes(
        profile.view(base, models.SUPPORTED.get(dev.code)), profile.view(new, models.SUPPORTED.get(dev.code))
    )
    res = {"controller": models.label(dev.code), "base": label, "changes": d or ["(none: exact copy)"]}
    if str(source).lower().startswith(("slot", "onboard")) and (note := store.stale_note(dev.code, dev.uids[0])):
        res["base_note"] = note
    if dry_run:
        res["dry_run"] = "Nothing was created. Run again with dry_run=false to create the local profile."
        return res
    warn = compat.ensure_writable(dev.code)
    bk = store.backup("create")
    with ipc.Client() as cli:
        fn = _import(cli, dev, new)
    res.update({"created": {"title": new.title, "file_name": fn}, "backup": bk, "next_step": NEXT_STEP})
    if warn:
        res["warning"] = warn
    return res


def edit(ref: str, changes: dict, dry_run: bool, device_code: str = "") -> dict:
    dev = store.resolve_device(device_code)
    e = find_local(dev.code, ref)
    base = _read_local_titled(dev.code, e)
    new = profile.apply_changes(base, changes, models.get(dev.code))
    d = profile.describe_changes(
        profile.view(base, models.SUPPORTED.get(dev.code)), profile.view(new, models.SUPPORTED.get(dev.code))
    )
    res = {"controller": models.label(dev.code), "profile": f"'{e.title}' ({e.fileName})", "changes": d or ["(none)"]}
    if dry_run or not d:
        res["dry_run"] = "Nothing was changed." + (" Run again with dry_run=false to apply it." if d else "")
        return res
    pos = [x.fileName for x in _local_entries(dev.code)].index(e.fileName)
    warn = compat.ensure_writable(dev.code)
    bk = store.backup("edit")
    with ipc.Client() as cli:
        fn = _import(cli, dev, new)  # 1) the new version exists first
        _delete(cli, dev, e.fileName)  # 2) only then does the old one go
        _sort(cli, dev, fn, pos)  # 3) same place in the list
    res.update({"updated": {"title": new.title, "file_name": fn}, "backup": bk, "next_step": NEXT_STEP})
    if warn:
        res["warning"] = warn
    return res


def duplicate(ref: str, title: str, device_code: str = "") -> dict:
    return create(
        f"local:{find_local(store.resolve_device(device_code).code, ref).fileName}", title, None, False, device_code
    )


def rename(ref: str, title: str, device_code: str = "") -> dict:
    dev = store.resolve_device(device_code)
    e = find_local(dev.code, ref)
    t = profile.check_title(title)
    compat.ensure_writable(dev.code)
    bk = store.backup("rename")
    with ipc.Client() as cli:
        r = cli.call(
            "IpcCommandEnum_UpdateLocalConfigName",
            {
                "updateLocalConfigNameParam": {
                    "deviceCode": dev.code,
                    "uid": _uid(dev),
                    "fileName": e.fileName,
                    "newTitle": t,
                }
            },
        )
    if not r.state:
        raise OpError("The service could not rename the profile.")
    return {"renamed": f"'{e.title}' → '{t}'", "backup": bk}


def move(ref: str, position: int, device_code: str = "") -> dict:
    dev = store.resolve_device(device_code)
    ents = _local_entries(dev.code)
    e = find_local(dev.code, ref)
    if not 1 <= position <= len(ents):
        raise OpError(f"Position out of range (1-{len(ents)}).")
    compat.ensure_writable(dev.code)
    bk = store.backup("reorder")
    with ipc.Client() as cli:
        _sort(cli, dev, e.fileName, position - 1)
    return {
        "moved": f"'{e.title}' to position {position}",
        "current_order": [x.title for x in _local_entries(dev.code)],
        "backup": bk,
    }


def delete(ref: str, device_code: str = "") -> dict:
    dev = store.resolve_device(device_code)
    e = find_local(dev.code, ref)
    compat.ensure_writable(dev.code)
    bk = store.backup("delete")
    with ipc.Client() as cli:
        _delete(cli, dev, e.fileName)
    return {
        "deleted": f"'{e.title}' ({e.fileName})",
        "backup": bk,
        "note": "It can be recovered with restore_backup while Space Station is closed.",
    }


def restore(name: str) -> dict:
    if ipc.app_running():
        raise OpError("Close Space Station before restoring a backup.")
    restored, safety = store.restore_backup(name)
    return {
        "restored": store.describe_backup(name),
        "folders": restored,
        "to_go_back": f"restore_backup('{safety}') returns to the state just replaced.",
    }


def undo() -> dict:
    """Undo the most recent change to local profiles (repeat to go further back)."""
    if ipc.app_running():
        raise OpError("Close Space Station before undoing a change.")
    candidates = store.undo_candidates()
    if not candidates:
        raise OpError("There is nothing to undo: no backup of an earlier change was found.")
    name = candidates[0]
    restored, safety = store.restore_backup(name)
    store.mark_undone(name)
    info = store.describe_backup(name)
    return {
        "undone": f"the change made after {info['taken_at']} ({info['taken_before']})",
        "folders": restored,
        "redo": f"restore_backup('{safety}') brings that change back.",
        "remaining_undo_steps": len(store.undo_candidates()),
        "next_step": "Reopen Space Station to see the local profiles as they were.",
    }


def backups() -> dict:
    return {"folder": store.backup_root(), "backups": [store.describe_backup(b) for b in store.list_backups()]}


def macros() -> list:
    out = []
    for e in store.read_macro_index():
        try:
            m = store.read_macro(e.fileName)
            acts = [
                f"{profile.key_name(a.keyId)} {profile._e('MacroActionEvent', a.event, 'MacroActionEvent_')}"
                f" {a.duration}ms"
                for a in m.actions
            ]
            out.append(
                {
                    "title": e.title,
                    "file_name": e.fileName,
                    "repeat": m.count,
                    "type": profile._e("MacroEnableType", m.type, "MacroEnableType_"),
                    "actions": acts,
                }
            )
        except Exception as ex:  # unreadable entry: report it, don't fail the whole list
            out.append({"title": e.title, "file_name": e.fileName, "error": str(ex)})
    return out


def options(device_code: str = "") -> dict:
    dev = store.resolve_device(device_code)
    model = models.get(dev.code)
    try:
        _, b, _ = load_source("slot:1" if dev.uids else f"factory:{dev.factory_ids[0]}", dev.code)
        old = models.old_stick_protocol(b)
    except Exception:
        old = False
    kb = [k[len("Keyboard_") :] for k in schema.enum_values("KeyboardKey") if k.startswith("Keyboard_")]
    if old:
        sticks = {
            "deadzone_center": "0..40 (this model has no anti-deadzone)",
            "deadzone_edge": "not available on this model",
            "curve": "not available on this model",
        }
    else:
        sticks = {
            "deadzone_center": "-40..40 (negative = anti-deadzone)",
            "deadzone_edge": "-40..40",
            "curve": "p1/p2 = [x, y] in 0..127, p1 <= p2",
        }
    sticks["circularity"] = ["circular", "rectangle"] if model.circularity else "not available on this model"
    sticks["mouse_*"] = "1..100 (only when the stick is in mouse mode)"
    return {
        "controller": models.label(dev.code),
        "support": models.support_level(dev.code),
        "model_notes": list(model.notes),
        "buttons_you_can_remap": model.buttons,
        "button_targets": profile.TARGET_KEYS,
        "aliases": profile.KEY_ALIASES,
        "keyboard_keys": kb,
        "turbo": {"rate": "1-30 presses per second", "mode": list(profile.TURBO_MODES)},
        "sticks": sticks,
        "triggers": {"start": "0..254", "end": "1..255 (start < end)", "trigger_vibration": "true/false"},
        "vibration": {
            "enabled": "true/false",
            "left/right": {"enabled": "bool", "min": "0..255", "max": "0..255", "strength": "1..100 %"},
        },
        "motion": {"mode": list(profile.MOTION_MODES), "sensitivity": "1..100", "deadzone": "0..50"},
        "led": {"brightness": "0..100"},
    }
