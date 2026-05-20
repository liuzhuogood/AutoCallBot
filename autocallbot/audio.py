from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from loguru import logger

from autocallbot import config


class AudioError(RuntimeError):
    pass


async def ensure_bluealsa_sco() -> None:
    output = await asyncio.to_thread(run_check, [config.BLUEALSA_APLAY_PATH, "-L"])
    if f"DEV={config.PHONE_MAC}" not in output or "PROFILE=sco" not in output or "playback" not in output:
        raise AudioError("BlueALSA SCO playback is not available")


async def play_mp3(audio_path: str, seconds: float) -> None:
    path = Path(audio_path)
    if not path.exists():
        raise AudioError(f"Audio file not found: {audio_path}")

    command = [
        config.FFMPEG_PATH,
        "-hide_banner",
        "-nostdin",
        "-re",
        "-i",
        str(path),
        "-t",
        str(seconds),
        "-af",
        f"volume={config.PLAYBACK_VOLUME},aresample={config.SCO_RATE}",
        "-f",
        "alsa",
        "-ac",
        "1",
        "-ar",
        str(config.SCO_RATE),
        config.BLUEALSA_PCM,
    ]
    logger.info("playback start audio_path={} seconds={}", audio_path, seconds)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate()
    except asyncio.CancelledError:
        process.terminate()
        try:
            await asyncio.wait_for(process.communicate(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
        logger.info("playback cancelled audio_path={}", audio_path)
        raise

    stderr_text = stderr.decode(errors="replace").strip()
    stdout_text = stdout.decode(errors="replace").strip()
    if stdout_text:
        logger.debug("ffmpeg stdout: {}", stdout_text)
    if stderr_text:
        logger.info("ffmpeg stderr: {}", stderr_text[-2000:])
    if process.returncode != 0:
        raise AudioError(f"ffmpeg playback failed with code {process.returncode}")
    logger.info("playback finished audio_path={}", audio_path)


def run_check(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=10, check=False)
    if completed.returncode != 0:
        raise AudioError(completed.stderr.strip() or completed.stdout.strip() or "bluealsa check failed")
    return completed.stdout
