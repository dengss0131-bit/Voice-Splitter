# v2.3 智能一键启动

此版本在 v2.2 基础上升级 Windows 一键启动脚本：

- 自动检查 Node.js / npm
- 自动检查 Python 或 py launcher
- 自动检查 ffmpeg / ffprobe
- 如果缺少 node_modules，自动执行 npm install
- 如果缺少 Python 后端依赖，自动执行 pip install -r backend/requirements.txt
- 检查通过后自动启动后端和前端，并打开 http://127.0.0.1:5173/

如果缺少 Node.js、Python 或 ffmpeg，会在窗口中给出明确提示，不再静默失败。
