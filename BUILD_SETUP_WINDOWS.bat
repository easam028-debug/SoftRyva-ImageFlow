@echo off
REM SPDX-License-Identifier: GPL-3.0-only
REM Copyright (C) 2026 SoftRyva Development contributors
setlocal EnableExtensions
cd /d "%~dp0"
title SoftRyva ImageFlow - Build Windows Setup

echo ============================================================
echo   SoftRyva ImageFlow v0.3.1 - Windows Setup Builder
echo ============================================================
echo.

set "PYTHON="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py -3"
if not defined PYTHON (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
  echo ERROR: Install Python 3.10+ from python.org and retry.
  goto :fail
)
if not exist ".venv\Scripts\python.exe" (
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :fail
)
set "VENV_PY=.venv\Scripts\python.exe"

echo [1/5] Installing build dependencies...
"%VENV_PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2/5] Running regression tests...
"%VENV_PY%" -m unittest discover -s tests -q
if errorlevel 1 goto :fail

echo [3/5] Generating shared SoftRyva installer artwork...
"%VENV_PY%" "installer\shared\make_wizard_assets.py" --config "installer\product.json" --output "installer\branding"
if errorlevel 1 goto :fail

echo [4/5] Building native Windows executable...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "SoftRyva-ImageFlow" --icon "assets\ImageFlow.ico" --add-data "assets;assets" --add-data "LICENSE;." --add-data "THIRD_PARTY_NOTICES.md;." --collect-all tkinterdnd2 imageflow.py
if errorlevel 1 goto :fail
if not exist "dist\SoftRyva-ImageFlow.exe" (
  echo ERROR: Missing generated EXE.
  goto :fail
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  for /f "delims=" %%P in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%P"
)
if not defined ISCC (
  echo.
  echo ERROR: Inno Setup 6.6+ is needed to compile the branded installer.
  echo Official download: https://jrsoftware.org/isdl.php
  echo The Windows app EXE was built at: dist\SoftRyva-ImageFlow.exe
  goto :fail
)

echo [5/5] Building branded SoftRyva installer...
"%ISCC%" "installer\SoftRyva_ImageFlow.iss"
if errorlevel 1 goto :fail
if not exist "dist_setup\SoftRyva_ImageFlow_Setup_v0.3.1.exe" (
  echo ERROR: Setup output file missing.
  goto :fail
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash 'dist_setup\SoftRyva_ImageFlow_Setup_v0.3.1.exe' -Algorithm SHA256).Hash + '  SoftRyva_ImageFlow_Setup_v0.3.1.exe' | Set-Content -Encoding ascii 'dist_setup\SHA256.txt'"
if errorlevel 1 echo WARNING: Could not create SHA256.txt.
echo.
echo BUILD COMPLETE!
echo Installer: dist_setup\SoftRyva_ImageFlow_Setup_v0.3.1.exe
echo Source images stay in installer\branding
echo Test install, update and uninstall on Windows before sharing.
pause
exit /b 0

:fail
 echo.
echo BUILD FAILED. Read the error above.
pause
exit /b 1
