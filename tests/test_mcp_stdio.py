# /// script
# requires-python = ">=3.10"
# dependencies = ["protobuf>=5.26,<7"]
# ///
"""Start the real MCP server over stdio against SYNTHETIC data, list its tools and call the read-only ones.
Run: uv run --script tests/test_mcp_stdio.py"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import fixtures  # noqa: E402

fixtures.build(tempfile.mkdtemp(prefix="flydigi-mcp-"))
EXPECTED = {
    "status",
    "list_profiles",
    "get_profile",
    "compare_profiles",
    "list_options",
    "list_macros",
    "create_local_profile",
    "edit_local_profile",
    "duplicate_local_profile",
    "rename_local_profile",
    "move_local_profile",
    "delete_local_profile",
    "list_backups",
    "restore_backup",
    "undo_last_change",
    "export_profile",
    "import_profile",
}

p = subprocess.Popen(
    ["uv", "run", "--script", os.path.join(HERE, "..", "server", "flydigi_mcp.py")],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    env=os.environ.copy(),
)


def send(obj):
    p.stdin.write((json.dumps(obj) + "\n").encode())
    p.stdin.flush()


def recv():
    return json.loads(p.stdout.readline())


try:
    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
    )
    print("server:", recv()["result"]["serverInfo"]["name"])
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = {t["name"] for t in recv()["result"]["tools"]}
    assert tools == EXPECTED, f"tool list changed: missing {EXPECTED - tools}, extra {tools - EXPECTED}"
    print(f"tools: {len(tools)} as expected")
    calls = [
        ("status", {"language": "es"}),
        ("list_profiles", {}),
        ("get_profile", {"source": "slot:1"}),
        ("compare_profiles", {"source_a": "slot:1", "source_b": "local:Local One"}),
        ("list_options", {}),
        ("list_macros", {}),
        ("export_profile", {"source": "slot:2"}),
        ("create_local_profile", {"source": "slot:1", "title": "Dry", "changes": {"led": {"brightness": 5}}}),
        ("get_profile", {"source": "slot:42"}),
    ]
    for i, (name, args) in enumerate(calls, start=3):
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
        out = json.loads(recv()["result"]["content"][0]["text"])
        is_error = isinstance(out, dict) and "error" in out
        if name == "status":
            assert out["space_station_ui"]["labels"]["inactive_configs"] == "Configuraciones inactivas", out
        if name == "create_local_profile":
            assert out["changes"] == ["Profile name: Slot A → Dry", "LED › brightness: 100 → 5"], out
        assert is_error == (name == "get_profile" and args["source"] == "slot:42"), f"{name}: {out}"
        print(f"  {name}: {'error as expected' if is_error else 'ok'}")
    print("OK: MCP server answers every read-only tool")

    # Hostile or malformed input must always come back as a clear {"error": ...}, never a crash.
    hostile = [
        ("get_profile", {"source": "slot:x"}),
        ("get_profile", {"source": "slot:"}),
        ("get_profile", {"source": ""}),
        ("get_profile", {"source": "factory:144:9"}),
        ("get_profile", {"source": "factory:144:x"}),
        ("get_profile", {"source": "local:"}),
        ("compare_profiles", {"source_a": "slot:1", "source_b": "nope"}),
        ("create_local_profile", {"source": "slot:1", "title": "T", "changes": {"buttons": "A"}}),
        ("create_local_profile", {"source": "slot:1", "title": "T", "changes": {"triggers": [1, 2]}}),
        ("create_local_profile", {"source": "slot:1", "title": "T", "changes": {"buttons": {"A": 5}}}),
        (
            "create_local_profile",
            {"source": "slot:1", "title": "T", "changes": {"buttons": {"RB": {"turbo": {"rate": "fast"}}}}},
        ),
        (
            "create_local_profile",
            {"source": "slot:1", "title": "T", "changes": {"sticks": {"left": {"curve": {"p1": [1]}}}}},
        ),
        ("edit_local_profile", {"profile_ref": "", "changes": {}}),
        ("move_local_profile", {"profile_ref": "Local One", "position": 0}),
        ("import_profile", {"path": ""}),
        ("export_profile", {"source": "slot:1", "path": "C:\\nope\\x.json"}),
        ("restore_backup", {"name": "..\\..\\Windows"}),
        ("list_options", {"device_code": "zz"}),
    ]
    for i, (name, args) in enumerate(hostile, start=100):
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
        out = json.loads(recv()["result"]["content"][0]["text"])
        assert (
            isinstance(out, dict) and "error" in out and "Unexpected error" not in out["error"]
        ), f"{name}{args}: {out}"
    print(f"OK: {len(hostile)} malformed inputs all return a clear error")
finally:
    p.terminate()
