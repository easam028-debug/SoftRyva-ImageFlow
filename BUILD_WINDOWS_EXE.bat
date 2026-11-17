@echo off
REM SPDX-License-Identifier: GPL-3.0-only
REM Copyright (C) 2026 SoftRyva Development contributors
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "SoftRyva-ImageFlow" --icon "assets\ImageFlow.ico" --add-data "assets;assets" --add-data "LICENSE;." --add-data "THIRD_PARTY_NOTICES.md;." --collect-all tkinterdnd2 imageflow.py
if errorlevel 1 goto fail
echo.
echo DONE! Windows executable: dist\SoftRyva-ImageFlow.exe
echo Test on Windows before sharing publicly.
pause
exit /b 0
:fail
echo EXE build failed. Check that Windows Python and internet are available.
pause
exit /b 1
