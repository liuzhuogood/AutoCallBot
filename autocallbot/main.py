from __future__ import annotations

from fastapi import FastAPI, HTTPException

from autocallbot.logging import setup_logging
from autocallbot.models import BusyResponse, CallRequest, CallResponse
from autocallbot.service import CallService


setup_logging()

app = FastAPI(title="AutoCallBot", version="0.1.0")
service = CallService()


@app.post("/call", response_model=CallResponse, responses={409: {"model": BusyResponse}})
async def call(request: CallRequest) -> CallResponse:
    result = await service.call(
        phone=request.phone,
        audio_path=request.audio_path,
        sim=request.sim,
        play_seconds=request.play_seconds,
    )
    if result is None:
        raise HTTPException(status_code=409, detail={"status": "busy", "message": "phone is busy"})
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
