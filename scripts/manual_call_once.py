from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autocallbot.config import AppConfig, CallConfig, DeviceConfig
from autocallbot.models import TaskStatus
from autocallbot.service import CallManager


FINISHED_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.INVALID_OR_STOPPED,
    TaskStatus.NO_ANSWER,
    TaskStatus.HUNG_UP,
    TaskStatus.FAILED,
}


async def run_once(args: argparse.Namespace) -> int:
    config = AppConfig(
        devices=[
            DeviceConfig(
                id=args.device_id,
                serial=args.serial,
                default_sim=args.sim,
                enabled=True,
            )
        ],
        call=CallConfig(
            poll_interval_seconds=args.poll_interval,
            invalid_hangup_seconds=args.invalid_hangup_seconds,
            no_answer_timeout_seconds=args.no_answer_timeout,
            post_connect_grace_seconds=args.post_connect_grace,
            max_play_seconds=max(args.play_seconds, 1),
            media_volume=args.media_volume,
        ),
    )
    manager = CallManager(config)
    task = await manager.start_call(
        phone=args.phone,
        sim=args.sim,
        audio_path=args.audio_path,
        play_seconds=args.play_seconds,
    )
    if not task:
        print(json.dumps({"status": "busy", "message": "device is busy"}, ensure_ascii=False), flush=True)
        return 2

    last_status: TaskStatus | None = None
    while True:
        status = await manager.find_status(task_id=task.task_id)
        if status is None:
            print(json.dumps({"status": "failed", "message": "task disappeared"}, ensure_ascii=False), flush=True)
            return 1
        if status.status != last_status:
            print(status.model_dump_json(), flush=True)
            last_status = status.status
        if status.status in FINISHED_STATUSES:
            return 0 if status.status == TaskStatus.COMPLETED else 1
        await asyncio.sleep(args.poll_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one real outbound call through AutoCallBot.")
    parser.add_argument("--serial", required=True, help="ADB serial, e.g. 10.0.0.244:5555")
    parser.add_argument("--phone", required=True, help="Phone number to dial")
    parser.add_argument("--audio-path", required=True, help="Audio path on Android device")
    parser.add_argument("--sim", type=int, default=0, help="SIM slot")
    parser.add_argument("--device-id", default="manual-device", help="Device id used in status output")
    parser.add_argument("--play-seconds", type=float, default=6, help="Seconds to wait after starting playback")
    parser.add_argument("--no-answer-timeout", type=float, default=25, help="Seconds to wait before no-answer")
    parser.add_argument("--invalid-hangup-seconds", type=float, default=8, help="Short hangup threshold")
    parser.add_argument("--post-connect-grace", type=float, default=1, help="Delay before audio playback after connect")
    parser.add_argument("--poll-interval", type=float, default=1, help="Status polling interval")
    parser.add_argument("--media-volume", type=int, default=15, help="Android media volume")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run_once(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
