from autocallbot.adb import (
    CallState,
    build_sms_intent_args,
    find_resource_bounds,
    is_connect_success,
    is_missing_device_error,
    is_tcp_serial,
    parse_bt_sco_active,
    parse_call_snapshot,
    parse_call_state,
)


def test_parse_call_state_prefers_offhook() -> None:
    output = """
      mCallState=0
      mCallState=2
    """
    assert parse_call_state(output) == CallState.OFFHOOK


def test_parse_call_state_reads_ringing() -> None:
    assert parse_call_state("mCallState=1") == CallState.RINGING


def test_parse_call_state_defaults_idle() -> None:
    assert parse_call_state("no call state here") == CallState.IDLE


def test_parse_call_snapshot_waits_for_precise_active_state() -> None:
    dialing = """
      mCallState=2
      mPreciseCallState=Ringing call state: -1, Foreground call state: 3, Background call state: -1
    """
    active = """
      mCallState=2
      mPreciseCallState=Ringing call state: -1, Foreground call state: 1, Background call state: -1
    """

    assert parse_call_snapshot(dialing).is_active is False
    assert parse_call_snapshot(active).is_active is True


def test_parse_bt_sco_active_reads_active_communication_device() -> None:
    output = "Active communication device: AudioDeviceInfo: type:bt_sco name:AutoCallBot-BT"
    assert parse_bt_sco_active(output) is True
    assert parse_bt_sco_active("Active communication device: type:built_in_earpiece") is False


def test_is_tcp_serial_detects_network_adb_devices() -> None:
    assert is_tcp_serial("10.0.0.117:5555") is True
    assert is_tcp_serial("phone.local:5555") is True
    assert is_tcp_serial("485edb64") is False


def test_is_connect_success_accepts_adb_connected_messages() -> None:
    assert is_connect_success("connected to 10.0.0.117:5555\n") is True
    assert is_connect_success("already connected to 10.0.0.117:5555\n") is True
    assert is_connect_success("failed to connect to 10.0.0.117:5555\n") is False


def test_is_missing_device_error_reads_common_adb_failures() -> None:
    assert is_missing_device_error("adb: device '10.0.0.117:5555' not found") is True
    assert is_missing_device_error("device offline") is True
    assert is_missing_device_error("some other adb failure") is False


def test_build_sms_intent_args_matches_marketing_gateway_payload() -> None:
    command = build_sms_intent_args("13800138000", "测试短信内容", 1)

    assert command[:6] == ["shell", "am", "start", "-a", "android.intent.action.SENDTO", "-d"]
    assert "smsto:13800138000" in command
    assert command[command.index("--es") + 1] == "sms_body"
    assert command[command.index("sms_body") + 1] == "测试短信内容"
    assert command[command.index("com.android.phone.extra.slot") + 1] == "1"


def test_find_resource_bounds_reads_uiautomator_node() -> None:
    xml = """
    <hierarchy>
      <node resource-id="com.android.mms:id/send_button" bounds="[912,1396][1008,1461]" />
    </hierarchy>
    """

    assert find_resource_bounds(xml, "com.android.mms:id/send_button") == (912, 1396, 1008, 1461)
