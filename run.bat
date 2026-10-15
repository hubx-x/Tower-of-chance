@echo off
setlocal
cd /d "%~dp0"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"

if exist ".venv\Scripts\python.exe" goto dependencies
echo Creating the Python environment...
where py >nul 2>&1
if errorlevel 1 goto python
py -3 -m venv .venv
if not errorlevel 1 goto dependencies

:python
python -m venv .venv
if errorlevel 1 goto setup_error

:dependencies
".venv\Scripts\python.exe" -c "import pygame; assert 'pygame==' + pygame.version.ver in open('requirements.txt').read().splitlines()" >nul 2>&1
if not errorlevel 1 goto play
echo Installing Pygame...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_error

:play
if /i "%~1" == "--leaderboard" goto leaderboard
".venv\Scripts\python.exe" -m client.main
if errorlevel 1 goto game_error
exit /b 0

:leaderboard
".venv\Scripts\python.exe" -m client.leaderboard --open
if errorlevel 1 goto game_error
exit /b 0

:setup_error
echo Setup failed. Check the error above and run this file again.
goto error

:game_error
echo The game could not start. See the error above.

:error
if /i "%~0" == "%~f0" pause
exit /b 1
