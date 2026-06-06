from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from enum import IntEnum
from xml.etree import ElementTree


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

    async def send_sms(
        self,
        phone: str,
        content: str,
        sim: int,
        wake_screen_before_send: bool,
        compose_wait_seconds: float,
        send_button_resource_id: str | None,
        confirm_keyevents: list[str],
        confirm_taps: list[tuple[int, int]],
        keyevent_interval_seconds: float,
        timeout: float,
    ) -> str:
        if wake_screen_before_send:
            await self.wake_screen(timeout=timeout)
        output = await self.shell(build_sms_intent_args(phone, content, sim), timeout=timeout)
        await asyncio.sleep(compose_wait_seconds)
        confirmed = False
        if send_button_resource_id:
            await self.tap_by_resource_id(send_button_resource_id, timeout=timeout)
            confirmed = True
        for keyevent in confirm_keyevents:
            await self.shell(["shell", "input", "keyevent", keyevent], timeout=timeout)
            confirmed = True
            await asyncio.sleep(keyevent_interval_seconds)
        for x, y in confirm_taps:
            await self.shell(["shell", "input", "tap", str(x), str(y)], timeout=timeout)
            confirmed = True
            await asyncio.sleep(keyevent_interval_seconds)
        if not confirmed:
            raise AdbError("sms confirm action is not configured")
        return output

    async def wake_screen(self, timeout: float = 10.0) -> None:
        await self.shell(["shell", "input", "keyevent", "WAKEUP"], timeout=timeout)
        await self.shell(["shell", "wm", "dismiss-keyguard"], timeout=timeout)

    async def tap_by_resource_id(self, resource_id: str, timeout: float = 10.0) -> None:
        dump_path = "/sdcard/autocallbot-window.xml"
        await self.shell(["shell", "uiautomator", "dump", dump_path], timeout=timeout)
        output = await self.shell(["shell", "cat", dump_path], timeout=timeout)
        bounds = find_resource_bounds(output, resource_id)
        if bounds is None:
            raise AdbError(f"resource id not found: {resource_id}")
        left, top, right, bottom = bounds
        await self.shell(["shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2)], timeout=timeout)

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


def build_sms_intent_args(phone: str, content: str, sim: int) -> list[str]:
    return [
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.SENDTO",
        "-d",
        f"smsto:{phone}",
        "--es",
        "sms_body",
        content,
        "--ez",
        "exit_on_sent",
        "true",
        "--ei",
        "com.android.phone.extra.slot",
        str(sim),
        "--ei",
        "android.telephony.extra.SUBSCRIPTION_INDEX",
        str(sim),
    ]


def find_resource_bounds(xml_text: str, resource_id: str) -> tuple[int, int, int, int] | None:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None
    for node in root.iter("node"):
        if node.attrib.get("resource-id") != resource_id:
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is not None:
            return bounds
    return None


def parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d+),(\d+)]\[(\d+),(\d+)]", bounds)
    if match is None:
        return None
    return tuple(int(value) for value in match.groups())


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
