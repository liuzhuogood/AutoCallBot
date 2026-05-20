from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    DIALING = "dialing"
    RINGING = "ringing"
    CONNECTED = "connected"
    PLAYING = "playing"
    COMPLETED = "completed"
    INVALID_OR_STOPPED = "invalid_or_stopped"
    NO_ANSWER = "no_answer"
    HUNG_UP = "hung_up"
    FAILED = "failed"


class CallRequest(BaseModel):
    phone: str = Field(..., min_length=3, description="Phone number to dial")
    sim: int | None = Field(default=None, ge=0, description="SIM slot, default uses device config")
    audio_path: str | None = Field(
        default=None,
        min_length=1,
        description="Audio path on Android device, e.g. /sdcard/voice.mp3",
    )
    wav_path: str | None = Field(
        default=None,
        min_length=1,
        description="Deprecated alias for audio_path.",
    )
    play_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Optional playback wait time. Defaults to call.max_play_seconds.",
    )

    def resolved_audio_path(self) -> str | None:
        return self.audio_path or self.wav_path


class CallResponse(BaseModel):
    status: Literal["ok"]
    message: str
    task_id: str
    device_id: str


class BusyResponse(BaseModel):
    status: Literal["busy"]
    message: str


class StatusResponse(BaseModel):
    task_id: str
    phone: str
    device_id: str
    sim: int
    audio_path: str
    play_seconds: float
    status: TaskStatus
    message: str
    started_at: str
    updated_at: str
    connected_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
