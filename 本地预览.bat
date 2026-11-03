@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   GitPlain 本地预览
echo   浏览器会自动打开 http://127.0.0.1:8899/
echo   关掉这个黑窗口 = 停止预览
echo ============================================
echo.

REM 清掉占着 8899 的僵死进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8899" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

start "" http://127.0.0.1:8899/
python -m http.server 8899 --bind 127.0.0.1

pause
