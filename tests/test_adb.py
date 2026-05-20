from autocallbot.adb import CallState, parse_bt_sco_active, parse_call_snapshot, parse_call_state


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
