@echo off
setlocal

if exist "dist\binance-data-downloader.exe" (
  echo Running packaged app...
  dist\binance-data-downloader.exe
  exit /b %errorlevel%
)

if not exist ".venv\Scripts\python.exe" (
  echo Missing virtual environment. Run setup_windows.bat first.
  exit /b 1
)

echo Running python script...
call .venv\Scripts\activate
python download_data.py

endlocal
