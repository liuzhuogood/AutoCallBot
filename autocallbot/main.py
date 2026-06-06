from __future__ import annotations

from fastapi import FastAPI, HTTPException

from autocallbot.logging import setup_logging
from autocallbot.models import BusyResponse, CallRequest, CallResponse, SmsRequest, SmsResponse, SmsStatus
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


@app.post("/sms", response_model=SmsResponse, responses={409: {"model": BusyResponse}})
async def sms(request: SmsRequest) -> SmsResponse:
    result = await service.send_sms(phone=request.phone, content=request.content, sim=request.sim)
    if result is None:
        raise HTTPException(status_code=409, detail={"status": "busy", "message": "phone is busy"})
    if result.status == SmsStatus.FAILED:
        raise HTTPException(status_code=500, detail=model_to_dict(result))
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
