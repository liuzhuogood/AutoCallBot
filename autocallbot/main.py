from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from autocallbot.config import load_config
from autocallbot.models import BusyResponse, CallRequest, CallResponse, StatusResponse
from autocallbot.service import CallManager


app = FastAPI(title="AutoCallBot", version="0.1.0")
manager = CallManager(load_config())


@app.post("/call", response_model=CallResponse, responses={409: {"model": BusyResponse}})
async def call(request: CallRequest) -> CallResponse:
    audio_path = request.resolved_audio_path()
    if not audio_path:
        raise HTTPException(status_code=422, detail="audio_path is required")

    task = await manager.start_call(
        phone=request.phone,
        sim=request.sim,
        audio_path=audio_path,
        play_seconds=request.play_seconds,
    )
    if not task:
        raise HTTPException(status_code=409, detail={"status": "busy", "message": "all devices are busy"})
    return CallResponse(
        status="ok",
        message="dialing started",
        task_id=task.task_id,
        device_id=task.device.id,
    )


@app.get("/status", response_model=StatusResponse)
async def status(
    task_id: str | None = Query(default=None),
    phone: str | None = Query(default=None),
) -> StatusResponse:
    result = await manager.find_status(task_id=task_id, phone=phone)
    if not result:
        raise HTTPException(status_code=404, detail="task not found")
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
