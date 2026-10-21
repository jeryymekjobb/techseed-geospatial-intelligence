"""Windows desktop operations, loaded only on Windows. No third-party packages."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import time


def user32():
    api = ctypes.WinDLL("user32", use_last_error=True)
    try:
        api.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        api.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor DPI awareness v2
    except AttributeError:
        api.SetProcessDPIAware()
    # Pointer-sized handles must not be truncated on 64-bit Windows.
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.IsWindowVisible.argtypes = [wintypes.HWND]
    api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
    return api


def monitors():
    from tools.open_screens import Monitor

    class Info(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    api = user32()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    api.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback_type, wintypes.LPARAM]
    found = []

    def collect(handle, dc, rect, data):
        info = Info()
        info.size = ctypes.sizeof(info)
        if api.GetMonitorInfoW(handle, ctypes.byref(info)):
            area = info.work
            found.append(Monitor(str(len(found)), area.right - area.left, area.bottom - area.top,
                                 area.left, area.top))
        return True

    if not api.EnumDisplayMonitors(None, None, callback_type(collect), 0):
        raise OSError("Windows could not enumerate monitors")
    return found


def place(pid, window, seconds=20.0):
    api = user32()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = []

        def collect(handle, data):
            owner = wintypes.DWORD()
            api.GetWindowThreadProcessId(handle, ctypes.byref(owner))
            if owner.value == pid and api.IsWindowVisible(handle):
                found.append(handle)
            return True

        api.EnumWindows(callback_type(collect), 0)
        if found:
            api.ShowWindow(found[0], 9)  # SW_RESTORE before applying the shared layout
            return bool(api.SetWindowPos(found[0], None, window.x, window.y,
                                         window.width, window.height, 0x0014))  # no activation/z-order change
        time.sleep(0.25)
    return False


def close_command(profile: Path) -> list[str]:
    """Match one complete profile argument, never all Chrome processes or a PID tree."""
    value = str(profile).replace("'", "''")
    script = (f"$profile = '{value}'; "
              "$argument = [regex]::Escape('--user-data-dir=' + $profile); "
              "$pattern = '(?:^|\\s)(?:\"' + $argument + '\"|' + $argument + '(?=\\s|$))'; "
              "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' OR Name = 'chromium.exe'\" | "
              "Where-Object { $_.CommandLine -cmatch $pattern } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]
