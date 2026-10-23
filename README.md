# 口播停顿重塑器

一个本地运行的口播音频工具：上传完整配音音频后，自动识别停顿位置，自动加长过短停顿，生成一条新的完整音频 `edited_voice.wav`。同时保留复审区，可以批量或逐个微调停顿时间后重新导出。
<img width="1485" height="1289" alt="image" src="https://github.com/user-attachments/assets/4a7feeae-ca1e-4417-bd5d-845a13ec0250" />


## 功能

- 本地上传音频，不上传云端
- 自动识别音频中的静音停顿
- 自动按风格优化停顿时长
- 一键批量调节所有停顿
- 单个停顿滑块微调
- 导出完整音频 `edited_voice.wav`
- 支持蓝白多巴胺风格 Web UI

## 技术栈

- 前端：React + Vite + Wavesurfer.js
- 后端：FastAPI + ffmpeg
- 音频处理：ffmpeg `silencedetect` + 重新拼接静音间隙

## 环境要求

请先安装：

- Node.js 18+
- Python 3.10+
- ffmpeg，并确保命令行可直接运行 `ffmpeg` 和 `ffprobe`

## 安装依赖

### 前端依赖

```bash
npm install
```

### 后端依赖

建议使用虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

## 启动项目

### 方式一：Windows 一键启动

双击：

```text
一键启动.bat
```

或运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

> 注意：仓库里的 `start.ps1` 默认写的是当前开发机的运行时路径。如果分享给朋友或换电脑使用，建议根据自己的 Python/Node 路径调整脚本，或者使用方式二手动启动。

### 方式二：手动启动

启动后端：

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

启动前端：

```bash
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173/
```

## 使用流程

1. 上传完整口播音频
2. 选择停顿风格：短视频紧凑 / 自然口播 / 慢速旁白
3. 点击“自动优化并生成音频”
4. 先试听/下载自动生成的 `edited_voice.wav`
5. 如果整体不满意，使用“一键批量调节所有停顿”
6. 如果局部不满意，单独调节某个停顿滑块
7. 点击“微调后重新导出”

## 输出位置

生成文件默认在：

```text
workspace/outputs/
```

上传文件默认在：

```text
workspace/uploads/
```

这些运行产物不会被 Git 跟踪。

## 目录结构

```text
voice-splitter/
  backend/              # FastAPI 后端和音频处理逻辑
  frontend/src/         # React 前端源码
  workspace/            # 本地上传和输出目录
  index.html            # Vite 入口
  package.json          # 前端依赖和脚本
  start.ps1             # Windows PowerShell 启动脚本
  一键启动.bat          # Windows 双击启动器
```

## 隐私说明

该工具默认在本地处理音频，不会主动上传你的音频到云端。
