@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [오류] 아직 설치가 완료되지 않은 것 같습니다.
    echo 설치 프로그램을 다시 실행해서 설치를 완료해주세요.
    pause
    exit /b 1
)

echo CapCut 자동 컷편집을 시작합니다...
echo 브라우저가 자동으로 열립니다. 이 창을 닫으면 서버가 종료됩니다.
echo.

"venv\Scripts\python.exe" -m capcut_auto.webapp

pause
