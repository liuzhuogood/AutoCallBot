from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class CallStatus(str, Enum):
    COMPLETED = "completed"
    INVALID_OR_STOPPED = "invalid_or_stopped"
    NO_ANSWER = "no_answer"
    HUNG_UP = "hung_up"
    FAILED = "failed"


class SmsStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"


class CallRequest(BaseModel):
    phone: str = Field(..., min_length=3, description="Phone number to dial")
    audio_path: str = Field(..., min_length=1, description="MP3 path on this Raspberry Pi")
    sim: int | None = Field(default=None, ge=0, description="SIM slot, default uses config.DEFAULT_SIM")
    play_seconds: float | None = Field(default=None, gt=0, description="Max playback/call seconds")


class CallResponse(BaseModel):
    status: CallStatus
    message: str
    call_id: str
    phone: str
    device_id: str
    audio_path: str
    play_seconds: float
    started_at: str
    ended_at: str
    connected_at: str | None = None
    error: str | None = None


class SmsRequest(BaseModel):
    phone: str = Field(..., min_length=3, description="Phone number to receive SMS")
    content: str = Field(..., min_length=1, max_length=500, description="SMS content")
    sim: int | None = Field(default=None, ge=0, description="SIM slot, default uses config.DEFAULT_SIM")


class SmsResponse(BaseModel):
    status: SmsStatus
    message: str
    sms_id: str
    phone: str
    device_id: str
    started_at: str
    ended_at: str
    error: str | None = None


class BusyResponse(BaseModel):
    status: Literal["busy"]
    message: str
