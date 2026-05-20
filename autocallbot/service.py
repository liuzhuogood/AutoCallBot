from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic

from autocallbot.adb import AdbClient, AdbError, CallState
from autocallbot.config import AppConfig, DeviceConfig
from autocallbot.models import StatusResponse, TaskStatus


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CallTask:
    task_id: str
    phone: str
    device: DeviceConfig
    sim: int
    audio_path: str
    play_seconds: float
    status: TaskStatus = TaskStatus.DIALING
    message: str = "dialing started"
    started_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    connected_at: str | None = None
    ended_at: str | None = None
    error: str | None = None

    def update(self, status: TaskStatus, message: str, error: str | None = None) -> None:
        self.status = status
        self.message = message
        self.updated_at = utc_now_iso()
        if error:
            self.error = error
        if status in {
            TaskStatus.COMPLETED,
            TaskStatus.INVALID_OR_STOPPED,
            TaskStatus.NO_ANSWER,
            TaskStatus.HUNG_UP,
            TaskStatus.FAILED,
        }:
            self.ended_at = self.updated_at

    def response(self) -> StatusResponse:
        return StatusResponse(
            task_id=self.task_id,
            phone=self.phone,
            device_id=self.device.id,
            sim=self.sim,
            audio_path=self.audio_path,
            play_seconds=self.play_seconds,
            status=self.status,
            message=self.message,
            started_at=self.started_at,
            updated_at=self.updated_at,
            connected_at=self.connected_at,
            ended_at=self.ended_at,
            error=self.error,
        )


class DevicePool:
    def __init__(self, devices: list[DeviceConfig]) -> None:
        self._devices = devices
        self._busy: dict[str, bool] = {device.id: False for device in devices}
        self._lock = asyncio.Lock()

    async def acquire(self) -> DeviceConfig | None:
        async with self._lock:
            for device in self._devices:
                if not self._busy[device.id]:
                    self._busy[device.id] = True
                    return device
            return None

    async def release(self, device_id: str) -> None:
        async with self._lock:
            if device_id in self._busy:
                self._busy[device_id] = False

    async def snapshot(self) -> dict[str, bool]:
        async with self._lock:
            return dict(self._busy)


class CallManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.pool = DevicePool(config.devices)
        self.tasks: dict[str, CallTask] = {}
        self.tasks_by_phone: dict[str, str] = {}
        self._tasks_lock = asyncio.Lock()

    async def start_call(
        self,
        phone: str,
        sim: int | None,
        audio_path: str,
        play_seconds: float | None = None,
    ) -> CallTask | None:
        device = await self.pool.acquire()
        if not device:
            return None

        resolved_play_seconds = min(play_seconds or self.config.call.max_play_seconds, self.config.call.max_play_seconds)
        task = CallTask(
            task_id=str(uuid.uuid4()),
            phone=phone,
            device=device,
            sim=device.default_sim if sim is None else sim,
            audio_path=audio_path,
            play_seconds=resolved_play_seconds,
        )
        async with self._tasks_lock:
            self.tasks[task.task_id] = task
            self.tasks_by_phone[phone] = task.task_id

        asyncio.create_task(self._run_call(task))
        return task

    async def find_status(self, task_id: str | None = None, phone: str | None = None) -> StatusResponse | None:
        async with self._tasks_lock:
            resolved_task_id = task_id or (self.tasks_by_phone.get(phone) if phone else None)
            if not resolved_task_id:
                return None
            task = self.tasks.get(resolved_task_id)
            return task.response() if task else None

    async def _run_call(self, task: CallTask) -> None:
        adb = AdbClient(task.device.serial)
        try:
            if self.config.call.media_volume is not None:
                try:
                    await adb.set_media_volume(self.config.call.media_volume)
                except AdbError as exc:
                    task.error = f"set media volume skipped: {exc}"

            await adb.dial(task.phone, task.sim)
            connected = await self._wait_until_connected_or_finished(adb, task)
            if not connected:
                return

            await asyncio.sleep(self.config.call.post_connect_grace_seconds)
            task.update(TaskStatus.PLAYING, "call connected, playing audio")
            await adb.play_audio(task.audio_path)
            playback_completed = await self._wait_until_playback_done_or_hung_up(adb, task)
            if not playback_completed:
                return
            await adb.hangup()
            task.update(TaskStatus.COMPLETED, "playback wait finished, call ended")
        except AdbError as exc:
            task.update(TaskStatus.FAILED, "adb command failed", error=str(exc))
            await self._safe_hangup(adb)
        except Exception as exc:
            task.update(TaskStatus.FAILED, "call task failed", error=str(exc))
            await self._safe_hangup(adb)
        finally:
            await self.pool.release(task.device.id)

    async def _wait_until_connected_or_finished(self, adb: AdbClient, task: CallTask) -> bool:
        started = monotonic()
        ever_non_idle = False
        while True:
            elapsed = monotonic() - started
            snapshot = await adb.get_call_snapshot()
            state = snapshot.state
            if state != CallState.IDLE:
                ever_non_idle = True
            if snapshot.is_active:
                task.connected_at = utc_now_iso()
                task.update(TaskStatus.CONNECTED, "call connected")
                return True

            if state == CallState.RINGING:
                task.update(TaskStatus.RINGING, "waiting for answer")

            if state == CallState.IDLE and ever_non_idle and elapsed <= self.config.call.invalid_hangup_seconds:
                task.update(TaskStatus.INVALID_OR_STOPPED, "call ended within invalid-number threshold")
                return False

            if state == CallState.IDLE and ever_non_idle:
                task.update(TaskStatus.HUNG_UP, "call ended before answer")
                return False

            if elapsed >= self.config.call.no_answer_timeout_seconds:
                await adb.hangup()
                task.update(TaskStatus.NO_ANSWER, "no answer before timeout")
                return False

            await asyncio.sleep(self.config.call.poll_interval_seconds)

    async def _wait_until_playback_done_or_hung_up(self, adb: AdbClient, task: CallTask) -> bool:
        started = monotonic()
        while True:
            elapsed = monotonic() - started
            if elapsed >= task.play_seconds:
                return True

            snapshot = await adb.get_call_snapshot()
            if snapshot.state == CallState.IDLE:
                task.update(TaskStatus.HUNG_UP, "call ended before playback wait finished")
                return False

            await asyncio.sleep(min(self.config.call.poll_interval_seconds, task.play_seconds - elapsed))

    async def _safe_hangup(self, adb: AdbClient) -> None:
        try:
            await adb.hangup()
        except Exception:
            pass
