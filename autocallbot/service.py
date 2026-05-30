from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from time import monotonic

from loguru import logger

from autocallbot import audio, config
from autocallbot.adb import AdbClient, AdbError, CallState
from autocallbot.models import CallResponse, CallStatus


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CallService:
    def __init__(self) -> None:
        self._busy = False
        self._lock = asyncio.Lock()
        self.adb = AdbClient(config.ADB_SERIAL)

    async def call(self, phone: str, audio_path: str, sim: int | None, play_seconds: float | None) -> CallResponse | None:
        if not await self._acquire():
            return None
        try:
            return await self._call(phone, audio_path, config.DEFAULT_SIM if sim is None else sim, self._seconds(play_seconds))
        finally:
            await self._release()

    async def _call(self, phone: str, audio_path: str, sim: int, play_seconds: float) -> CallResponse:
        call_id = str(uuid.uuid4())
        started_at = now_iso()
        connected_at: str | None = None
        logger.info("call start call_id={} phone={} audio_path={} seconds={}", call_id, phone, audio_path, play_seconds)

        def response(status: CallStatus, message: str, error: str | None = None) -> CallResponse:
            return CallResponse(
                status=status,
                message=message,
                call_id=call_id,
                phone=phone,
                device_id=config.DEVICE_ID,
                audio_path=audio_path,
                play_seconds=play_seconds,
                started_at=started_at,
                connected_at=connected_at,
                ended_at=now_iso(),
                error=error,
            )

        try:
            if config.MEDIA_VOLUME is not None:
                await self._try_set_volume(config.MEDIA_VOLUME)

            await self.adb.dial(phone, sim)
            connected = await self._wait_connected()
            if connected != CallStatus.COMPLETED:
                await self._safe_hangup()
                result = response(connected, status_message(connected))
                logger.info("call end call_id={} status={} message={}", call_id, result.status, result.message)
                return result

            connected_at = now_iso()
            await asyncio.sleep(config.POST_CONNECT_GRACE_SECONDS)
            if config.REQUIRE_BT_SCO and audio.requires_android_bt_sco():
                await self._wait_bt_sco()
            await audio.ensure_audio_output()

            result = await self._play_until_done_or_hung_up(audio_path, play_seconds)
            if result == CallStatus.COMPLETED:
                await self._safe_hangup()
            final = response(result, status_message(result))
            logger.info("call end call_id={} status={} message={}", call_id, final.status, final.message)
            return final
        except Exception as exc:
            logger.exception("call failed call_id={} phone={}", call_id, phone)
            await self._safe_hangup()
            return response(CallStatus.FAILED, "call failed", str(exc))

    async def _play_until_done_or_hung_up(self, audio_path: str, play_seconds: float) -> CallStatus:
        playback = asyncio.create_task(audio.play_mp3(audio_path, play_seconds))
        monitor = asyncio.create_task(self._wait_hung_up_or_timeout(play_seconds))
        done, _ = await asyncio.wait({playback, monitor}, return_when=asyncio.FIRST_COMPLETED)

        if playback in done:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            await playback
            return CallStatus.COMPLETED

        status = await monitor
        playback.cancel()
        await asyncio.gather(playback, return_exceptions=True)
        return status

    async def _wait_connected(self) -> CallStatus:
        started = monotonic()
        ever_non_idle = False
        while True:
            elapsed = monotonic() - started
            snapshot = await self.adb.get_call_snapshot()
            if snapshot.state != CallState.IDLE:
                ever_non_idle = True
            if snapshot.is_active:
                return CallStatus.COMPLETED
            if snapshot.state == CallState.IDLE and ever_non_idle:
                return CallStatus.INVALID_OR_STOPPED if elapsed <= config.INVALID_HANGUP_SECONDS else CallStatus.HUNG_UP
            if elapsed >= config.NO_ANSWER_TIMEOUT_SECONDS:
                return CallStatus.NO_ANSWER
            await asyncio.sleep(config.POLL_INTERVAL_SECONDS)

    async def _wait_bt_sco(self) -> None:
        started = monotonic()
        while monotonic() - started < config.BT_SCO_WAIT_SECONDS:
            if await self.adb.is_bt_sco_active():
                return
            await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
        raise RuntimeError("Android bt_sco route is not active")

    async def _wait_hung_up_or_timeout(self, seconds: float) -> CallStatus:
        started = monotonic()
        while monotonic() - started < seconds:
            snapshot = await self.adb.get_call_snapshot()
            if snapshot.state == CallState.IDLE:
                return CallStatus.HUNG_UP
            await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
        return CallStatus.COMPLETED

    async def _try_set_volume(self, volume: int) -> None:
        try:
            await self.adb.set_media_volume(volume)
        except AdbError as exc:
            logger.warning("set media volume skipped: {}", exc)

    async def _safe_hangup(self) -> None:
        try:
            await self.adb.hangup()
        except Exception as exc:
            logger.warning("hangup skipped: {}", exc)

    async def _acquire(self) -> bool:
        async with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    async def _release(self) -> None:
        async with self._lock:
            self._busy = False

    def _seconds(self, requested: float | None) -> float:
        return min(requested or config.MAX_PLAY_SECONDS, config.MAX_PLAY_SECONDS)


def status_message(status: CallStatus) -> str:
    return {
        CallStatus.COMPLETED: "playback finished, call ended",
        CallStatus.INVALID_OR_STOPPED: "call ended within invalid-number threshold",
        CallStatus.NO_ANSWER: "no answer before timeout",
        CallStatus.HUNG_UP: "call hung up",
        CallStatus.FAILED: "call failed",
    }[status]
