from __future__ import annotations

from pathlib import Path


# Raspberry Pi + one Android phone.
DEVICE_ID = "phone-a"
ADB_SERIAL = "10.0.0.117:5555"
DEFAULT_SIM = 0

# Call flow.
POLL_INTERVAL_SECONDS = 1.0
INVALID_HANGUP_SECONDS = 8.0
NO_ANSWER_TIMEOUT_SECONDS = 20.0
POST_CONNECT_GRACE_SECONDS = 1.0
MAX_PLAY_SECONDS = 300.0
MEDIA_VOLUME: int | None = 15
REQUIRE_BT_SCO = True
BT_SCO_WAIT_SECONDS = 8.0

# Local BlueALSA playback on this Raspberry Pi.
PHONE_MAC = "B8:D4:3E:6A:AF:84"
BLUEALSA_PCM = f"bluealsa:SRV=org.bluealsa,DEV={PHONE_MAC},PROFILE=sco,VOL=100+,SOFTVOL=yes"
SCO_RATE = 16000
PLAYBACK_VOLUME = 4.0
FFMPEG_PATH = "ffmpeg"
BLUEALSA_APLAY_PATH = "bluealsa-aplay"

# Local logs.
LOG_DIR = Path("data/logs")
LOG_LEVEL = "INFO"
LOG_ROTATION = "20 MB"
LOG_RETENTION = "14 days"
