# AutoCallBot

AutoCallBot 是一个部署在树莓派上的单通道安卓自动外呼服务。

当前模型固定为：

```mermaid
flowchart LR
    A["POST /call"] --> B["ADB 拨号"]
    B --> C["等待电话接通"]
    C --> D["确认 Android 通话路由是 bt_sco"]
    D --> E["检查本机 BlueALSA SCO playback"]
    E --> F["本机 ffmpeg 播放 MP3 到 HFP/SCO"]
    F --> G["对方挂断或超时后 ADB 挂断"]
```

只做 `手机A -> 树莓派A`，不做多手机池、不做任务状态库、不做外部 JSON 配置。

## 配置

直接改 [autocallbot/config.py](/Users/liuzhuo/code/AutoCallBot/autocallbot/config.py) 顶部变量：

```python
ADB_SERIAL = "10.0.0.104:5555"
PHONE_MAC = "B8:D4:3E:6A:AF:84"
MAX_PLAY_SECONDS = 300.0
```

`audio_path` 是树莓派本机可访问的 MP3 路径，不是手机里的文件路径。

## 启动

开发启动：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn autocallbot.main:app --host 0.0.0.0 --port 8000
```

树莓派部署：

```bash
./scripts/deploy_pi.sh
```

部署脚本会安装 ADB、BlueALSA、ffmpeg、Python venv，并创建 `autocallbot.service`。

## 调用

```bash
curl -X POST http://127.0.0.1:8000/call \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800138000","audio_path":"/tmp/1779194620494.mp3","play_seconds":12}'
```

接口会等待本次外呼结束后返回最终结果。当前手机占用时返回 `409 busy`。

日志写入：

```text
data/logs/autocallbot.log
```

## 运行前检查

```bash
adb devices
bluealsa-aplay -L
```

关键条件：

- 手机蓝牙详情里启用“通话音频”。
- 通话中 Android 音频路由必须是 `bt_sco`。
- `bluealsa-aplay -L` 必须能看到配置的 `PHONE_MAC`、`PROFILE=sco` 和 `playback`。
- 接听方能听到树莓派播放的测试音或 MP3，才说明上行注入真正成功。

更完整的树莓派蓝牙配置和排障见 [docs/raspberry-pi-bluetooth-headset-runbook.md](/Users/liuzhuo/code/AutoCallBot/docs/raspberry-pi-bluetooth-headset-runbook.md)。
