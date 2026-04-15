# CityU Human（实时交互数字人 / 英语口语教练）

本项目基于 **LiveTalking** 改造：在“实时音视频数字人（WebRTC/RTMP/推流）”能力之上，增加了**英语口语教练**相关能力（文本对话、语音识别 STT、Qwen/DashScope LLM 流式回复、可打断播报），用于课堂/演示/交互式口语练习等场景。

- **支持的数字人模型**：`ernerf` / `musetalk` / `wav2lip` / `ultralight`
- **交互方式**：浏览器 WebRTC、RTMP、WHIP/推流（见 `app.py --transport`）
- **英语口语教练**：
  - Web 端录音 → 服务器 `ffmpeg` 转码 → `speech_recognition`（Google Web Speech API）英文 STT → 英语教练 LLM → 数字人播报（`/voice_chat`）
  - 文本对话接口（`/human`，`type=chat` 会调用 Qwen 流式输出并分句驱动数字人）

> 说明：仓库里包含多个上游子模块（`ernerf/`、`wav2lip/`、`musetalk/` 等），各自也有 README。此 README 以**跑通本项目**为主。

## 演示页面入口

项目内置了多个前端示例页面，默认服务会把 `web/` 作为静态目录：

- WebRTC 主入口：`web/webrtcapi.html`
- CityU 定制页（如有）：`web/webrtcapi_cityu.html`
- ASR 示例：`web/webrtcapi-asr.html`、`web/asr/index.html`
- 推流/rtcpush 示例：`web/rtcpushapi.html`

启动服务后控制台会打印实际访问地址（形如 `http://localhost:8010/webrtcapi.html`）。

## 环境要求

- **Python**：建议 3.10+（你当前环境为 3.11 也可用，依赖较重时可能需要按报错微调）
- **GPU（推荐）**：NVIDIA CUDA（不同模型/推理速度差异很大）
- **ffmpeg（必需）**：语音接口 `/voice_chat` 会调用系统 `ffmpeg` 做转码
- **浏览器**：Chrome/Edge（用于 WebRTC）

## 快速开始（Windows 10 / PowerShell）

### 1）创建 Conda 环境并安装依赖

在项目根目录执行：

```bash
conda create -n cityu_human python=3.10 -y
conda activate cityu_human
python -m pip install -U pip
pip install -r requirements.txt
```

> 如果你有 CUDA，建议先按 PyTorch 官方说明安装与你本机 CUDA 匹配的 `torch/torchvision`，再安装 `requirements.txt` 其余依赖；否则可能出现 CUDA/torch 版本不匹配。

### 2）安装 ffmpeg

确保命令行可执行：

```bash
ffmpeg -version
```

（Windows 建议安装后把 `ffmpeg.exe` 加到 `PATH`。）

### 3）配置 LLM Key（DashScope/Qwen）

本项目调用 DashScope 兼容 OpenAI 的接口，默认从环境变量读取：

- `DASHSCOPE_API_KEY`：你的 DashScope Key

PowerShell 示例：

```powershell
$env:DASHSCOPE_API_KEY="你的DashScopeKey"
```

> 建议仅用环境变量，不要把 Key 写进代码/提交到 GitHub。

### 4）启动服务

默认 WebRTC：

```bash
python app.py --transport webrtc --listenport 8010
```

然后打开：

- `http://localhost:8010/webrtcapi.html`（或根据控制台提示的页面）

## 快速开始（Linux / Ubuntu 20.04+）

> 说明：Linux 下整体体验通常更稳定（CUDA/驱动/依赖更友好）。以下以 Ubuntu 为例，其他发行版可替换包管理器命令。

### 1）安装系统依赖（ffmpeg 等）

```bash
sudo apt update
sudo apt install -y ffmpeg
ffmpeg -version
```

### 2）创建 Conda 环境并安装 Python 依赖

在项目根目录执行：

```bash
conda create -n cityu_human python=3.10 -y
conda activate cityu_human
python -m pip install -U pip
pip install -r requirements.txt
```

> 如果你使用 NVIDIA GPU，请先按 PyTorch 官方说明安装与你 CUDA 版本匹配的 `torch/torchvision`，再安装 `requirements.txt` 其余依赖，避免 CUDA/torch 不匹配导致无法调用 GPU。

### 3）配置 LLM Key（DashScope/Qwen）

```bash
export DASHSCOPE_API_KEY="你的DashScopeKey"
```

### 4）启动服务并访问

```bash
python app.py --transport webrtc --listenport 8010
```

在本机浏览器打开：

- `http://localhost:8010/webrtcapi.html`

如果是远程 Linux 服务器（云主机）：

- **安全组/防火墙**：放通 `--listenport` 对应端口（默认 8010）
- **浏览器访问**：用 `http://<服务器IP>:8010/webrtcapi.html`

## 关键接口（后端）

后端基于 `aiohttp` 提供接口（代码在 `app.py`）：

- `POST /offer`：建立 WebRTC（浏览器 SDP 交换）
- `POST /human`：文本驱动数字人
  - `type=echo`：直接播报文本
  - `type=chat`：调用 LLM（Qwen）生成回复并分句推入数字人队列
- `POST /voice_chat`：**【英语口语教练】**上传浏览器录音（WebM），服务端 STT 后生成教练回复并驱动数字人播报
- `POST /is_speaking`：查询数字人是否还在说话（前端可轮询）

## 模型选择与常用参数

运行时可切换模型：

```bash
python app.py --model ernerf
python app.py --model musetalk
python app.py --model wav2lip
python app.py --model ultralight
```

其他常见参数（部分）：

- `--listenport`：HTTP 服务端口（默认 8010）
- `--max_session`：并发 session 数
- `--tts`：TTS 方案（默认 `edgetts`，见 `app.py` 参数）

## 目录结构（简版）

- `app.py`：主服务入口（WebRTC + HTTP API + 英语口语教练语音接口）
- `web/`：前端页面（WebRTC/推流/ASR 示例）
- `llm/`：LLM 相关封装与英语教练逻辑
- `ernerf/`、`wav2lip/`、`musetalk/`、`ultralight/`：各数字人模型子模块
- `models/`、`data/`：模型权重与示例数据（实际内容因环境而异）

## 常见问题

- **页面打不开/无视频**：确认端口 `--listenport` 未被占用；浏览器允许摄像头/麦克风权限；优先用 Chrome/Edge。
- **`/voice_chat` 报错找不到 ffmpeg**：先把 ffmpeg 加入 `PATH`，确保 `ffmpeg -version` 可执行。
- **依赖安装失败**：优先确认 `torch`/CUDA 版本匹配；然后再装其余依赖。部分库在 Windows 可能需要对应的 wheel 或编译工具链。

## 打包（可选）

提供了 `build.bat` 用于 PyInstaller 打包（需要你先准备好 conda 环境并按脚本修改环境名）。

## 致谢

- 上游项目：LiveTalking（原作者/社区贡献者）
- 语音识别：`speech_recognition`（Google Web Speech API）
- WebRTC：`aiortc`
