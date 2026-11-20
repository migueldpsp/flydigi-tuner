"""Client for the Space Station service pipe (\\\\.\\pipe\\fcs.sock).

SAFETY: only commands in ALLOWED can be sent. Every one of them works on PC-side files
(local profiles / macro library). Any command that writes to the controller's memory,
firmware, calibration or factory tests is rejected here, before anything is sent."""

import contextlib
import ctypes
import msvcrt
import struct
import subprocess
import time
from ctypes import wintypes

from google.protobuf import json_format

from . import schema

_PeekNamedPipe = ctypes.windll.kernel32.PeekNamedPipe
_PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
_PeekNamedPipe.restype = wintypes.BOOL

PIPE = r"\\.\pipe\fcs.sock"
APP_EXE = "Flydigi Space Station.exe"

ALLOWED = frozenset(
    {
        "IpcCommandEnum_Init",
        "IpcCommandEnum_GetConnectedDevices",
        "IpcCommandEnum_DownloadSharedLocalConfig",  # import -> creates a LOCAL profile on the PC
        "IpcCommandEnum_UpdateLocalConfigName",
        "IpcCommandEnum_UpdateLocalConfigSort",
        "IpcCommandEnum_DeleteLocalConfig",
        "IpcCommandEnum_GetLocalMacroConfigList",
    }
)

# Never allowed, listed explicitly so a future edit of ALLOWED is easy to review.
FORBIDDEN = frozenset(
    {
        "IpcCommandEnum_UpdateConfig",
        "IpcCommandEnum_SaveConfig",
        "IpcCommandEnum_ApplyOnboardConfig",
        "IpcCommandEnum_ApplyLocalConfig",
        "IpcCommandEnum_ApplySwitchConfig",
        "IpcCommandEnum_ApplyMacroConfig",
        "IpcCommandEnum_SaveMacroConfig",
        "IpcCommandEnum_ResetMappingConfig",
        "IpcCommandEnum_WriteDeviceType",
        "IpcCommandEnum_AdcCalibration",
        "IpcCommandEnum_SwitchUsb",
        "IpcCommandEnum_SwitchToXInputMode",
        "IpcCommandEnum_UploadPic",
        "IpcCommandEnum_UpdateFrame",
        "IpcCommandEnum_UpdateReportRate",
        "IpcCommandEnum_UpdateSleepTime",
        "IpcCommandEnum_UpdateJoystickSensitivity",
        "IpcCommandEnum_UpdateJoystickPrecision",
        "IpcCommandEnum_UpdateNickname",
    }
)
assert not (ALLOWED & FORBIDDEN)


class ServiceBusy(RuntimeError):
    pass


def app_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {APP_EXE}", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        ).stdout
        return APP_EXE.lower() in out.lower()
    except Exception:
        return False


class Client:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._pipe = None
        self._handle = None

    def __enter__(self):
        if app_running():
            raise ServiceBusy(
                "Space Station is open. Its service accepts only one client at a time: "
                "close the app (including from the system tray) and try again."
            )
        # After a client disconnects the service needs ~200 ms to listen again: retry for a few seconds.
        last = None
        for _ in range(25):
            try:
                self._pipe = open(PIPE, "r+b", buffering=0)
                break
            except OSError as e:
                last = e
                time.sleep(0.2)
        else:
            if isinstance(last, FileNotFoundError):
                raise ServiceBusy("The Space Station service (SpaceStationService.exe) is not running.")
            raise ServiceBusy("The service pipe is busy (is Space Station open?). Close it and try again.")
        self._handle = msvcrt.get_osfhandle(self._pipe.fileno())
        self.call("IpcCommandEnum_Init", {"initParam": {"appVersion": "4.2.3.1", "language": "en"}})
        return self

    def __exit__(self, *exc):
        with contextlib.suppress(Exception):
            self._pipe.close()

    # -- framing -------------------------------------------------------
    # A synchronous Windows pipe can't be written while another thread is blocked reading it,
    # so everything is single-threaded: poll PeekNamedPipe and only read bytes that are there.
    def _available(self) -> int:
        avail = wintypes.DWORD(0)
        if not _PeekNamedPipe(self._handle, None, 0, None, ctypes.byref(avail), None):
            raise ConnectionError("The service closed the connection.")
        return avail.value

    def _read_exact(self, n: int, deadline: float) -> bytes:
        buf = b""
        while len(buf) < n:
            a = self._available()
            if a:
                buf += self._pipe.read(min(a, n - len(buf)))
            elif time.time() > deadline:
                raise TimeoutError("The service stopped responding in the middle of a message.")
            else:
                time.sleep(0.01)
        return buf

    def _read_message(self, deadline: float):
        """Return the next IpcResult, or None if nothing arrives before the deadline."""
        while not self._available():
            if time.time() > deadline:
                return None
            time.sleep(0.02)
        hdr = b""
        while not hdr.endswith(b"\n"):
            hdr += self._read_exact(1, deadline + 5)
        hdr = hdr.strip()

        def rd(n: int) -> bytes:
            return self._read_exact(n, deadline + 5)

        if hdr == b"FDG_PROTOCOL":
            data = rd(struct.unpack("<i", rd(4))[0])
        elif hdr == b"FDG_CHUNK":
            _, n = struct.unpack("<ii", rd(8))
            data = b"".join(rd(struct.unpack("<i", rd(4))[0]) for _ in range(n))
        elif hdr == b"FDG_COMPRESSED":
            import gzip

            data = gzip.decompress(rd(struct.unpack("<i", rd(4))[0]))
        else:
            raise ConnectionError(f"Unknown message header from the service: {hdr[:20]!r}")
        r = schema.msg("IpcResult")()
        r.ParseFromString(data)
        return r

    def call(self, cmd: str, params: dict, category: str = "Category_Controller"):
        if cmd not in ALLOWED or cmd in FORBIDDEN:
            raise PermissionError(f"Command blocked for safety: {cmd}")
        body = {"cmdId": cmd, **params}
        if cmd != "IpcCommandEnum_Init":
            body["category"] = category
        m = json_format.ParseDict(body, schema.msg("IpcCommand")())
        raw = m.SerializeToString()
        self._pipe.write(b"FDG_PROTOCOL\n" + struct.pack("<i", len(raw)) + raw)
        want = schema.enum_values("IpcCommandEnum")[cmd]
        end = time.time() + self.timeout
        while time.time() < end:
            r = self._read_message(end)
            if r is None:
                break
            if r.cmdId == want:
                return r
        raise TimeoutError(f"The service did not answer {cmd}.")
