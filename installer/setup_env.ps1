$ErrorActionPreference = "Continue"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-CommandExists($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

Write-Host "=== CapCut 자동 컷편집 - 설치 준비 ==="
Write-Host "설치 위치: $appDir"
Write-Host ""

# --- Python 확인/설치 ---
if (-not (Test-CommandExists "python")) {
    Write-Host "Python을 찾지 못했습니다. winget으로 설치를 시도합니다..."
    if (Test-CommandExists "winget") {
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        Refresh-Path
    } else {
        Write-Host ""
        Write-Host "[안내] winget을 사용할 수 없어 Python을 자동으로 설치하지 못했습니다."
        Write-Host "https://www.python.org/downloads/ 에서 Python을 설치한 뒤(반드시 'Add python.exe to PATH' 체크),"
        Write-Host "이 설치 프로그램을 다시 실행해주세요."
        Read-Host "계속하려면 Enter를 누르세요"
        exit 1
    }
} else {
    Write-Host "Python 확인됨: $(python --version)"
}

# --- ffmpeg 확인/설치 ---
if (-not (Test-CommandExists "ffmpeg")) {
    Write-Host "ffmpeg를 찾지 못했습니다. winget으로 설치를 시도합니다..."
    if (Test-CommandExists "winget") {
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        Refresh-Path
    } else {
        Write-Host "[안내] winget이 없어 ffmpeg를 자동 설치하지 못했습니다."
        Write-Host "https://ffmpeg.org/download.html 에서 직접 설치 후 PATH에 등록해주세요."
    }
} else {
    Write-Host "ffmpeg 확인됨"
}

if (-not (Test-CommandExists "python")) {
    Write-Host "[오류] Python 설치가 완료되지 않아 계속할 수 없습니다. 설치 프로그램을 다시 실행해주세요."
    Read-Host "계속하려면 Enter를 누르세요"
    exit 1
}

# --- 가상환경 생성 ---
Write-Host ""
Write-Host "Python 가상환경을 만드는 중..."
python -m venv "$appDir\venv"

if (-not (Test-Path "$appDir\venv\Scripts\python.exe")) {
    Write-Host "[오류] 가상환경 생성에 실패했습니다."
    Read-Host "계속하려면 Enter를 누르세요"
    exit 1
}

# --- 패키지 설치 ---
Write-Host ""
Write-Host "필요한 패키지를 설치하는 중입니다 (faster-whisper 등 포함, 인터넷 속도에 따라 수 분 걸릴 수 있습니다)..."
& "$appDir\venv\Scripts\python.exe" -m pip install --upgrade pip
& "$appDir\venv\Scripts\python.exe" -m pip install -r "$appDir\requirements.txt"

Write-Host ""
Write-Host "=== 설치 완료 ==="
Write-Host "시작 메뉴 또는 바탕화면의 'CapCut 자동 컷편집' 아이콘으로 실행할 수 있습니다."
Start-Sleep -Seconds 2
