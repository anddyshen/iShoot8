@echo off
chcp 65001 > nul
echo ===================================================
echo   正在使用虚拟环境启动 iShoot 彩票系统...
echo ===================================================
call "%~dp0.venv\Scripts\python.exe" "%~dp0app.py"
pause

