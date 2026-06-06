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
    rate = audio_rate(backend)

    ffmpeg_cmd = _build_ffmpeg_cmd(path, seconds, rate, backend)
    aplay_cmd = _build_aplay_cmd(rate, backend)

    logger.info("playback start backend={} audio_path={} seconds={}", backend, audio_path, seconds)
    await asyncio.to_thread(_play_pipe, ffmpeg_cmd, aplay_cmd)
    logger.info("playback finished audio_path={}", audio_path)


def _build_ffmpeg_cmd(path: Path, seconds: float, rate: int, backend: AudioOutputBackend) -> list[str]:
    cmd = [config.FFMPEG_PATH, "-hide_banner", "-nostdin"]
    if config.PLAYBACK_LOOP_FOREVER:
        cmd.extend(["-stream_loop", "-1"])
    cmd.extend([
        "-i", str(path),
        "-t", str(seconds),
        "-af", f"volume={config.PLAYBACK_VOLUME},aresample={rate}",
        "-f", "s16le",
        "-ac", "2",
        "-ar", str(rate),
        "-",
    ])
    return cmd


def _build_aplay_cmd(rate: int, backend: AudioOutputBackend) -> list[str]:
    return [
        config.APLAY_PATH,
        "-D", audio_pcm(backend),
        "-f", "S16_LE",
        "-r", str(rate),
        "-c", "2",
    ]


def _play_pipe(ffmpeg_cmd: list[str], aplay_cmd: list[str]) -> None:
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    aplay_proc = subprocess.Popen(
        aplay_cmd,
        stdin=ffmpeg_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ffmpeg_proc.stdout.close()

    try:
        aplay_proc.wait()
    except KeyboardInterrupt:
        aplay_proc.terminate()
        ffmpeg_proc.terminate()
        aplay_proc.wait(timeout=3)
        ffmpeg_proc.wait(timeout=3)
        raise

    ffmpeg_proc.wait()

    ffmpeg_stderr = ffmpeg_proc.stderr.read().decode(errors="replace").strip()
    aplay_stderr = aplay_proc.stderr.read().decode(errors="replace").strip()
    if ffmpeg_stderr:
        logger.info("ffmpeg stderr: {}", ffmpeg_stderr[-2000:])
    if aplay_stderr:
        logger.info("aplay stderr: {}", aplay_stderr[-2000:])
    if ffmpeg_proc.returncode and ffmpeg_proc.returncode != 0:
        raise AudioError(f"ffmpeg failed with code {ffmpeg_proc.returncode}")
    if aplay_proc.returncode and aplay_proc.returncode != 0:
        raise AudioError(f"aplay failed with code {aplay_proc.returncode}")


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
