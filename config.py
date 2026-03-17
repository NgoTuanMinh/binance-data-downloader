import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Create folders if missing
for dir_path in (DATA_DIR, RAW_DIR, PROCESSED_DIR):
    dir_path.mkdir(parents=True, exist_ok=True)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _get_intervals(default: str = "1h,4h") -> list[str]:
    raw = os.getenv("INTERVALS", default)
    values = [v.strip() for v in raw.split(",") if v.strip()]
    return values or ["1h", "4h"]


# Download settings
INTERVALS = _get_intervals()
START_YEAR = _get_int("START_YEAR", 2019)
END_YEAR = _get_int("END_YEAR", datetime.now().year - 1)
TOP_COINS_LIMIT = _get_int("TOP_COINS_LIMIT", 100)
MAX_WORKERS = _get_int("MAX_WORKERS", 5)
DOWNLOAD_DELAY = _get_float("DOWNLOAD_DELAY", 0.5)

# Binance endpoints
BINANCE_API_URL = "https://api.binance.com/api/v3"
BINANCE_DATA_URL = "https://data.binance.vision"
