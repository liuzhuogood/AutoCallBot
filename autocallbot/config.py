from __future__ import annotations

from pathlib import Path


# 树莓派控制的一台安卓手机配置。
# DEVICE_ID 仅用于日志和接口返回，方便区分当前外呼设备。
DEVICE_ID = "phone-a"
# ADB_SERIAL 是安卓手机的 ADB 设备号；网络 ADB 使用 ip:port，例如 10.0.0.117:5555。
ADB_SERIAL = "10.0.0.114:5555"
# 默认 SIM 卡槽；请求里不传 sim 时使用该值。
DEFAULT_SIM = 0

# 短信发送配置。
# 通过 Android 短信 Intent 写入手机号和内容，再用按键事件确认发送。
SMS_COMPOSE_WAIT_SECONDS = 1.0
# 发送前唤醒屏幕，避免短信 App 打开后被锁屏或通知面板遮挡。
SMS_WAKE_SCREEN_BEFORE_SEND = True
# 默认短信 App 发送按钮资源 ID；优先动态读取按钮坐标，避免键盘弹出后固定坐标失效。
SMS_SEND_BUTTON_RESOURCE_ID = "com.android.mms:id/send_button"
# 可选按键确认；当前 vivo 短信 App 用按键会误触添加联系人，默认只用坐标点击。
SMS_CONFIRM_KEYEVENTS = []
# 可选兜底点击坐标，格式为 [(x, y)]；默认依赖 SMS_SEND_BUTTON_RESOURCE_ID 动态定位。
SMS_CONFIRM_TAPS = []
# 多个确认按键之间的间隔。
SMS_KEYEVENT_INTERVAL_SECONDS = 0.2
# 单次短信 ADB 操作超时时间。
SMS_SEND_TIMEOUT_SECONDS = 20.0

# 外呼流程控制参数。
# 轮询手机通话状态的间隔，越小越灵敏，但 ADB 调用越频繁；3.5mm 模式下可适当调低减少接通后空白。
POLL_INTERVAL_SECONDS = 0.3
# 拨号后很快回到空闲状态时，低于该秒数认为更像空号、拦截或异常结束。
INVALID_HANGUP_SECONDS = 8.0
# 拨号后等待接听的最长时间，超过后返回无人接听。
NO_ANSWER_TIMEOUT_SECONDS = 20.0
# 识别为已接通后的固定等待时间。
# 3.5mm 模式不依赖蓝牙路由，可设为 0；切回蓝牙模式时建议保留 1 秒左右，给 bt_sco 通话路由稳定时间。
POST_CONNECT_GRACE_SECONDS = 0.0
# 单次通话允许播放的最长秒数；请求里的 play_seconds 不会超过该上限。
MAX_PLAY_SECONDS = 30.0
# 拨号前设置安卓手机媒体音量；设为 None 表示不主动调整。
MEDIA_VOLUME: int | None = 15
# 蓝牙模式下是否要求 Android 通话路由必须是 bt_sco。
REQUIRE_BT_SCO = True
# 蓝牙模式下等待 bt_sco 路由出现的最长秒数。
BT_SCO_WAIT_SECONDS = 8.0

# 树莓派本机音频播放配置。
# "bluetooth" 表示走 BlueALSA SCO/HFP；"alsa" 表示走本机 ALSA 设备，例如 3.5mm 耳机口。
AUDIO_OUTPUT_BACKEND = "alsa"
# ffmpeg 播放增益；3.5mm 或蓝牙音量偏小时可以调大。
PLAYBACK_VOLUME = 1.0
# 音频文件短于 play_seconds 时是否循环播放，开启后会循环播满请求时长。
PLAYBACK_LOOP_FOREVER = True
# ffmpeg 命令路径；部署环境不在 PATH 中时可改成绝对路径。
FFMPEG_PATH = "ffmpeg"

# 蓝牙 BlueALSA SCO 播放配置。
# PHONE_MAC 是与树莓派配对的手机蓝牙 MAC。
PHONE_MAC = "B8:D4:3E:6A:AF:84"
# BlueALSA 暴露给 ffmpeg/ALSA 的 SCO PCM 设备。
BLUEALSA_PCM = f"bluealsa:SRV=org.bluealsa,DEV={PHONE_MAC},PROFILE=sco,VOL=100+,SOFTVOL=yes"
# 蓝牙 SCO 常用 8k/16k 采样率；当前按实测使用 16k。
SCO_RATE = 16000
# bluealsa-aplay 用于检查当前是否存在可播放的 SCO 设备。
BLUEALSA_APLAY_PATH = "bluealsa-aplay"

# 本机 3.5mm / ALSA 播放配置。
# Raspberry Pi OS 通常会暴露 Headphones 这张 ALSA 卡；如设备名不同，改这里即可。
AUDIO_ALSA_PCM = "default"
# 3.5mm 输出的采样率；保持 16k 便于和通话音频链路一致。
ALSA_RATE = 48000
# aplay 用于检查本机 ALSA 播放设备。
APLAY_PATH = "aplay"

# 本地日志配置。
LOG_DIR = Path("data/logs")
LOG_LEVEL = "INFO"
LOG_ROTATION = "20 MB"
LOG_RETENTION = "14 days"
