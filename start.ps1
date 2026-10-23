$ProjectRoot = "D:\2026-10-22-16-14-07\voice-splitter"
$BackendRoot = Join-Path $ProjectRoot "backend"
$PythonExe = "C:\Users\Administrator\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe"
$NodeExe = "C:\Users\Administrator\.workbuddy-ai\binaries\node\versions\22.22.2-6\node.exe"
$NpmCli = "C:\Users\Administrator\.workbuddy-ai\binaries\node\versions\22.22.2-6\node_modules\npm\bin\npm-cli.js"

Write-Host "Starting Voice Pause Editor..." -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$BackendRoot'; & '$PythonExe' -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$ProjectRoot'; & '$NodeExe' '$NpmCli' run dev"
)

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173/"

Write-Host "Done. If the page does not open automatically, visit: http://127.0.0.1:5173/" -ForegroundColor Green
