@echo off
setlocal

REM 双击即可执行的一键打包脚本
powershell -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if %errorlevel% neq 0 (
  echo Build failed.
  exit /b %errorlevel%
)

echo Build completed: dist\PRStabilizer.exe
endlocal
