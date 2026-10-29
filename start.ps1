$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $ProjectRoot "backend"

function Test-Command($Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  return $null -ne $cmd
}

function Stop-WithMessage($Message) {
  Write-Host ""
  Write-Host $Message -ForegroundColor Red
  Write-Host ""
  Write-Host "Press any key to exit..." -ForegroundColor Yellow
  $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
  exit 1
}

Write-Host "Starting Voice Pause Editor..." -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Command "node")) {
  Stop-WithMessage "Node.js was not found. Please install Node.js first: https://nodejs.org/"
}

if (-not (Test-Command "npm")) {
  Stop-WithMessage "npm was not found. Please install Node.js/npm first: https://nodejs.org/"
}

if (-not (Test-Command "python")) {
  if (Test-Command "py") {
    $PythonCommand = "py"
  } else {
    Stop-WithMessage "Python was not found. Please install Python first: https://www.python.org/downloads/"
  }
} else {
  $PythonCommand = "python"
}

if (-not (Test-Command "ffmpeg")) {
  Stop-WithMessage "ffmpeg was not found. Please install ffmpeg and add it to PATH first. Download: https://www.gyan.dev/ffmpeg/builds/"
}

if (-not (Test-Command "ffprobe")) {
  Stop-WithMessage "ffprobe was not found. It is usually installed with ffmpeg. Please add ffmpeg/bin to PATH."
}

if (-not (Test-Path (Join-Path $ProjectRoot "node_modules"))) {
  Write-Host "Front-end dependencies were not found. Running npm install..." -ForegroundColor Yellow
  Set-Location $ProjectRoot
  npm install
  if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "npm install failed. Please check your network or npm configuration."
  }
}

Write-Host "Checking Python back-end dependencies..." -ForegroundColor Yellow
Set-Location $BackendRoot
$DependencyCheck = 'import importlib.util,sys; missing=[name for name in ["fastapi","uvicorn","multipart","pydantic"] if importlib.util.find_spec(name) is None]; print("MISSING:"+",".join(missing)) if missing else print("OK"); sys.exit(1 if missing else 0)'
& $PythonCommand -c $DependencyCheck

if ($LASTEXITCODE -ne 0) {
  Write-Host "Back-end dependencies were not found. Running pip install..." -ForegroundColor Yellow
  & $PythonCommand -m pip install -r (Join-Path $BackendRoot "requirements.txt")
  if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "pip install failed. Please check your Python/pip configuration."
  }
}

Write-Host "All checks passed. Starting services..." -ForegroundColor Green

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$BackendRoot'; $PythonCommand -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-Command",
  "Set-Location '$ProjectRoot'; npm run dev"
)

Start-Sleep -Seconds 4
Start-Process "http://127.0.0.1:5173/"

Write-Host ""
Write-Host "Done. If the page does not open automatically, visit: http://127.0.0.1:5173/" -ForegroundColor Green
Write-Host "Keep the two PowerShell service windows open while using the app." -ForegroundColor Gray
