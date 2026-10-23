$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $ProjectRoot "backend"

Write-Host "Starting Voice Pause Editor..." -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$BackendRoot'; python -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$ProjectRoot'; npm run dev"
)

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173/"

Write-Host "Done. If the page does not open automatically, visit: http://127.0.0.1:5173/" -ForegroundColor Green
