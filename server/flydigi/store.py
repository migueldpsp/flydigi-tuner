"""Read-only access to the profile files Space Station keeps on disk, plus backups.

Nothing here talks to the controller. The only writes in this module go to the backup folder,
or restore a backup (Space Station's own PC-side files, never the controller)."""

import os
import shutil
import time
from dataclasses import dataclass

from . import models, schema

DEFAULT_DATA_DIR = r"C:\Program Files\Flydigi Space Station"


def backup_root() -> str:
    return os.environ.get("FLYDIGI_BACKUP_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "flydigi-tuner", "backups"
    )


def data_dir() -> str:
    d = os.environ.get("FLYDIGI_DATA_DIR", DEFAULT_DATA_DIR)
    if not os.path.isdir(os.path.join(d, "Configs", "Controller")):
        raise FileNotFoundError(
            f"Space Station data not found in '{d}'. "
            "If Space Station is installed somewhere else, set the FLYDIGI_DATA_DIR environment variable."
        )
    return d


def controller_dir(device_code: str = "") -> str:
    base = os.path.join(data_dir(), "Configs", "Controller")
    return os.path.join(base, device_code) if device_code else base


@dataclass
class Device:
    code: str
    uids: list
    onboard_updated: str
    local_count: int
    factory_ids: list


def _mtime(p: str) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p)))


def devices() -> list[Device]:
    """Controller models that have onboard copies or local profiles on this PC."""
    out = []
    base = controller_dir()
    for code in sorted(os.listdir(base)):
        d = os.path.join(base, code)
        if not os.path.isdir(d) or code in ("macro", "Trigger"):
            continue
        onboard = os.path.join(d, "onboard")
        uids = [f[:-4] for f in os.listdir(onboard) if f.endswith(".dat")] if os.path.isdir(onboard) else []
        local_n = (
            len(read_local_index(code).deviceConfig) if os.path.exists(os.path.join(d, "local", "index.dat")) else 0
        )
        if not uids and not local_n:
            continue
        fdir = os.path.join(d, "default")
        fids = (
            sorted(f[len("default_mapping_") : -4] for f in os.listdir(fdir) if f.startswith("default_mapping_"))
            if os.path.isdir(fdir)
            else []
        )
        upd = max((_mtime(os.path.join(onboard, u + ".dat")) for u in uids), default="")
        out.append(Device(code, uids, upd, local_n, fids))
    return out


def resolve_device(device_code: str = "") -> Device:
    devs = devices()
    if not devs:
        raise LookupError("No controller is registered in Space Station on this PC.")
    if device_code:
        for d in devs:
            if d.code == device_code:
                return d
        raise LookupError(
            f"No data for {models.label(device_code)} on this PC. Available: " f"{[models.label(d.code) for d in devs]}"
        )
    if len(devs) > 1:
        raise LookupError(
            f"Several controllers have data on this PC: {[models.label(d.code) for d in devs]}. "
            "Ask the user which one and pass its code as device_code."
        )
    return devs[0]


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def read_onboard(code: str, uid: str):
    """Copy of the 4 onboard slots as Space Station last saw them (ControllerMappingConfigBeans)."""
    return schema.parse(
        "ControllerMappingConfigBeans", _read(os.path.join(controller_dir(code), "onboard", uid + ".dat"))
    )


def onboard_updated(code: str, uid: str) -> str:
    return _mtime(os.path.join(controller_dir(code), "onboard", uid + ".dat"))


STALE_DAYS = 14


def onboard_age_days(code: str, uid: str) -> int:
    return int((time.time() - os.path.getmtime(os.path.join(controller_dir(code), "onboard", uid + ".dat"))) // 86400)


def stale_note(code: str, uid: str) -> str | None:
    age = onboard_age_days(code, uid)
    if age < STALE_DAYS:
        return None
    return (
        f"The copy of the controller's slots is {age} days old. If the controller was changed since then, "
        "connect it and open Space Station once so the copy is refreshed before using a slot as the base."
    )


def read_local_index(code: str):
    p = os.path.join(controller_dir(code), "local", "index.dat")
    if not os.path.exists(p):
        return schema.msg("LocalConfigs")()
    return schema.parse("LocalConfigs", _read(p))


def read_local(code: str, file_name: str):
    return schema.parse(
        "ControllerMappingConfigBean", _read(os.path.join(controller_dir(code), "local", file_name + ".dat"))
    )


def read_factory(code: str, factory_id: str):
    return schema.parse(
        "ControllerMappingConfigBeans",
        _read(os.path.join(controller_dir(code), "default", f"default_mapping_{factory_id}.dat")),
    )


def read_macro_index():
    p = os.path.join(controller_dir("macro"), "index.dat")
    if not os.path.exists(p):
        return []
    return list(schema.parse("LocalConfigs", _read(p)).deviceConfig)


def read_macro(file_name: str):
    return schema.parse("MacroItem", _read(os.path.join(controller_dir("macro"), file_name + ".dat")))


# ---------------------------------------------------------------- backups


def backup(reason: str) -> str:
    """Copy every PC-side local profile folder and the macro library before a change."""
    now = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{int(now * 1000) % 1000:03d}"
    dest = os.path.join(backup_root(), f"{stamp}_{reason}")
    n = 1
    while os.path.exists(dest):  # several changes within the same millisecond
        n += 1
        dest = os.path.join(backup_root(), f"{stamp}-{n}_{reason}")
    base = controller_dir()
    for code in os.listdir(base):
        src = os.path.join(base, code, "local")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, code, "local"))
    mac = os.path.join(base, "macro")
    if os.path.isdir(mac):
        shutil.copytree(mac, os.path.join(dest, "macro"))
    os.makedirs(dest, exist_ok=True)
    _prune_backups()
    return dest


MAX_BACKUPS = 50


def _prune_backups():
    """Keep only the newest MAX_BACKUPS backups (folder names sort by time)."""
    for old in list_backups()[MAX_BACKUPS:]:
        shutil.rmtree(os.path.join(backup_root(), old), ignore_errors=True)


def list_backups() -> list[str]:
    if not os.path.isdir(backup_root()):
        return []
    return sorted(os.listdir(backup_root()), reverse=True)


UNDONE = "_undone"
SAFETY = "before-restore"


def describe_backup(name: str) -> dict:
    """{'name', 'taken_at', 'taken_before', 'undone'} from a backup folder name like 20261116-172347-123_create."""
    stamp, _, reason = name.partition("_")
    undone = reason.endswith(UNDONE)
    reason = reason[: -len(UNDONE)] if undone else reason
    try:
        taken = time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(stamp[:15], "%Y%m%d-%H%M%S"))
    except ValueError:
        taken = stamp
    what = {
        "create": "creating a profile",
        "edit": "editing a profile",
        "rename": "renaming a profile",
        "reorder": "reordering profiles",
        "delete": "deleting a profile",
        "import": "importing a profile",
        SAFETY: "restoring a backup",
    }.get(reason, reason)
    return {"name": name, "taken_at": taken, "taken_before": what, "undone": undone}


def undo_candidates() -> list[str]:
    """Backups that undo the most recent changes, newest first (safety copies and used ones excluded)."""
    return [b for b in list_backups() if not b.endswith(UNDONE) and not b.endswith("_" + SAFETY)]


def restore_backup(name: str) -> tuple[list[str], str]:
    """Restore a backup. Returns (what was restored, name of the safety backup of the state just replaced)."""
    src = os.path.join(backup_root(), name)
    if not name or not os.path.isdir(src) or os.path.dirname(os.path.abspath(src)) != os.path.abspath(backup_root()):
        raise LookupError(f"Backup '{name}' does not exist.")
    safety = os.path.basename(backup(SAFETY))
    restored = []
    base = controller_dir()
    for entry in os.listdir(src):
        if entry == "macro":
            target = os.path.join(base, "macro")
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(os.path.join(src, "macro"), target)
            restored.append("macro")
            continue
        local_src = os.path.join(src, entry, "local")
        if os.path.isdir(local_src):
            target = os.path.join(base, entry, "local")
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(local_src, target)
            restored.append(f"{entry}/local")
    return restored, safety


def mark_undone(name: str):
    """Mark a backup as used by undo, so the next undo goes one step further back."""
    src = os.path.join(backup_root(), name)
    if os.path.isdir(src) and not name.endswith(UNDONE):
        os.rename(src, src + UNDONE)
