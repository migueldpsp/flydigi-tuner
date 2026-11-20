"""Export profiles to a portable JSON file and import them back as LOCAL profiles.

The file is meant to be shared (GitHub, Discord, forums) without Flydigi's cloud. It holds the
readable summary for humans and the exact profile bytes for the machine, with a checksum.
Imports are validated in full before anything is created, and they only ever create a local profile."""

import base64
import hashlib
import json
import os
import re
import time

from . import compat, ipc, models, ops, profile, schema, store

FORMAT = "flydigi-tuner-profile"
FORMAT_VERSION = 1
MAX_FILE_BYTES = 256 * 1024


def default_folder() -> str:
    return os.environ.get("FLYDIGI_EXPORT_DIR") or os.path.join(
        os.path.expanduser("~"), "Documents", "Flydigi Profiles"
    )


def _safe_name(title: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")
    return s or "profile"


def export(source: str, path: str = "", device_code: str = "") -> dict:
    dev, bean, label = ops.load_source(source, device_code)
    b = schema.msg("ControllerMappingConfigBean")()
    b.CopyFrom(bean)
    b.cfgId = 0
    raw = b.SerializeToString()
    doc = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "title": b.title,
        "model": models.name(dev.code),
        "device_code": dev.code,
        "space_station_version": compat.app_version() or "unknown",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": profile.view(b, models.SUPPORTED.get(dev.code)),
        "data": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if not path:
        os.makedirs(default_folder(), exist_ok=True)
        path = os.path.join(default_folder(), f"{_safe_name(b.title)}.{dev.code}.json")
        n = 2
        while os.path.exists(path):
            path = os.path.join(default_folder(), f"{_safe_name(b.title)} ({n}).{dev.code}.json")
            n += 1
    elif not path.lower().endswith(".json"):
        raise ops.OpError("The export path must end in .json.")
    elif not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise ops.OpError(f"The folder {os.path.dirname(os.path.abspath(path))} does not exist.")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    return {"controller": models.label(dev.code), "exported": label, "file": os.path.abspath(path)}


def _load(path: str) -> tuple[dict, object]:
    if not os.path.isfile(path):
        raise ops.OpError(f"File not found: {path}")
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise ops.OpError("The file is too large to be a profile.")
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (ValueError, UnicodeDecodeError):
        raise ops.OpError("The file is not valid JSON.") from None
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ops.OpError("This is not a Flydigi Station profile file.")
    if doc.get("format_version") != FORMAT_VERSION:
        raise ops.OpError(f"Unsupported file version {doc.get('format_version')}; update the plugin.")
    try:
        raw = base64.b64decode(doc["data"], validate=True)
    except (KeyError, ValueError, TypeError):
        raise ops.OpError("The profile data in the file is missing or corrupted.") from None
    if hashlib.sha256(raw).hexdigest() != doc.get("sha256"):
        raise ops.OpError("Checksum mismatch: the file was modified or corrupted.")
    try:
        bean = schema.parse("ControllerMappingConfigBean", raw)
    except Exception:
        raise ops.OpError("The profile data cannot be decoded.") from None
    if compat._has_unknown_fields(bean):
        raise ops.OpError("The profile contains fields this plugin does not know (newer format?).")
    return doc, bean


def import_file(path: str, title: str = "", dry_run: bool = True, device_code: str = "") -> dict:
    doc, bean = _load(path)
    dev = store.resolve_device(device_code)
    if doc.get("device_code") != dev.code:
        raise ops.OpError(
            f"This profile is for the {models.label(str(doc.get('device_code')))}, but your controller is the "
            f"{models.label(dev.code)}. "
            "Profiles cannot be moved between controller models."
        )
    models.get(dev.code)  # unsupported models are read-only
    _, reference, ref_label = ops.load_source("slot:1" if dev.uids else f"factory:{dev.factory_ids[0]}", dev.code)
    warnings = profile.validate_bean(bean, reference)
    bean.cfgId = 0
    bean.title = profile.check_title(title or bean.title or "Imported")
    res = {
        "controller": models.label(dev.code),
        "file": os.path.abspath(path),
        "title": bean.title,
        "from_space_station": doc.get("space_station_version"),
        "compared_with": ref_label,
        "differences": profile.describe_changes(
            profile.view(reference, models.SUPPORTED.get(dev.code)), profile.view(bean, models.SUPPORTED.get(dev.code))
        )
        or ["(identical)"],
    }
    if warnings:
        res["warnings"] = warnings
    if dry_run:
        res["dry_run"] = "Validated; nothing was created. Run again with dry_run=false to create the local profile."
        return res
    warn = compat.ensure_writable(dev.code)
    bk = store.backup("import")
    with ipc.Client() as cli:
        fn = ops._import(cli, dev, bean)
    res.update({"created": {"title": bean.title, "file_name": fn}, "backup": bk, "next_step": ops.NEXT_STEP})
    if warn:
        res["warning"] = warn
    return res
