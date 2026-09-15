@echo off
rem Pinball Space Cadet launcher (ASCII-only content on purpose:
rem cmd parses batch files with the OEM codepage, so non-ASCII text
rem inside a .bat can corrupt parsing. Keep this file ASCII!)
rem For the GUI launcher double-click launcher.pyw instead.
cd /d "%~dp0"

set "PY=C:\ProgramData\anaconda3\python.exe"
if exist "%PY%" goto check_dep

where python >nul 2>nul
if errorlevel 1 goto nopy
for /f "delims=" %%i in ('where python') do set "PY=%%i"

rem reject the Microsoft Store python stub (it exists but cannot run)
"%PY%" -c "print(1)" >nul 2>nul
if errorlevel 1 goto nopy

:check_dep
echo Using Python: %PY%
"%PY%" -c "import ursina" >nul 2>nul
if not errorlevel 1 goto play

echo [INFO] Ursina not found, installing dependencies...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail

:play
if "%PINBALL_DRYRUN%"=="1" goto dryrun
"%PY%" main.py
if errorlevel 1 goto fail
exit /b 0

:dryrun
echo [DRYRUN] environment OK, game would start now.
exit /b 0

:nopy
echo [ERROR] No usable Python found. Install Anaconda or add python to PATH.
pause
exit /b 1

:fail
echo [ERROR] Launch failed. See messages above.
pause
exit /b 1
