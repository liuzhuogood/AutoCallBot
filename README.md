# AutoCallBot

AutoCallBot 是一个安卓 ADB 自动外呼机器人 MVP。

当前推荐方案不再依赖“手机外放 + 麦克风收音”，而是采用树莓派 3B 模拟蓝牙耳机：

1. FastAPI 接收 `/call` 外呼请求。
2. Python 通过 ADB 控制安卓手机拨号、等待接通、挂断。
3. 手机通话音频路由切到 `AutoCallBot-BT`。
4. 树莓派通过 BlueALSA HFP/SCO 把 MP3 注入到通话上行音频。
5. 播放完成后服务端挂断电话，并可通过 `/status` 查询任务状态。

方案说明以 [树莓派 3B 模拟蓝牙耳机外呼可行性验证方案](docs/raspberry-pi-bluetooth-headset-feasibility.md) 为准；已跑通环境和操作命令见 [树莓派蓝牙耳机外呼音频注入跑通指引](docs/raspberry-pi-bluetooth-headset-runbook.md)。

## 当前状态

项目目前包含两部分：

- 已实现的基础外呼服务：设备池、ADB 拨号、接通判断、播放等待、挂断、状态查询。
- 已验证的树莓派蓝牙耳机方案：树莓派作为 `AutoCallBot-BT`，通过 HFP/SCO playback 播放 MP3 到通话链路。

后续代码集成时，建议把树莓派封装成独立音频节点，由外呼服务在电话接通并确认 `bt_sco` 路由后，通过 SSH/systemd 调用树莓派播放音频。

## 功能

- `POST /call` 发起外呼，支持指定 SIM 卡和音频文件路径
- 多设备池：自动选择空闲安卓手机，全部占用时返回 `409 busy`
- 轮询 `dumpsys telephony.registry` 的 `mCallState` 和精确通话状态
- 优先用 `Foreground call state: 1` 判定为已接通
- 按 `play_seconds` 或配置的播放等待窗口自动挂断
- 播放期间持续检测通话状态，提前挂断会返回 `hung_up`
- 初步判断短时间挂断、无人接听
- `GET /status` 按 `task_id` 或 `phone` 查询任务状态

注意：当前代码里的 `audio_path` 仍是外呼任务的音频参数。旧版实现会让安卓手机打开该路径播放；树莓派方案集成后，这个参数应改为服务端/树莓派可访问的 MP3 文件，并由树莓派播放到 BlueALSA SCO。

## 推荐链路

```mermaid
flowchart LR
    A["FastAPI /call"] --> B["ADB 控制安卓手机拨号"]
    B --> C["等待 mForegroundCallState=1"]
    C --> D["确认 Android 通话路由为 bt_sco"]
    D --> E["检查树莓派 BlueALSA SCO playback"]
    E --> F["树莓派 ffmpeg 播放 MP3 到 HFP/SCO"]
    F --> G["ADB 挂断电话"]
```

树莓派只负责蓝牙音频播放和可选录音；拨号、通话状态判断、任务状态管理、挂断仍由 Python/ADB 完成。

## 树莓派蓝牙耳机方案

当前已验证环境：

| 项 | 值 |
| --- | --- |
| 蓝牙设备名 | `AutoCallBot-BT` |
| 树莓派 SSH 用户 | `liuzhuo` |
| 树莓派当前 WiFi IP | `10.0.0.16` |
| 已配对手机 | `vivo S9` |
| 手机蓝牙 MAC | `B8:D4:3E:6A:AF:84` |
| BlueALSA profile | `hfp-hf` |
| SCO 编码 | `mSBC` |
| SCO 采样率 | `16000 Hz` |

关键验证点：

- 手机蓝牙详情里必须启用“通话音频”。
- 通话中 Android 音频路由必须是 `bt_sco`。
- `bluealsa-aplay -L` 必须能看到 `PROFILE=sco` 的 `capture` 和 `playback`。
- `ffmpeg` 日志里应出现 `hfphf/sink: Starting IO loop`。
- 接听方能听到树莓派播放的测试音或 MP3，才说明上行注入真正成功。

推荐先按 runbook 完成手动验证，再做代码自动化：

```bash
bluealsa-aplay -L

sudo systemd-run \
  --unit=autocallbot-mp3-loop \
  --description='AutoCallBot MP3 loop to BlueALSA SCO' \
  --collect \
  --property=RuntimeMaxSec=610 \
  /usr/bin/ffmpeg \
    -hide_banner -nostdin \
    -stream_loop -1 -re \
    -i /tmp/1779194620494.mp3 \
    -t 600 \
    -af volume=4.0,aresample=16000 \
    -f alsa -ac 1 -ar 16000 \
    'bluealsa:SRV=org.bluealsa,DEV=B8:D4:3E:6A:AF:84,PROFILE=sco,VOL=100+,SOFTVOL=yes'
```

## 配置

复制配置示例：

```bash
cp config/devices.example.json config/devices.json
```

按实际手机修改 `serial`。可先用下面命令查看：

```bash
adb devices
```

示例：

```json
{
  "devices": [
    {
      "id": "phone-104",
      "serial": "10.0.0.104:5555",
      "default_sim": 0,
      "enabled": true
    },
    {
      "id": "phone-244",
      "serial": "10.0.0.244:5555",
      "default_sim": 0,
      "enabled": true
    }
  ],
  "call": {
    "poll_interval_seconds": 1.0,
    "invalid_hangup_seconds": 8.0,
    "no_answer_timeout_seconds": 20.0,
    "post_connect_grace_seconds": 1.0,
    "max_play_seconds": 300.0,
    "media_volume": 15
  }
}
```

`max_play_seconds` 是播放等待的默认上限。树莓派方案里建议请求传 `play_seconds`，值为实际音频时长加 1 到 2 秒，避免通话过早挂断或等待过久。

后续树莓派音频节点建议增加独立配置，例如：

```text
PI_HOST=10.0.0.16
PI_USER=liuzhuo
PHONE_MAC=B8:D4:3E:6A:AF:84
BLUEALSA_PCM=bluealsa:SRV=org.bluealsa,DEV=B8:D4:3E:6A:AF:84,PROFILE=sco,VOL=100+,SOFTVOL=yes
SCO_RATE=16000
PLAYBACK_VOLUME=4.0
MAX_PLAY_SECONDS=600
```

不要把 WiFi 密码、sudo 密码、SSH 私钥等敏感信息写入配置或日志。

## 启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn autocallbot.main:app --host 0.0.0.0 --port 8000
```

如果配置文件不放在默认路径，可用环境变量指定：

```bash
AUTOCALLBOT_CONFIG=/path/to/devices.json uvicorn autocallbot.main:app --port 8000
```

## 调用

```bash
curl -X POST http://127.0.0.1:8000/call \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800138000","sim":0,"audio_path":"/tmp/1779194620494.mp3","play_seconds":12}'
```

返回：

```json
{
  "status": "ok",
  "message": "dialing started",
  "task_id": "uuid",
  "device_id": "phone-104"
}
```

查询状态：

```bash
curl 'http://127.0.0.1:8000/status?task_id=uuid'
curl 'http://127.0.0.1:8000/status?phone=13800138000'
```

全部设备占用时：

```json
{
  "detail": {
    "status": "busy",
    "message": "all devices are busy"
  }
}
```

## 注意

- 当前首选方案是树莓派蓝牙耳机 HFP/SCO 注入，不建议继续按外放 + 麦克风收音方向投入。
- 本方案已经完成手动链路验证，但仍需代码集成树莓派音频节点。
- 如果 `bluealsa-aplay -L` 没有 `PROFILE=sco`，不要继续播放 MP3，先处理蓝牙连接或通话音频路由。
- 如果接听方听不到测试音，即使 BlueALSA playback 命令成功，也说明上行注入没有真正进入手机通话麦克风链路。
- 空号、停机、无人接听判断只是按通话状态和时间做初步推断。
