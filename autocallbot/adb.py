from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from enum import IntEnum


class CallState(IntEnum):
    IDLE = 0
    RINGING = 1
    OFFHOOK = 2


class AdbError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallSnapshot:
    state: CallState
    is_active: bool


class AdbClient:
    def __init__(self, serial: str, adb_path: str = "adb") -> None:
        self.serial = serial
        self.adb_path = adb_path
        self._connected = False

    async def shell(self, args: list[str], timeout: float = 15.0) -> str:
        await self.ensure_connected()
        command = [self.adb_path, "-s", self.serial, *args]
        try:
            return await asyncio.to_thread(run_adb, command, timeout)
        except AdbError as exc:
            if not is_tcp_serial(self.serial) or not is_missing_device_error(str(exc)):
                raise
            self._connected = False
            await self.ensure_connected()
            return await asyncio.to_thread(run_adb, command, timeout)

    async def ensure_connected(self) -> None:
        if self._connected or not is_tcp_serial(self.serial):
            return
        output = await asyncio.to_thread(run_adb, [self.adb_path, "connect", self.serial], 10)
        if not is_connect_success(output):
            raise AdbError(output.strip() or f"adb connect {self.serial} failed")
        self._connected = True

    async def dial(self, phone: str, sim: int) -> None:
        await self.shell(
            [
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.CALL",
                "-d",
                f"tel:{phone}",
                "--ei",
                "com.android.phone.extra.slot",
                str(sim),
            ]
        )

    async def hangup(self) -> None:
        await self.shell(["shell", "input", "keyevent", "KEYCODE_ENDCALL"], timeout=10)

    async def set_media_volume(self, volume: int) -> None:
        await self.shell(["shell", "media", "volume", "--stream", "3", "--set", str(volume)], timeout=10)

    async def get_call_snapshot(self) -> CallSnapshot:
        output = await self.shell(["shell", "dumpsys", "telephony.registry"], timeout=10)
        return parse_call_snapshot(output)

    async def is_bt_sco_active(self) -> bool:
        output = await self.shell(["shell", "dumpsys", "audio"], timeout=10)
        return parse_bt_sco_active(output)


def run_adb(command: list[str], timeout: float) -> str:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise AdbError("adb command not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdbError(f"adb command timed out: {' '.join(command)}") from exc

    if completed.returncode != 0:
        raise AdbError(completed.stderr.strip() or completed.stdout.strip() or "adb command failed")
    return completed.stdout


def is_tcp_serial(serial: str) -> bool:
    return re.fullmatch(r"[^:\s]+:\d+", serial) is not None


def is_connect_success(output: str) -> bool:
    return any(
        line.strip().lower().startswith(("connected to ", "already connected to "))
        for line in output.splitlines()
    )


def is_missing_device_error(message: str) -> bool:
    normalized = message.lower()
    return "not found" in normalized or "offline" in normalized or "no devices" in normalized


def parse_call_state(output: str) -> CallState:
    states = [int(value) for value in re.findall(r"mCallState\s*=\s*(\d)", output)]
    if not states:
        states = [int(value) for value in re.findall(r"mCallState(?:ForPhoneId)?\[\d+\]\s*=\s*(\d)", output)]
    if CallState.OFFHOOK in states:
        return CallState.OFFHOOK
    if CallState.RINGING in states:
        return CallState.RINGING
    return CallState.IDLE


def parse_call_snapshot(output: str) -> CallSnapshot:
    foreground_states = [int(value) for value in re.findall(r"Foreground call state:\s*(-?\d+)", output)]
    state = parse_call_state(output)
    return CallSnapshot(state=state, is_active=1 in foreground_states if foreground_states else state == CallState.OFFHOOK)


def parse_bt_sco_active(output: str) -> bool:
    active_lines = [line for line in output.splitlines() if "Active communication device" in line]
    return any("bt_sco" in line.lower() for line in active_lines)
