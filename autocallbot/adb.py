from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from enum import IntEnum
from pathlib import PurePosixPath


class CallState(IntEnum):
    IDLE = 0
    RINGING = 1
    OFFHOOK = 2


@dataclass(frozen=True)
class AdbResult:
    returncode: int
    stdout: str
    stderr: str


class AdbError(RuntimeError):
    pass


class AdbClient:
    def __init__(self, serial: str, adb_path: str = "adb") -> None:
        self.serial = serial
        self.adb_path = adb_path

    async def run(self, args: list[str], timeout: float = 15.0) -> AdbResult:
        command = [self.adb_path, "-s", self.serial, *args]
        return await asyncio.to_thread(self._run_sync, command, timeout)

    def _run_sync(self, command: list[str], timeout: float) -> AdbResult:
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AdbError("adb command not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb command timed out: {' '.join(command)}") from exc

        if completed.returncode != 0:
            raise AdbError(completed.stderr.strip() or completed.stdout.strip() or "adb command failed")
        return AdbResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    async def dial(self, phone: str, sim: int) -> None:
        await self.run(
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
            ],
            timeout=15,
        )

    async def hangup(self) -> None:
        await self.run(["shell", "input", "keyevent", "KEYCODE_ENDCALL"], timeout=10)

    async def set_media_volume(self, volume: int) -> None:
        await self.run(["shell", "media", "volume", "--stream", "3", "--set", str(volume)], timeout=10)

    async def play_audio(self, audio_path: str) -> None:
        path = audio_path if audio_path.startswith("file://") else f"file://{audio_path}"
        await self.run(
            [
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                path,
                "-t",
                guess_audio_mime_type(audio_path),
            ],
            timeout=15,
        )

    async def get_call_state(self) -> CallState:
        result = await self.run(["shell", "dumpsys", "telephony.registry"], timeout=10)
        return parse_call_state(result.stdout)

    async def get_call_snapshot(self) -> "CallSnapshot":
        result = await self.run(["shell", "dumpsys", "telephony.registry"], timeout=10)
        return parse_call_snapshot(result.stdout)


def parse_call_state(output: str) -> CallState:
    states = [int(value) for value in re.findall(r"mCallState\s*=\s*(\d)", output)]
    if not states:
        states = [int(value) for value in re.findall(r"mCallState(?:ForPhoneId)?\[\d+\]\s*=\s*(\d)", output)]
    if not states:
        return CallState.IDLE
    if CallState.OFFHOOK in states:
        return CallState.OFFHOOK
    if CallState.RINGING in states:
        return CallState.RINGING
    return CallState.IDLE


@dataclass(frozen=True)
class CallSnapshot:
    state: CallState
    is_active: bool


def parse_call_snapshot(output: str) -> CallSnapshot:
    foreground_states = [int(value) for value in re.findall(r"Foreground call state:\s*(-?\d+)", output)]
    call_state = parse_call_state(output)
    if foreground_states:
        return CallSnapshot(state=call_state, is_active=1 in foreground_states)
    return CallSnapshot(state=call_state, is_active=call_state == CallState.OFFHOOK)


def guess_audio_mime_type(audio_path: str) -> str:
    suffix = PurePosixPath(audio_path.removeprefix("file://")).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
    }.get(suffix, "audio/mpeg")
