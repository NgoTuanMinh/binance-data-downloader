@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  echo Missing virtual environment. Run setup_windows.bat first.
  exit /b 1
)

call .venv\Scripts\activate

echo Building EXE with PyInstaller...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name binance-data-downloader ^
  --add-data ".env.example;." ^
  download_data.py

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo Build completed.
echo EXE path: dist\binance-data-downloader.exe

endlocal
