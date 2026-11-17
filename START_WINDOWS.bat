@echo off
REM SPDX-License-Identifier: GPL-3.0-only
REM Copyright (C) 2026 SoftRyva Development contributors
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  echo [ImageFlow] Creating local Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)
if not exist ".venv\imageflow-v030-ready" (
  echo [ImageFlow] Installing libraries once (internet needed for setup)...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  echo ready> ".venv\imageflow-v030-ready"
)
echo [ImageFlow] Starting offline application...
".venv\Scripts\python.exe" imageflow.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Start failed. Verify Python 3.10+ and connection for the first run.
pause
exit /b 1
