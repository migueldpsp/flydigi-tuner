"""Read Space Station's message format and UI labels from the user's own installation.

Nothing from Space Station is shipped with this plugin. On first use (and again whenever Space Station is
updated) this module reads resources/app.asar of the installed app, which holds the app's JavaScript in plain
form, and takes from it:
- the protobuf descriptors the app's UI and service use to talk to each other;
- a few UI labels in every language the app ships, so Claude can quote them exactly.

The result is cached per Space Station version under %LOCALAPPDATA%/flydigi-tuner/cache."""

import base64
import json
import os
import re
import struct

from google.protobuf import descriptor_pb2

from . import store

# Plugin name -> Space Station translation key.
UI_KEYS = {
    "inactive_configs": "local_config",
    "onboard_configs": "onboard_config",
    "apply_to_onboard": "apply_to_onboard",
    "duplicate": "copy",
    "rename": "rename",
    "delete": "delete",
    "share": "share",
    "import": "import",
}
_DESCRIPTOR = re.compile(r'\w+\("(C[A-Za-z0-9+/=]{100,})"')


class ExtractError(RuntimeError):
    pass


def _cache_root() -> str:
    return os.environ.get("FLYDIGI_CACHE_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "flydigi-tuner", "cache"
    )


def asar_path() -> str:
    return os.path.join(store.data_dir(), "resources", "app.asar")


class _Asar:
    """Minimal reader for Electron's asar archive (a JSON header followed by the files)."""

    def __init__(self, path: str):
        try:
            self._fh = open(path, "rb")  # noqa: SIM115 (closed in close())
            _, header_size = struct.unpack("<II", self._fh.read(8))
            _, str_len = struct.unpack("<II", self._fh.read(8))
            self._header = json.loads(self._fh.read(str_len).decode("utf-8"))
            self._base = 8 + header_size
        except (OSError, ValueError, struct.error) as e:
            raise ExtractError(f"Cannot read Space Station's app files ({path}): {e}") from None

    def _entry(self, path: str):
        node = self._header
        for part in path.split("/"):
            node = node.get("files", {}).get(part)
            if node is None:
                return None
        return node

    def read(self, path: str) -> bytes | None:
        ent = self._entry(path)
        if not ent or "offset" not in ent:
            return None
        self._fh.seek(self._base + int(ent["offset"]))
        return self._fh.read(ent["size"])

    def list(self, path: str) -> list[str]:
        ent = self._entry(path)
        return sorted((ent or {}).get("files", {}))

    def close(self):
        self._fh.close()


def _find(d, key):
    if isinstance(d, dict):
        if isinstance(d.get(key), str):
            return d[key]
        for v in d.values():
            r = _find(v, key)
            if r:
                return r
    return None


def _extract(asar: _Asar) -> tuple[bytes, dict, str]:
    pkg = asar.read("package.json")
    version = json.loads(pkg.decode("utf-8")).get("version", "unknown") if pkg else "unknown"
    main_js = asar.read(".vite/build/main.js")
    if not main_js:
        raise ExtractError("Space Station's main program was not found inside app.asar. Is the app installed?")
    merged = descriptor_pb2.FileDescriptorProto(name="space_station.proto", syntax="proto3")
    seen = set()
    for m in _DESCRIPTOR.finditer(main_js.decode("utf-8", errors="replace")):
        b64 = m.group(1)
        try:
            fd = descriptor_pb2.FileDescriptorProto.FromString(base64.b64decode(b64 + "=" * (-len(b64) % 4)))
        except Exception:
            continue
        if not fd.name.endswith(".proto") or fd.name in seen:
            continue
        seen.add(fd.name)
        merged.package = fd.package
        merged.message_type.extend(fd.message_type)
        merged.enum_type.extend(fd.enum_type)
    if not merged.message_type:
        raise ExtractError("Space Station's message format was not found in this version of the app.")
    labels = {}
    for lang in asar.list(".vite/build/locales"):
        raw = asar.read(f".vite/build/locales/{lang}/translation.json")
        if raw:
            tr = json.loads(raw.decode("utf-8"))
            found = {name: _find(tr, key) for name, key in UI_KEYS.items()}
            if all(found.values()):
                labels[lang] = found
    if "en" not in labels:
        raise ExtractError("Space Station's English UI labels were not found in this version of the app.")
    return merged.SerializeToString(), labels, version


def _load():
    path = asar_path()
    st = os.stat(path)
    key = f"{int(st.st_mtime)}-{st.st_size}"
    folder = os.path.join(_cache_root(), key)
    schema_file, labels_file = os.path.join(folder, "schema.pb"), os.path.join(folder, "ui_labels.json")
    if os.path.exists(schema_file) and os.path.exists(labels_file):
        with open(schema_file, "rb") as fh:
            schema = fh.read()
        with open(labels_file, encoding="utf-8") as fh:
            data = json.load(fh)
        return schema, data["labels"], data["version"]
    asar = _Asar(path)
    try:
        schema, labels, version = _extract(asar)
    finally:
        asar.close()
    os.makedirs(folder, exist_ok=True)
    with open(schema_file, "wb") as fh:
        fh.write(schema)
    with open(labels_file, "w", encoding="utf-8") as fh:
        json.dump({"version": version, "labels": labels}, fh, ensure_ascii=False, indent=1)
    return schema, labels, version


_memo: dict = {}


def schema_bytes() -> bytes:
    """Serialized FileDescriptorProto. FLYDIGI_SCHEMA_FILE overrides it (used by tests without Space Station)."""
    override = os.environ.get("FLYDIGI_SCHEMA_FILE")
    if override:
        with open(override, "rb") as fh:
            return fh.read()
    if "data" not in _memo:
        _memo["data"] = _load()
    return _memo["data"][0]


def ui_labels() -> dict:
    if "data" not in _memo:
        _memo["data"] = _load()
    return _memo["data"][1]
