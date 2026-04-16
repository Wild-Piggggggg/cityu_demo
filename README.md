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

**有 sudo 权限（Ubuntu/Debian）**：
```bash
sudo apt update && sudo apt install -y ffmpeg
```

**无 sudo / RHEL 系（推荐 conda-forge）**：
```bash
conda install -c conda-forge -y ffmpeg
```

验证：
```bash
ffmpeg -version | head -1
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
python app.py --transport webrtc
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
- **能打开页面但视频黑屏（尤其是用 SSH 端口转发访问）**：WebRTC 的媒体流是端到端 UDP/DTLS 直连，**不会走 SSH `-L`/`-R` 的 TCP 隧道**；因此“信令 HTTP 能通”不等于“媒体能通”。解决思路：1）用公网 IP/域名直连服务器，并在防火墙/安全组放通 WebRTC 所需 UDP（以及 `--listenport` 对应的 TCP）；2）在受限网络/NAT 环境下配置 TURN（推荐走 443/TCP 或 443/TLS），并用 `--ice_servers` 指定可用的 STUN/TURN（`app.py` 默认已带 `stun:stun.cloudflare.com:3478`）。
- **`/voice_chat` 报错找不到 ffmpeg**：先把 ffmpeg 加入 `PATH`，确保 `ffmpeg -version` 可执行。
- **启用 speaking 后一直卡在 `Processing...`**：`/voice_chat` 默认使用 `speech_recognition` 的 **Google Web Speech API** 做英文 STT，该能力对网络环境有要求——需要你的**服务器或本地**具备可用的出网能力，或开启**特定网络环境的节点/代理**以访问 Google 语音服务。若网络不满足，后端常见日志为 `Google STT service error` / `Network is unreachable`，前端就会停留在 `processing` 状态。解决思路：配置可访问 Google 的网络节点/代理；或将 STT 替换为本地离线方案（如 Whisper/Vosk）/自建 ASR 服务。
- **依赖安装失败**：优先确认 `torch`/CUDA 版本匹配；然后再装其余依赖。部分库在 Windows 可能需要对应的 wheel 或编译工具链。

---

## 安装问题排查（实测记录）

以下是在 Linux 服务器（RHEL9 / Miniconda + Python 3.10）上逐一踩过的安装坑及解决方案。

### 1. `lws` 构建失败：`No module named 'numpy'`

```
ERROR: Failed to build 'lws' when getting requirements to build wheel
ModuleNotFoundError: No module named 'numpy'
```

**原因**：`lws` 在 pip 的隔离构建环境中无法找到 `numpy`（构建依赖声明不完整）。

**解决**：先装 `numpy`，再关闭隔离构建安装 `lws`：

```bash
pip install -U pip setuptools wheel
pip install -U "numpy<2"
pip install --no-build-isolation lws
pip install -r requirements.txt
```

---

### 2. `chumpy` 构建失败：`No module named 'pip'`

```
ERROR: Failed to build 'chumpy' when getting requirements to build wheel
ModuleNotFoundError: No module named 'pip'
```

**原因**：`chumpy` 是老包，`setup.py` 里直接 `import pip`，但 pip 的隔离构建环境里没有 `pip`。

**解决**：关闭隔离构建：

```bash
pip install --no-build-isolation "chumpy==0.70"
pip install -r requirements.txt
```

---

### 3. `PyAudio` 构建失败：`portaudio.h: No such file or directory`

```
fatal error: portaudio.h: No such file or directory
ERROR: Failed building wheel for PyAudio
```

**原因**：`PyAudio` 需要编译 C 扩展，依赖 PortAudio 系统开发包。

**解决（推荐 conda-forge）**：

```bash
conda install -c conda-forge -y portaudio pyaudio
pip install -r requirements.txt
```

**或安装系统包（需 sudo）**：

```bash
# RHEL/Rocky 9
sudo dnf install -y portaudio portaudio-devel
# Ubuntu/Debian
sudo apt-get install -y portaudio19-dev
pip install pyaudio
```

---

### 4. 启动报错：`Ninja is required to load C++ extensions`

```
RuntimeError: Ninja is required to load C++ extensions (pip install ninja to get it)
```

**原因**：`ernerf` 的 CUDA C++ 扩展（`_raymarching_face` 等）需要 `ninja` 做 JIT 编译，但未安装。

**解决**：`ninja` 已加入 `requirements.txt`，正常 `pip install -r requirements.txt` 即可。若仍报错可手动：

```bash
conda install -y ninja
# 或
pip install ninja
```

---

### 5. 启动报错：`ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`

```
ImportError: Using SOCKS proxy, but the 'socksio' package is not installed.
Make sure to install httpx using `pip install httpx[socks]`.
```

**原因**：环境变量中设置了 SOCKS 代理（`ALL_PROXY` 等），但缺少 `socksio`。

**解决**：`httpx[socks]` 已加入 `requirements.txt`。代码层面 `nerfreal.py` 已在加载 ASR 模型前自动清除代理变量，如仍有问题可手动：

```bash
pip install "httpx[socks]"
unset ALL_PROXY HTTPS_PROXY HTTP_PROXY
```

---

### 6. ASR 模型下载失败（网络不通/超时）

**原因**：服务器无法直接访问 HuggingFace，或代理配置问题。

**解决**：手动下载到本地 `models/asr_model/`（代码会自动识别本地路径，不再走网络）：

```bash
# 方式一：huggingface-cli + 国内镜像
HF_ENDPOINT=https://hf-mirror.com \
  hf download cpierse/wav2vec2-large-xlsr-53-esperanto \
  --local-dir models/asr_model 

# 方式二：wget 逐文件下载
mkdir -p models/asr_model
BASE=https://hf-mirror.com/cpierse/wav2vec2-large-xlsr-53-esperanto/resolve/main
for f in config.json preprocessor_config.json tokenizer_config.json \
          vocab.json special_tokens_map.json pytorch_model.bin; do
  wget -c "$BASE/$f" -O "models/asr_model/$f"
done
```

---

### 7. 浏览器麦克风权限被拒绝

```
Unable to access the microphone.
Please allow microphone permission in your browser and try again.
```

**原因**：浏览器的 `getUserMedia` API 只在**安全上下文**（`https://` 或 `localhost`）下允许麦克风访问，通过局域网 IP 的 `http://` 访问会被直接拒绝。

**解决方案（三选一）**：

**方案 A（最快，仅调试用）**：Chrome 临时放行
在浏览器地址栏打开 `chrome://flags/#unsafely-treat-insecure-origin-as-secure`，将服务地址（如 `http://10.x.x.x:8010`）填入并启用，重启浏览器。

**方案 B（无需改代码）**：SSH 本地端口转发
在本地电脑执行：
```bash
ssh -NL 8010:localhost:8010 user@<服务器IP>
```
然后通过 `http://localhost:8010` 访问，浏览器视为本地地址。

**方案 C（推荐，多人使用）**：启用自签名 HTTPS
```bash
# 生成证书（仅需一次）
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout ssl/key.pem -out ssl/cert.pem -days 365 \
  -subj "/CN=<服务器IP>" -addext "subjectAltName=IP:<服务器IP>"

# 正常启动，代码会自动识别 ssl/ 目录并启用 HTTPS
python app.py --transport webrtc
```
浏览器提示证书不受信任时点击"高级 → 继续访问"，之后麦克风权限可正常请求。

---

### 8. `ffmpeg` 权限报错（`[Errno 13] Permission denied: 'ffmpeg'`）

**原因**：`ffmpeg` 未安装或不在 conda 环境的 `PATH` 中，`subprocess` 调用时报权限拒绝。

**解决**：在 conda 环境中安装 ffmpeg：

```bash
conda install -c conda-forge ffmpeg -n cityu_human -y
# 验证
ffmpeg -version | head -1
```

---

### 9. 音画不同步（嘴型快、声音慢）

**原因（三处叠加）**：
1. 音频轨和视频轨的时钟起点独立初始化，产生起始偏差
2. WebRTC 视频时间戳以 30fps 步长递进，但渲染循环实际跑 25fps，时间戳漂移
3. TTS 音频帧无背压限速，可无限超前于对应视频帧堆积

**解决**：已在代码层面修复（`webrtc.py` + `nerfreal.py`），无需用户操作：
- 音视频共享同一起始时钟
- `VIDEO_PTIME` 改为 `1/25` 匹配实际渲染帧率
- 音频队列加入与视频队列联动的背压控制

## 打包（可选）

提供了 `build.bat` 用于 PyInstaller 打包（需要你先准备好 conda 环境并按脚本修改环境名）。

## 致谢

- 上游项目：LiveTalking（原作者/社区贡献者）
- 语音识别：`speech_recognition`（Google Web Speech API）
- WebRTC：`aiortc`
