#!/usr/bin/env python3
"""
Binance Spot Data Downloader
Download historical kline data for many symbols and intervals.
"""

from __future__ import annotations

import logging
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from config import (
    BINANCE_API_URL,
    BINANCE_DATA_URL,
    DOWNLOAD_DELAY,
    END_YEAR,
    INTERVALS,
    MAX_WORKERS,
    PROCESSED_DIR,
    RAW_DIR,
    START_YEAR,
    TOP_COINS_LIMIT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(RAW_DIR / "download.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class BinanceDataDownloader:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _safe_request(self, method: str, url: str, **kwargs) -> requests.Response:
        if DOWNLOAD_DELAY > 0:
            time.sleep(DOWNLOAD_DELAY)
        response = self.session.request(method=method, url=url, **kwargs)
        return response

    def get_top_volume_symbols(self, limit: int = 100) -> List[str]:
        try:
            response = self._safe_request("GET", f"{BINANCE_API_URL}/ticker/24hr", timeout=30)
            response.raise_for_status()
            tickers = response.json()

            stable_base = ("USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP")
            usdt_pairs = [
                t
                for t in tickers
                if t["symbol"].endswith("USDT")
                and float(t.get("quoteVolume", 0)) > 0
                and not t["symbol"].startswith(stable_base)
            ]

            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
            top_symbols = [p["symbol"] for p in sorted_pairs[:limit]]
            logger.info("Loaded %s symbols by quote volume", len(top_symbols))
            logger.info("Top 10 symbols: %s", ", ".join(top_symbols[:10]))
            return top_symbols
        except Exception as exc:
            logger.error("Cannot fetch symbols from Binance API: %s", exc)
            fallback = [
                "BTCUSDT",
                "ETHUSDT",
                "BNBUSDT",
                "SOLUSDT",
                "XRPUSDT",
                "ADAUSDT",
                "AVAXUSDT",
                "DOGEUSDT",
                "DOTUSDT",
                "LINKUSDT",
                "MATICUSDT",
                "SHIBUSDT",
                "LTCUSDT",
                "UNIUSDT",
                "ATOMUSDT",
                "ETCUSDT",
                "FILUSDT",
                "ICPUSDT",
                "NEARUSDT",
                "APTUSDT",
                "OPUSDT",
                "ARBUSDT",
                "HBARUSDT",
                "VETUSDT",
                "ALGOUSDT",
            ]
            return fallback[:limit]

    def get_available_months(self, symbol: str, interval: str) -> List[Tuple[int, int]]:
        available: List[Tuple[int, int]] = []
        now = datetime.now()
        max_year = min(END_YEAR, now.year)

        for year in range(START_YEAR, max_year + 1):
            end_month = 12 if year < now.year else now.month
            for month in range(1, end_month + 1):
                filename = f"{symbol}-{interval}-{year}-{month:02d}.zip"
                monthly_url = (
                    f"{BINANCE_DATA_URL}/data/spot/monthly/klines/{symbol}/{interval}/{filename}"
                )
                try:
                    res = self._safe_request("HEAD", monthly_url, timeout=10)
                    if res.status_code == 200:
                        available.append((year, month))
                        continue

                    # Monthly file can be missing for very recent periods, try first daily file.
                    daily_filename = f"{symbol}-{interval}-{year}-{month:02d}-01.zip"
                    daily_url = (
                        f"{BINANCE_DATA_URL}/data/spot/daily/klines/{symbol}/{interval}/{daily_filename}"
                    )
                    daily_res = self._safe_request("HEAD", daily_url, timeout=10)
                    if daily_res.status_code == 200:
                        available.append((year, month))
                except Exception:
                    continue
        return available

    def download_monthly_data(
        self, symbol: str, interval: str, year: int, month: int
    ) -> Optional[str]:
        filename = f"{symbol}-{interval}-{year}-{month:02d}.zip"
        filepath = RAW_DIR / filename

        if filepath.exists():
            try:
                with zipfile.ZipFile(filepath, "r") as zip_ref:
                    if zip_ref.testzip() is None:
                        return str(filepath)
            except Exception:
                logger.warning("Corrupted file found, re-downloading %s", filename)
                filepath.unlink(missing_ok=True)

        monthly_url = f"{BINANCE_DATA_URL}/data/spot/monthly/klines/{symbol}/{interval}/{filename}"
        daily_filename = f"{symbol}-{interval}-{year}-{month:02d}-01.zip"
        daily_url = f"{BINANCE_DATA_URL}/data/spot/daily/klines/{symbol}/{interval}/{daily_filename}"

        for attempt in range(3):
            try:
                response = self._safe_request("GET", monthly_url, stream=True, timeout=60)
                if response.status_code != 200:
                    response = self._safe_request("GET", daily_url, stream=True, timeout=60)

                if response.status_code != 200:
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                    return None

                total_size = int(response.headers.get("content-length", 0))
                with open(filepath, "wb") as file_obj:
                    with tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=f"{symbol} {interval} {year}-{month:02d}",
                        leave=False,
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if not chunk:
                                continue
                            file_obj.write(chunk)
                            pbar.update(len(chunk))

                with zipfile.ZipFile(filepath, "r") as zip_ref:
                    if zip_ref.testzip() is not None:
                        raise zipfile.BadZipFile("ZIP integrity failed")
                return str(filepath)
            except Exception as exc:
                if attempt < 2:
                    time.sleep(2**attempt)
                else:
                    logger.error("Failed to download %s: %s", filename, exc)
                    filepath.unlink(missing_ok=True)
        return None

    def process_zip_to_csv(self, zip_path: str) -> Optional[pd.DataFrame]:
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                csv_filename = zip_ref.namelist()[0]
                with zip_ref.open(csv_filename) as csv_file:
                    df = pd.read_csv(
                        csv_file,
                        header=None,
                        usecols=[0, 1, 2, 3, 4, 5],
                        names=["timestamp", "open", "high", "low", "close", "volume"],
                    )

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
            return df
        except Exception as exc:
            logger.error("Cannot process %s: %s", zip_path, exc)
            return None

    def download_all_for_symbol(
        self, symbol: str, intervals: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        intervals = intervals or INTERVALS
        result: Dict[str, pd.DataFrame] = {}

        for interval in intervals:
            logger.info("Processing %s - %s", symbol, interval)
            available_months = self.get_available_months(symbol, interval)
            if not available_months:
                logger.warning("No data for %s %s", symbol, interval)
                continue

            all_dfs: List[pd.DataFrame] = []
            for year, month in available_months:
                zip_path = self.download_monthly_data(symbol, interval, year, month)
                if not zip_path:
                    continue
                df = self.process_zip_to_csv(zip_path)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                continue

            full_df = pd.concat(all_dfs, ignore_index=True)
            full_df = full_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])
            output_file = PROCESSED_DIR / f"{symbol}_{interval}.csv"
            full_df.to_csv(output_file, index=False)
            logger.info("Saved %s rows to %s", len(full_df), output_file)
            result[interval] = full_df
        return result

    def download_bulk(
        self, symbols: List[str], intervals: Optional[List[str]] = None, max_workers: Optional[int] = None
    ) -> None:
        intervals = intervals or INTERVALS
        max_workers = max_workers or MAX_WORKERS

        logger.info("Start bulk download: symbols=%s intervals=%s workers=%s", len(symbols), intervals, max_workers)
        start = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self.download_all_for_symbol, symbol, intervals): symbol
                for symbol in symbols
            }

            for future in tqdm(as_completed(future_to_symbol), total=len(future_to_symbol), desc="Overall progress"):
                symbol = future_to_symbol[future]
                try:
                    result = future.result(timeout=3600)
                    if result:
                        logger.info("Completed %s -> %s", symbol, list(result.keys()))
                    else:
                        logger.warning("Completed %s with no output", symbol)
                except Exception as exc:
                    logger.error("Error for %s: %s", symbol, exc)

        elapsed = time.time() - start
        logger.info("All done in %.2f seconds", elapsed)

    def load_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        filepath = PROCESSED_DIR / f"{symbol}_{interval}.csv"
        if not filepath.exists():
            logger.error("CSV not found: %s", filepath)
            return None
        try:
            df = pd.read_csv(filepath)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            logger.info("Loaded %s rows from %s", len(df), filepath)
            return df
        except Exception as exc:
            logger.error("Cannot read %s: %s", filepath, exc)
            return None


def main() -> None:
    downloader = BinanceDataDownloader()
    logger.info("Fetching top symbols from Binance...")
    symbols = downloader.get_top_volume_symbols(limit=TOP_COINS_LIMIT)

    if not symbols:
        logger.error("No symbols available. Check your connection and retry.")
        return

    print(f"\nTop {len(symbols)} symbols by quote volume:")
    for idx, symbol in enumerate(symbols[:20], 1):
        print(f"  {idx:2d}. {symbol}")
    print("  ...")

    choice = input(f"\nDownload all {len(symbols)} symbols? (y/n, default=y): ").strip().lower()
    if choice == "n":
        custom = input("Input symbols separated by comma (e.g. BTCUSDT,ETHUSDT,SOLUSDT): ")
        symbols = [token.strip().upper() for token in custom.split(",") if token.strip()]
        if not symbols:
            logger.error("No valid symbol provided, stopping.")
            return
        print(f"Will download {len(symbols)} symbols: {', '.join(symbols)}")
    else:
        print(f"Will download all {len(symbols)} symbols.")

    print(f"\nIntervals: {INTERVALS}")
    confirm = input("Start download now? (y/n, default=y): ").strip().lower()
    if confirm == "n":
        print("Cancelled.")
        return

    downloader.download_bulk(symbols=symbols, intervals=INTERVALS)

    print("\nDownload stats:")
    for interval in INTERVALS:
        csv_files = list(PROCESSED_DIR.glob(f"*_{interval}.csv"))
        print(f"  {interval}: {len(csv_files)} files")
    print("\nOutput folders:")
    print(f"  RAW ZIP: {RAW_DIR}")
    print(f"  PROCESSED CSV: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
