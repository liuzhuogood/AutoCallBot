from pathlib import Path

import pytest

from autocallbot import audio, config
from autocallbot.audio import AudioError


def test_get_audio_output_backend_accepts_supported_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUDIO_OUTPUT_BACKEND", "bluetooth")
    assert audio.get_audio_output_backend() == "bluetooth"
    assert audio.requires_android_bt_sco() is True

    monkeypatch.setattr(config, "AUDIO_OUTPUT_BACKEND", "alsa")
    assert audio.get_audio_output_backend() == "alsa"
    assert audio.requires_android_bt_sco() is False


def test_get_audio_output_backend_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUDIO_OUTPUT_BACKEND", "hdmi")

    with pytest.raises(AudioError, match="Unsupported AUDIO_OUTPUT_BACKEND"):
        audio.get_audio_output_backend()


def test_build_ffmpeg_command_uses_bluetooth_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "BLUEALSA_PCM", "bluealsa:DEV=AA:BB,PROFILE=sco")
    monkeypatch.setattr(config, "SCO_RATE", 16000)
    monkeypatch.setattr(config, "PLAYBACK_LOOP_FOREVER", True)

    command = audio.build_ffmpeg_command(Path("audio/kgtx.mp3"), 30, "bluetooth")

    assert command[command.index("-stream_loop") + 1] == "-1"
    assert command[-1] == "bluealsa:DEV=AA:BB,PROFILE=sco"
    assert command[command.index("-ar") + 1] == "16000"
    assert command[command.index("-af") + 1] == "volume=4.0,aresample=16000"


def test_build_ffmpeg_command_uses_local_alsa_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUDIO_ALSA_PCM", "plughw:CARD=Headphones,DEV=0")
    monkeypatch.setattr(config, "ALSA_RATE", 48000)
    monkeypatch.setattr(config, "PLAYBACK_LOOP_FOREVER", True)

    command = audio.build_ffmpeg_command(Path("audio/kgtx.mp3"), 30, "alsa")

    assert command[command.index("-stream_loop") + 1] == "-1"
    assert command[-1] == "plughw:CARD=Headphones,DEV=0"
    assert command[command.index("-ar") + 1] == "48000"
    assert command[command.index("-af") + 1] == "volume=4.0,aresample=48000"


def test_build_ffmpeg_command_can_disable_looping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "PLAYBACK_LOOP_FOREVER", False)

    command = audio.build_ffmpeg_command(Path("audio/kgtx.mp3"), 30, "alsa")

    assert "-stream_loop" not in command
