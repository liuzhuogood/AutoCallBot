import json

from autocallbot.config import load_config


def test_load_config_keeps_enabled_devices(tmp_path) -> None:
    path = tmp_path / "devices.json"
    path.write_text(
        json.dumps(
            {
                "devices": [
                    {"id": "a", "serial": "serial-a", "enabled": True},
                    {"id": "b", "serial": "serial-b", "enabled": False},
                ],
                "call": {"media_volume": None},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert [device.id for device in config.devices] == ["a"]
    assert config.call.media_volume is None
