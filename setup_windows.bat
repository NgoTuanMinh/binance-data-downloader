@echo off
setlocal

set "PY_CMD="

echo [1/5] Checking Python...
python --version >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=python"
)

if not defined PY_CMD (
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -3"
  )
)

if not defined PY_CMD (
  echo Python 3.10+ not found.
  echo.
  winget --version >nul 2>&1
  if errorlevel 1 (
    echo Winget not found. Please install Python manually:
    echo   https://www.python.org/downloads/windows/
    echo Then run this script again.
    exit /b 1
  )

  set /p INSTALL_PY="Install Python 3.11 now with winget? (Y/N, default=Y): "
  if /I "%INSTALL_PY%"=="N" (
    echo Cancelled. Please install Python and run again.
    exit /b 1
  )

  echo Installing Python via winget...
  winget install -e --id Python.Python.3.11
  if errorlevel 1 (
    echo Python installation failed. Please install manually:
    echo   https://www.python.org/downloads/windows/
    exit /b 1
  )

  python --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=python"
  ) else (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
      set "PY_CMD=py -3"
    )
  )
)

if not defined PY_CMD (
  echo Python is still not available in this terminal.
  echo Close this window, open a new terminal, and run setup_windows.bat again.
  exit /b 1
)

echo [2/5] Creating virtual environment...
if not exist ".venv" (
  %PY_CMD% -m venv .venv
)

echo [3/5] Installing dependencies...
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [4/5] Verifying Python...
python --version

echo [5/5] Setup done.
echo You can now run:
echo   - run_app.bat
echo   - build_windows_exe.bat

endlocal
