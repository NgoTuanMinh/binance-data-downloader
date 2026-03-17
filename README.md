# Binance Data Downloader

Download historical Binance spot kline data for top-volume USDT pairs and export merged CSV files.

## Project Structure

- `download_data.py`: main downloader script
- `config.py`: settings and directories
- `check_data.py`: quick data quality checks
- `requirements.txt`: Python dependencies
- `.env.example`: optional environment config
- `data/raw`: downloaded ZIP files
- `data/processed`: merged CSV files
- `setup_windows.bat`: Windows setup
- `build_windows_exe.bat`: build standalone EXE
- `run_app.bat`: run EXE (if available) or Python script

## Setup (Python)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # optional
python download_data.py
```

## Windows EXE

1. Run `setup_windows.bat`
2. Run `build_windows_exe.bat`
3. Use `dist\binance-data-downloader.exe` or run `run_app.bat`
