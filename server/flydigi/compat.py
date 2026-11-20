"""Compatibility checks against the installed Space Station.

Three signals:
- version: the app version read from its package.json (inside resources/app.asar);
- format: the installed app's message format must contain every message, field and enum value the plugin uses
  (required.py), with the same types;
- files: the profile files on disk must not contain fields the format does not know.
A format or file problem blocks writes until the plugin is updated; an untested version only adds a warning."""

import json
import os
import struct

from . import store

TESTED_VERSIONS = ("4.2.3.1",)


class SchemaDrift(RuntimeError):
    pass


def app_version() -> str | None:
    """Space Station version from package.json inside resources/app.asar, or None if unreadable."""
    path = os.path.join(store.data_dir(), "resources", "app.asar")
    try:
        with open(path, "rb") as f:
            _, header_size = struct.unpack("<II", f.read(8))
            _, str_len = struct.unpack("<II", f.read(8))
            header = json.loads(f.read(str_len).decode("utf-8"))
            ent = header["files"]["package.json"]
            f.seek(8 + header_size + int(ent["offset"]))
            return json.loads(f.read(ent["size"]).decode("utf-8")).get("version")
    except (OSError, KeyError, ValueError, struct.error):
        return None


# Fields present in genuine Space Station 4.2.3.1 files (factory ones included) that the app's own schema does not
# declare. They are preserved untouched when profiles are copied; only fields outside this list signal a change.
KNOWN_EXTRA_FIELDS = {("MacroConfigBean", 4)}


def unknown_fields(msg) -> set[tuple[str, int]]:
    """(message type, field number) of every field the schema does not know, anywhere in msg."""
    from google.protobuf.unknown_fields import UnknownFieldSet

    out = {(msg.DESCRIPTOR.name, f.field_number) for f in UnknownFieldSet(msg)}
    for fd, val in msg.ListFields():
        if fd.message_type is not None:
            for sub in val if fd.is_repeated else [val]:
                out |= unknown_fields(sub)
    return out


def _has_unknown_fields(msg) -> bool:
    return bool(unknown_fields(msg) - KNOWN_EXTRA_FIELDS)


def format_problems() -> list[str]:
    """Everything the plugin relies on (required.py) that the installed app's message format lacks or changed."""
    from google.protobuf import descriptor_pb2

    from . import extract, required, schema

    try:
        fd = schema._file()
    except (extract.ExtractError, OSError, ValueError) as e:
        return [f"Space Station's message format could not be read: {e}"]
    types = {v: k[5:].lower() for k, v in descriptor_pb2.FieldDescriptorProto.Type.items()}
    messages = {m.name: m for m in fd.message_type}
    enums = {e.name: {v.name for v in e.value} for e in fd.enum_type}
    problems = []
    for mname, fields in required.MESSAGES.items():
        m = messages.get(mname)
        if m is None:
            problems.append(f"message {mname} is missing")
            continue
        have = {f.name: f for f in m.field}
        for fname, want in fields.items():
            f = have.get(fname)
            if f is None:
                problems.append(f"{mname}.{fname} is missing")
                continue
            got = ("repeated " if f.label == 3 else "") + (f.type_name.split(".")[-1] if f.type_name else types[f.type])
            if got != want:
                problems.append(f"{mname}.{fname} changed type ({want} -> {got})")
    for ename, values in required.ENUM_VALUES.items():
        missing = sorted(set(values) - enums.get(ename, set()))
        if missing:
            problems.append(f"{ename} lacks {', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}")
    return problems


def schema_problems(device_code: str = "") -> list[str]:
    """Format problems, plus files whose content does not match the format (unknown fields or unreadable)."""
    problems = format_problems()
    if problems:
        return problems
    dev = store.resolve_device(device_code)
    checks = []
    if dev.uids:
        checks.append((f"onboard copy {dev.uids[0]}", lambda: store.read_onboard(dev.code, dev.uids[0])))
    for e in store.read_local_index(dev.code).deviceConfig:
        checks.append((f"local profile '{e.title}'", lambda fn=e.fileName: store.read_local(dev.code, fn)))
    if dev.factory_ids:
        checks.append(
            (f"factory profile {dev.factory_ids[0]}", lambda: store.read_factory(dev.code, dev.factory_ids[0]))
        )
    for label, read in checks:
        try:
            if _has_unknown_fields(read()):
                problems.append(f"{label}: contains fields this plugin does not know")
        except Exception as e:  # unreadable = the format changed
            problems.append(f"{label}: cannot be read ({type(e).__name__})")
    return problems


def report(device_code: str = "") -> dict:
    v = app_version()
    try:
        problems = schema_problems(device_code)
    except LookupError:  # Space Station installed but no controller registered yet: only the format can be checked
        problems = format_problems()
    out = {
        "space_station_version": v or "unknown",
        "tested_versions": list(TESTED_VERSIONS),
        "version_tested": v in TESTED_VERSIONS,
        "schema_ok": not problems,
    }
    if problems:
        out["schema_problems"] = problems
        out["warning"] = (
            "Space Station's profile format changed. Writes are blocked until the plugin is "
            "updated; reading still works."
        )
    elif v not in TESTED_VERSIONS:
        out["warning"] = (
            f"Space Station {v or '(unknown version)'} has not been tested with this plugin. "
            "The profile format still matches, so writes are allowed; review results in the app."
        )
    return out


def ensure_writable(device_code: str = "") -> str | None:
    """Raise SchemaDrift if writing is unsafe; return a warning string if the version is untested."""
    problems = schema_problems(device_code)
    if problems:
        raise SchemaDrift(
            "Writes are blocked: Space Station's profile format changed ("
            + "; ".join(problems)
            + "). Update the plugin."
        )
    v = app_version()
    if v not in TESTED_VERSIONS:
        return f"Space Station {v or '(unknown version)'} is untested with this plugin; review the result in the app."
    return None
