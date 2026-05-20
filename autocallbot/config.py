from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config/devices.json")


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    serial: str
    default_sim: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class CallConfig:
    poll_interval_seconds: float = 1.0
    invalid_hangup_seconds: float = 8.0
    no_answer_timeout_seconds: float = 20.0
    post_connect_grace_seconds: float = 1.0
    max_play_seconds: float = 300.0
    media_volume: int | None = 15


@dataclass(frozen=True)
class AppConfig:
    devices: list[DeviceConfig]
    call: CallConfig


def _read_number(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"call.{key} must be a number") from exc


def _read_int(data: dict[str, Any], key: str, default: int | None) -> int | None:
    value = data.get(key, default)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"call.{key} must be an integer or null") from exc


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or os.getenv("AUTOCALLBOT_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config/devices.example.json to config/devices.json first."
        )

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    devices: list[DeviceConfig] = []
    for item in raw.get("devices", []):
        if not item.get("id") or not item.get("serial"):
            raise ValueError("Each device must include id and serial")
        devices.append(
            DeviceConfig(
                id=str(item["id"]),
                serial=str(item["serial"]),
                default_sim=int(item.get("default_sim", 0)),
                enabled=bool(item.get("enabled", True)),
            )
        )

    enabled_devices = [device for device in devices if device.enabled]
    if not enabled_devices:
        raise ValueError("At least one enabled device is required")

    call_raw = raw.get("call", {})
    call = CallConfig(
        poll_interval_seconds=_read_number(call_raw, "poll_interval_seconds", 1.0),
        invalid_hangup_seconds=_read_number(call_raw, "invalid_hangup_seconds", 8.0),
        no_answer_timeout_seconds=_read_number(call_raw, "no_answer_timeout_seconds", 20.0),
        post_connect_grace_seconds=_read_number(call_raw, "post_connect_grace_seconds", 1.0),
        max_play_seconds=_read_number(call_raw, "max_play_seconds", 300.0),
        media_volume=_read_int(call_raw, "media_volume", 15),
    )
    return AppConfig(devices=enabled_devices, call=call)
