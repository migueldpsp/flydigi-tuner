# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.9,<2", "protobuf>=5.26,<7"]
# ///
"""Flydigi Space Station MCP server.

Prepares LOCAL profiles (stored on the PC) for Flydigi controllers. It never writes to the
controller: the 4 onboard slots are read-only here, and moving a profile to the controller is
something the user does in Space Station ("Apply to onboard")."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from flydigi import compat, ipc, models, ops, profile, share, store, ui  # noqa: E402

mcp = FastMCP(
    "flydigi-tuner",
    instructions=(
        "Flydigi Space Station helper. It only creates and edits LOCAL profiles on the PC. "
        "The controller's 4 onboard slots are read-only here: never suggest that this server writes to the "
        "controller. The user reviews local profiles in Space Station and applies them to a slot themselves. "
        "Write tools need the Space Station app closed. Always run a write with dry_run=true first and show the diff. "
        "Always identify the controller by its commercial name and code as returned by status (for example "
        "'VADER 4 Pro [f4]'); never guess the model, ask the user when several controllers are listed, and only offer "
        "the buttons and settings list_options reports for that model. "
        "Reply in the user's language and translate tool output, but quote Space Station's own button and section "
        "names exactly as status(language=...) returns them in space_station_ui instead of translating them."
    ),
)


def _out(fn, *a, **kw) -> str:
    try:
        return json.dumps(fn(*a, **kw), ensure_ascii=False, indent=1)
    except (
        profile.ChangeError,
        ops.OpError,
        ipc.ServiceBusy,
        compat.SchemaDrift,
        LookupError,
        FileNotFoundError,
        PermissionError,
        TimeoutError,
        ConnectionError,
    ) as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:  # safety net: never surface a raw stack trace to the user
        import traceback

        traceback.print_exc(file=sys.stderr)
        return json.dumps(
            {
                "error": f"Unexpected error ({type(e).__name__}: {e}). The controller was not touched; "
                "if a write was in progress, check list_profiles and list_backups."
            },
            ensure_ascii=False,
        )


CHANGES_DOC = """changes (all optional):
{
 "buttons":  {"A": "B", "X": "self", "M1": {"keyboard": "Space"}, "RB": {"turbo": {"rate": 15, "mode": "press"}}},
 "sticks":   {"left": {"deadzone_center": -5, "deadzone_edge": 3, "curve": {"p1": [64, 60], "p2": [127, 127]},
              "circularity": "circular"}},
 "triggers": {"left": {"start": 10, "end": 240}, "right": {"trigger_vibration": false}},
 "vibration": {"enabled": true, "left": {"strength": 60}, "right": {"min": 60, "max": 255}},
 "motion":   {"mode": "right_stick", "sensitivity": 30, "deadzone": 4},
 "led":      {"brightness": 80}
}
Ranges and names: call list_options."""


@mcp.tool()
def status(language: str = "") -> str:
    """Check Space Station: data folder, version and format compatibility, whether the app is open (write tools
    need it closed), and which controllers have data on this PC. Read-only. Call this first.
    language: the language the user is writing in (e.g. 'es', 'de', 'ja', 'pt-BR'). The result then includes
    'space_station_ui': the exact names of Space Station's sections and buttons in that language, taken from the
    app itself. Always use those names when telling the user where to click; never translate them yourself."""

    def f():
        app = ipc.app_running()
        compat_info = compat.report()
        can_write = not app and compat_info["schema_ok"]
        if not compat_info["schema_ok"]:
            note = "Writes are blocked: the profile format changed. Reading still works."
        elif app:
            note = "Close Space Station to create or edit local profiles."
        else:
            note = "Ready to prepare local profiles."
        return {
            "data_folder": store.data_dir(),
            "compatibility": compat_info,
            "space_station_open": app,
            "can_write": can_write,
            "note": note,
            "controllers": [
                {
                    "model": models.name(d.code),
                    "device_code": d.code,
                    "support": models.support_level(d.code),
                    **d.__dict__,
                }
                for d in store.devices()
            ],
            "backup_folder": store.backup_root(),
            "export_folder": share.default_folder(),
            "space_station_ui": ui.labels(language),
        }

    return _out(f)


@mcp.tool()
def export_profile(source: str, path: str = "", device_code: str = "") -> str:
    """Save a profile to a portable .json file to share it (GitHub, Discord, forums) without Flydigi's cloud.
    source: 'slot:N' (1-4, as in Space Station), 'local:<name>' or 'factory:<id>'.
    path: optional full path ending in .json; by default the file goes to Documents/Flydigi Profiles.
    Read-only for Space Station."""
    return _out(share.export, source, path, device_code)


@mcp.tool()
def import_profile(path: str, title: str = "", dry_run: bool = True, device_code: str = "") -> str:
    """Import a profile .json file (made by export_profile) as a NEW LOCAL profile. The file is untrusted: it is
    fully validated (format, checksum, controller model, every value range) before anything is created.
    Never touches the controller. dry_run=true (default) only validates and shows the differences against the
    user's slot 1; run again with dry_run=false after the user agrees. Needs Space Station closed to write."""
    return _out(share.import_file, path, title, dry_run, device_code)


@mcp.tool()
def list_profiles(device_code: str = "") -> str:
    """List the controller's 4 onboard slots (read-only copy saved by the app), the LOCAL profiles on the PC
    (the ones this server can edit) and the factory profiles. Read-only."""
    return _out(ops.overview, device_code)


@mcp.tool()
def get_profile(source: str, device_code: str = "", raw: bool = False) -> str:
    """Show a profile in readable form: buttons, sticks (deadzones, curve), triggers, vibration, gyro, LED, macros.
    source: 'slot:1'..'slot:4' (onboard copy, numbered as in Space Station), 'local:<name|file_name|position>', or
    'factory:<id>'.
    raw=true returns the full protobuf JSON. Read-only."""

    def f():
        dev, b, label = ops.load_source(source, device_code)
        from flydigi import schema

        return {
            "controller": models.label(dev.code),
            "source": label,
            "profile": schema.to_dict(b) if raw else profile.view(b, models.SUPPORTED.get(dev.code)),
        }

    return _out(f)


@mcp.tool()
def compare_profiles(source_a: str, source_b: str, device_code: str = "") -> str:
    """Differences between two profiles (same source syntax as get_profile). Read-only."""

    def f():
        dev, a, la = ops.load_source(source_a, device_code)
        _, b, lb = ops.load_source(source_b, dev.code)
        mdl = models.SUPPORTED.get(dev.code)
        diffs = profile.describe_changes(profile.view(a, mdl), profile.view(b, mdl))
        return {"controller": models.label(dev.code), "a": la, "b": lb, "differences": diffs or ["(identical)"]}

    return _out(f)


@mcp.tool()
def list_options(device_code: str = "") -> str:
    """Button names, keyboard keys and the valid range of every editable setting. Read-only."""
    return _out(ops.options, device_code)


@mcp.tool()
def list_macros() -> str:
    """Macros saved in Space Station's macro library on the PC, with their actions. Read-only."""
    return _out(ops.macros)


@mcp.tool(
    description=f"""Create a NEW LOCAL profile on the PC from a copy of an existing one plus changes.
Never touches the controller. Needs Space Station closed (unless dry_run).
source: 'slot:N' (1-4, as in Space Station), 'local:<name>' or 'factory:<id>'. title: max 10 characters.
dry_run=true (default) only shows the diff; run again with dry_run=false after the user agrees.
{CHANGES_DOC}"""
)
def create_local_profile(
    source: str, title: str, changes: dict | None = None, dry_run: bool = True, device_code: str = ""
) -> str:
    return _out(ops.create, source, title, changes, dry_run, device_code)


@mcp.tool(
    description=f"""Edit an existing LOCAL profile (by name, file_name or position). Never touches the
controller. Saves the new version, then removes the old one and keeps its place in the list; a backup is
taken first. Needs Space Station closed (unless dry_run). dry_run=true (default) only shows the diff.
{CHANGES_DOC}"""
)
def edit_local_profile(profile_ref: str, changes: dict, dry_run: bool = True, device_code: str = "") -> str:
    return _out(ops.edit, profile_ref, changes, dry_run, device_code)


@mcp.tool()
def duplicate_local_profile(profile_ref: str, title: str, device_code: str = "") -> str:
    """Copy a LOCAL profile under a new name (max 10 characters). PC only; needs Space Station closed."""
    return _out(ops.duplicate, profile_ref, title, device_code)


@mcp.tool()
def rename_local_profile(profile_ref: str, title: str, device_code: str = "") -> str:
    """Rename a LOCAL profile (max 10 characters). PC only; needs Space Station closed."""
    return _out(ops.rename, profile_ref, title, device_code)


@mcp.tool()
def move_local_profile(profile_ref: str, position: int, device_code: str = "") -> str:
    """Move a LOCAL profile to a position in the list (1 = first). PC only; needs Space Station closed."""
    return _out(ops.move, profile_ref, position, device_code)


@mcp.tool()
def delete_local_profile(profile_ref: str, device_code: str = "") -> str:
    """Delete a LOCAL profile from the PC (a backup is taken first). Confirm with the user before calling.
    Never touches the controller's slots. Needs Space Station closed."""
    return _out(ops.delete, profile_ref, device_code)


@mcp.tool()
def list_backups() -> str:
    """Backups of the local profiles and macro library taken before each change (newest first, the newest 50 are
    kept), with when each was taken and which change it precedes."""
    return _out(ops.backups)


@mcp.tool()
def undo_last_change() -> str:
    """Undo the most recent change to local profiles by restoring the backup taken just before it. Call it again
    to go one more step back. PC files only, never the controller. Needs Space Station closed. Confirm with the
    user before calling."""
    return _out(ops.undo)


@mcp.tool()
def restore_backup(name: str) -> str:
    """Restore the local profiles and macro library from a backup (takes a backup of the current state first).
    PC files only. Needs Space Station closed. Confirm with the user before calling."""
    return _out(ops.restore, name)


if __name__ == "__main__":
    mcp.run()
