from __future__ import annotations

import sys

from loguru import logger

from autocallbot import config


def setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=config.LOG_LEVEL, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}")
    logger.add(
        config.LOG_DIR / "autocallbot.log",
        level=config.LOG_LEVEL,
        rotation=config.LOG_ROTATION,
        retention=config.LOG_RETENTION,
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
    )
