# /// script
# requires-python = ">=3.10"
# dependencies = ["protobuf>=5.26,<7"]
# ///
"""Live test against the real service (Space Station app must be CLOSED).
Creates a temporary LOCAL profile, edits/renames/moves it, deletes it, and checks that the local
profiles end exactly as they started. Never sends anything that writes to the controller."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
sys.stdout.reconfigure(encoding="utf-8")

from flydigi import ops, store  # noqa: E402


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


dev = store.resolve_device()
idx = os.path.join(store.controller_dir(dev.code), "local", "index.dat")
start_index = read_bytes(idx)
start_files = sorted(os.listdir(os.path.dirname(idx)))


def p(x):
    print(json.dumps(x, ensure_ascii=False, indent=1))


try:
    p(ops.create("slot:3", "ZZ Claude", {"sticks": {"left": {"deadzone_center": 3}}}, dry_run=True))
    r = ops.create(
        "slot:3",
        "ZZ Claude",
        {"sticks": {"left": {"deadzone_center": 3}}, "buttons": {"Rb": {"turbo": {"rate": 12}}}},
        dry_run=False,
    )
    p(r)
    fn = r["created"]["file_name"]
    r = ops.edit("ZZ Claude", {"triggers": {"left": {"start": 12}}}, dry_run=False)
    p(r)
    fn = r["updated"]["file_name"]
    p(ops.rename(fn, "ZZ Test"))
    p(ops.move(fn, 1))
    v = ops.load_source(f"local:{fn}")[1]
    from flydigi import profile

    view = profile.view(v)
    assert view["title"] == "ZZ Test", view["title"]
    assert view["triggers"]["left"]["start"] == 12
    assert view["sticks"]["left"]["deadzone_center"] == 3
    assert view["buttons"]["Rb"].startswith("turbo")
    print("content verified after create + edit + rename + move")

    # Export -> import round trip: the imported profile must be byte-identical apart from its name.
    import tempfile
    from flydigi import share

    os.environ["FLYDIGI_EXPORT_DIR"] = tempfile.mkdtemp(prefix="flydigi-export-")
    exported = share.export(f"local:{fn}")
    p(share.import_file(exported["file"], "ZZ Import", dry_run=True))
    imp = share.import_file(exported["file"], "ZZ Import", dry_run=False)
    p(imp)
    a = store.read_local(dev.code, fn)
    b = store.read_local(dev.code, imp["created"]["file_name"])
    a.title = b.title = ""
    a.cfgId = b.cfgId = 0
    assert a.SerializeToString() == b.SerializeToString(), "imported profile differs from the exported one"
    print("export -> import round trip is byte-identical")

    # Undo restores files behind the service's back: the service must pick up the restored list on its next
    # command (it re-reads its index), so an undone profile must not come back.
    before_undo = [e.fileName for e in store.read_local_index(dev.code).deviceConfig]
    made = ops.create("slot:3", "ZZ Undo", None, dry_run=False)["created"]["file_name"]
    p(ops.undo())
    after = [e.fileName for e in store.read_local_index(dev.code).deviceConfig]
    assert after == before_undo and made not in after, "undo did not restore the list"
    again = ops.create("slot:3", "ZZ After", None, dry_run=False)["created"]["file_name"]
    seen = [e.fileName for e in store.read_local_index(dev.code).deviceConfig]
    assert made not in seen and again in seen, "the service brought back an undone profile"
    print("undo verified: the service sees the restored list")
finally:
    for e in store.read_local_index(dev.code).deviceConfig:
        if e.title.startswith("ZZ "):
            p(ops.delete(e.fileName))

end_index = read_bytes(idx)
end_files = sorted(os.listdir(os.path.dirname(idx)))
print("same files:", start_files == end_files)
print("index.dat: start", len(start_index), "B, end", len(end_index), "B, identical:", start_index == end_index)
assert start_files == end_files and start_index == end_index, "local profiles did not end as they started"
