from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Literal

from loguru import logger

from autocallbot import config


class AudioError(RuntimeError):
    pass


AudioOutputBackend = Literal["bluetooth", "alsa"]


async def ensure_bluealsa_sco() -> None:
    await ensure_audio_output()


async def ensure_audio_output() -> None:
    backend = get_audio_output_backend()
    if backend == "bluetooth":
        await ensure_bluetooth_output()
    else:
        await ensure_alsa_output()


async def ensure_bluetooth_output() -> None:
    output = await asyncio.to_thread(run_check, [config.BLUEALSA_APLAY_PATH, "-L"])
    if f"DEV={config.PHONE_MAC}" not in output or "PROFILE=sco" not in output or "playback" not in output:
        raise AudioError("BlueALSA SCO playback is not available")


async def ensure_alsa_output() -> None:
    output = await asyncio.to_thread(run_check, [config.APLAY_PATH, "-L"])
    if config.AUDIO_ALSA_PCM not in output:
        raise AudioError(f"ALSA audio output is not available: {config.AUDIO_ALSA_PCM}")


async def play_mp3(audio_path: str, seconds: float) -> None:
    path = Path(audio_path)
    if not path.exists():
        raise AudioError(f"Audio file not found: {audio_path}")

    backend = get_audio_output_backend()
    command = build_ffmpeg_command(path, seconds, backend)
    logger.info("playback start backend={} audio_path={} seconds={}", backend, audio_path, seconds)
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


def build_ffmpeg_command(path: Path, seconds: float, backend: AudioOutputBackend) -> list[str]:
    command = [
        config.FFMPEG_PATH,
        "-hide_banner",
        "-nostdin",
        "-re",
    ]
    if config.PLAYBACK_LOOP_FOREVER:
        command.extend(["-stream_loop", "-1"])
    command.extend(
        [
            "-i",
            str(path),
            "-t",
            str(seconds),
            "-af",
            f"volume={config.PLAYBACK_VOLUME},aresample={audio_rate(backend)}",
            "-f",
            "alsa",
            "-ac",
            "1",
            "-ar",
            str(audio_rate(backend)),
            audio_pcm(backend),
        ]
    )
    return command


def get_audio_output_backend() -> AudioOutputBackend:
    backend = config.AUDIO_OUTPUT_BACKEND.lower()
    if backend not in {"bluetooth", "alsa"}:
        raise AudioError(f"Unsupported AUDIO_OUTPUT_BACKEND: {config.AUDIO_OUTPUT_BACKEND}")
    return backend


def requires_android_bt_sco() -> bool:
    return get_audio_output_backend() == "bluetooth"


def audio_pcm(backend: AudioOutputBackend) -> str:
    if backend == "bluetooth":
        return config.BLUEALSA_PCM
    return config.AUDIO_ALSA_PCM


def audio_rate(backend: AudioOutputBackend) -> int:
    if backend == "bluetooth":
        return config.SCO_RATE
    return config.ALSA_RATE


def run_check(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=10, check=False)
    except FileNotFoundError as exc:
        raise AudioError(f"{command[0]} command not found") from exc
    if completed.returncode != 0:
        raise AudioError(completed.stderr.strip() or completed.stdout.strip() or "audio output check failed")
    return completed.stdout
