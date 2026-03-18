#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Spot Data Downloader - WINDOWS FIXED VERSION
Đã sửa lỗi Unicode và AttributeError cho Windows
"""

import os
import sys
import json
import zipfile
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import logging
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import config
from config import (
    RAW_DIR, PROCESSED_DIR, INTERVALS, START_YEAR, END_YEAR,
    TOP_COINS_LIMIT, MAX_WORKERS, BINANCE_API_URL, BINANCE_DATA_URL
)

# === FIX 1: XỬ LÝ UNICODE CHO WINDOWS ===
# Tắt hoàn toàn emoji, chỉ dùng text thường
# Tạo custom formatter không dùng emoji
class NoEmojiFormatter(logging.Formatter):
    """Formatter loại bỏ emoji cho Windows console"""
    def format(self, record):
        msg = super().format(record)
        # Thay thế emoji bằng text
        replacements = {
            '🚀': '[ROCKET]',
            '📁': '[FOLDER]',
            '🔄': '[SYNC]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '⚠️': '[WARN]',
            '📊': '[CHART]',
            '💾': '[SAVE]',
            '🔍': '[SEARCH]',
            '🎉': '[DONE]',
            '⏰': '[TIME]',
            '📋': '[LIST]',
            '🔧': '[TOOL]',
            '⚡': '[FAST]',
            '📈': '[UP]',
            '📉': '[DOWN]',
            '💰': '[MONEY]',
            '🛑': '[STOP]',
            '🎯': '[TARGET]',
            '📦': '[BOX]',
            '🌊': '[WAVE]',
            '⚖️': '[SCALE]',
            '💵': '[DOLLAR]',
            '📝': '[NOTE]',
            '🔐': '[LOCK]',
            'ℹ️': '[INFO]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '⚠️': '[WARNING]'
        }
        for emoji, text in replacements.items():
            msg = msg.replace(emoji, text)
        return msg

# Cấu hình logging với encoding UTF-8 cho file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RAW_DIR / 'download.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # Stream ra console không emoji
    ]
)
logger = logging.getLogger(__name__)

# Override handler để xử lý emoji
for handler in logger.handlers:
    handler.setFormatter(NoEmojiFormatter('%(asctime)s - %(levelname)s - %(message)s'))


class BinanceDataDownloader:
    """
    Binance Data Downloader Class - Windows Fixed Version
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Danh sách các coin không hợp lệ cần bỏ qua
        self.invalid_symbols = [
            'USD1USDT', 'USDCUSDT', 'BUSDUSDT', 'DAIUSDT', 'TUSDUSDT', 
            'USDPUSDT', 'GUSDUSDT', 'PAXUSDT', 'USTUSDT', 'LUNAUSDT',
            'WINUSDT', 'SUNUSDT', 'FLOKIUSDT', 'PEPEUSDT', 'BONKUSDT'
        ]
    
    def safe_timestamp_conversion(self, timestamp_ms):
        """
        Chuyển đổi timestamp an toàn, tránh lỗi out of bounds
        """
        try:
            if timestamp_ms > 946684800000 and timestamp_ms < 1893456000000:
                return pd.to_datetime(timestamp_ms, unit='ms')
            else:
                return None
        except (pd.errors.OutOfBoundsDatetime, ValueError, OverflowError):
            return None
    
    def get_top_volume_symbols(self, limit: int = 100) -> List[str]:
        """
        Lấy danh sách top coins theo volume 24h từ Binance
        """
        try:
            url = f"{BINANCE_API_URL}/ticker/24hr"
            response = self.session.get(url)
            response.raise_for_status()
            
            tickers = response.json()
            
            # Lọc các cặp USDT và có volume > 0
            usdt_pairs = []
            for t in tickers:
                symbol = t['symbol']
                if (symbol.endswith('USDT') and 
                    float(t['quoteVolume']) > 0 and
                    symbol not in self.invalid_symbols and
                    not any(s in symbol for s in ['UP', 'DOWN', 'BULL', 'BEAR'])):
                    usdt_pairs.append(t)
            
            # Sắp xếp theo quoteVolume
            sorted_pairs = sorted(
                usdt_pairs, 
                key=lambda x: float(x['quoteVolume']), 
                reverse=True
            )
            
            top_symbols = [p['symbol'] for p in sorted_pairs[:limit]]
            
            logger.info(f"[OK] Da lay {len(top_symbols)} top coins theo volume")
            logger.info(f"Top 10: {', '.join(top_symbols[:10])}")
            
            return top_symbols
            
        except Exception as e:
            logger.error(f"[ERROR] Loi khi lay top symbols: {e}")
            # Fallback list
            return [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'DOTUSDT', 'LINKUSDT'
            ][:limit]
    
    def get_available_months(self, symbol: str, interval: str) -> List[Tuple[int, int]]:
        """
        Kiểm tra những tháng nào có dữ liệu
        """
        available = []
        current_date = datetime.now()
        
        for year in range(START_YEAR, current_date.year + 1):
            start_month = 1
            end_month = 12
            
            if year == current_date.year:
                end_month = current_date.month
            
            for month in range(start_month, end_month + 1):
                url = f"{BINANCE_DATA_URL}/data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{year}-{month:02d}.zip"
                try:
                    response = self.session.head(url, timeout=5)
                    if response.status_code == 200:
                        available.append((year, month))
                except:
                    continue
                    
        return available
    
    def download_monthly_data(
        self, 
        symbol: str, 
        interval: str, 
        year: int, 
        month: int
    ) -> Optional[Path]:
        """
        Tải dữ liệu hàng tháng cho 1 symbol
        Trả về Path object thay vì string
        """
        filename = f"{symbol}-{interval}-{year}-{month:02d}.zip"
        filepath = RAW_DIR / filename
        
        # Kiểm tra nếu file đã tồn tại
        if filepath.exists() and filepath.stat().st_size > 1000:
            try:
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    if zip_ref.testzip() is None:
                        logger.debug(f"[FOLDER] File {filename} da ton tai va OK")
                        return filepath
            except:
                logger.warning(f"[WARN] File {filename} bi hong, tai lai...")
                filepath.unlink()
        
        # Tải file
        url = f"{BINANCE_DATA_URL}/data/spot/monthly/klines/{symbol}/{interval}/{filename}"
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, stream=True, timeout=30)
                
                if response.status_code == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    
                    if total_size < 1000:
                        logger.debug(f"[WARN] File {filename} qua nho ({total_size} bytes), bo qua")
                        return None
                    
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Verify file
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zip_ref:
                            if zip_ref.testzip() is not None:
                                raise Exception("File bi hong")
                        logger.debug(f"[OK] Downloaded: {filename}")
                        return filepath
                    except:
                        filepath.unlink()
                        raise
                    
                elif attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.debug(f"[ERROR] Khong tim thay {filename}")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error(f"[ERROR] Loi tai {filename}: {e}")
                    
        return None
    
    def process_zip_to_csv(self, zip_path: Path) -> Optional[pd.DataFrame]:
        """
        Giải nén file zip và chuyển thành DataFrame
        zip_path là Path object, không phải string
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                csv_filename = zip_ref.namelist()[0]
                
                with zip_ref.open(csv_filename) as csv_file:
                    try:
                        # Đọc CSV
                        df = pd.read_csv(
                            csv_file,
                            header=None,
                            usecols=[0, 1, 2, 3, 4, 5],
                            names=['timestamp', 'open', 'high', 'low', 'close', 'volume'],
                            dtype={
                                'timestamp': 'int64',
                                'open': 'float64',
                                'high': 'float64',
                                'low': 'float64',
                                'close': 'float64',
                                'volume': 'float64'
                            },
                            on_bad_lines='skip'
                        )
                        
                        # Chuan hoa timestamp ve milliseconds.
                        # Co du lieu tra ve theo ms (13 so) va us (16 so), can xu ly ca hai.
                        ts = pd.to_numeric(df['timestamp'], errors='coerce')

                        sec_min, sec_max = 946684800, 1893456000
                        ms_min, ms_max = 946684800000, 1893456000000
                        us_min, us_max = 946684800000000, 1893456000000000
                        ns_min, ns_max = 946684800000000000, 1893456000000000000

                        normalized_ts = pd.Series(index=df.index, dtype='float64')

                        sec_mask = (ts >= sec_min) & (ts <= sec_max)
                        ms_mask = (ts >= ms_min) & (ts <= ms_max)
                        us_mask = (ts >= us_min) & (ts <= us_max)
                        ns_mask = (ts >= ns_min) & (ts <= ns_max)

                        normalized_ts.loc[sec_mask] = ts.loc[sec_mask] * 1000
                        normalized_ts.loc[ms_mask] = ts.loc[ms_mask]
                        normalized_ts.loc[us_mask] = (ts.loc[us_mask] // 1000)
                        normalized_ts.loc[ns_mask] = (ts.loc[ns_mask] // 1000000)

                        valid_mask = normalized_ts.notna()
                        df_valid = df[valid_mask].copy()
                        
                        if df_valid.empty:
                            logger.warning(f"[WARN] {zip_path.name}: Khong co timestamp hop le")
                            return None
                        
                        # Chuyển đổi timestamp
                        try:
                            df_valid['timestamp'] = pd.to_datetime(
                                normalized_ts.loc[valid_mask].astype('int64'),
                                unit='ms'
                            )
                        except Exception as e:
                            logger.error(f"[ERROR] Loi chuyen timestamp {zip_path.name}: {e}")
                            return None
                        
                        logger.debug(f"[OK] Da doc {zip_path.name}: {len(df_valid)} rows")
                        return df_valid
                        
                    except Exception as e:
                        logger.error(f"[ERROR] Loi doc CSV {zip_path.name}: {e}")
                        return None
                        
        except zipfile.BadZipFile:
            logger.error(f"[ERROR] {zip_path.name}: File zip bi hong")
            try:
                zip_path.unlink()
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"[ERROR] Loi xu ly {zip_path.name}: {e}")
            return None
    
    def download_all_for_symbol(
        self, 
        symbol: str, 
        intervals: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Tải tất cả dữ liệu cho 1 symbol
        """
        if intervals is None:
            intervals = INTERVALS
            
        if symbol in self.invalid_symbols:
            logger.warning(f"[WARN] Bo qua {symbol} - Invalid symbol")
            return {}
            
        result = {}
        
        for interval in intervals:
            logger.info(f"[SYNC] Dang xu ly {symbol} - {interval}")
            
            # Lấy danh sách tháng có dữ liệu
            available_months = self.get_available_months(symbol, interval)
            
            if not available_months:
                logger.warning(f"[WARN] Khong tim thay du lieu {symbol} {interval}")
                continue
            
            # Tải từng tháng
            all_dfs = []
            for year, month in available_months:
                zip_path = self.download_monthly_data(symbol, interval, year, month)
                if zip_path:
                    df = self.process_zip_to_csv(zip_path)
                    if df is not None and not df.empty and len(df) > 100:
                        all_dfs.append(df)
            
            # Ghép dữ liệu
            if all_dfs:
                try:
                    full_df = pd.concat(all_dfs, ignore_index=True)
                    full_df = full_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
                    
                    if len(full_df) > 1000:
                        output_file = PROCESSED_DIR / f"{symbol}_{interval}.csv"
                        full_df.to_csv(output_file, index=False)
                        logger.info(f"[SAVE] Da luu {symbol} {interval}: {len(full_df)} rows -> {output_file}")
                        result[interval] = full_df
                    else:
                        logger.warning(f"[WARN] {symbol} {interval}: Qua it du lieu ({len(full_df)} rows)")
                        
                except Exception as e:
                    logger.error(f"[ERROR] Loi ghep du lieu {symbol} {interval}: {e}")
                
        return result
    
    def download_bulk(
        self, 
        symbols: List[str], 
        intervals: List[str] = None,
        max_workers: int = None
    ):
        """
        Tải dữ liệu cho nhiều symbols song song
        """
        if intervals is None:
            intervals = INTERVALS
            
        if max_workers is None:
            max_workers = MAX_WORKERS
            
        symbols = [s for s in symbols if s not in self.invalid_symbols]
            
        logger.info(f"[ROCKET] Bat dau tai du lieu cho {len(symbols)} symbols, {intervals}")
        logger.info(f"[FOLDER] Thu muc luu: {RAW_DIR}")
        
        start_time = time.time()
        
        # Dùng ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for symbol in symbols:
                future = executor.submit(
                    self.download_all_for_symbol, 
                    symbol, 
                    intervals
                )
                futures[future] = symbol
            
            # Theo dõi tiến trình
            with tqdm(total=len(symbols), desc="Tong tien do") as pbar:
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        result = future.result(timeout=300)
                        if result:
                            logger.info(f"[OK] Hoan thanh {symbol}: {list(result.keys())}")
                        else:
                            logger.warning(f"[WARN] {symbol}: Khong co du lieu")
                    except Exception as e:
                        logger.error(f"[ERROR] Loi xu ly {symbol}: {str(e)}")
                    pbar.update(1)
        
        elapsed_time = time.time() - start_time
        logger.info(f"[DONE] Hoan thanh! Tong thoi gian: {elapsed_time:.2f} giay")
        
        # Thống kê
        self.print_statistics()
    
    def print_statistics(self):
        """In thống kê dữ liệu đã tải"""
        print("\n" + "="*60)
        print("THONG KE DU LIEU DA TAI")
        print("="*60)
        
        for interval in INTERVALS:
            csv_files = list(PROCESSED_DIR.glob(f"*_{interval}.csv"))
            print(f"\n[TIME] {interval}: {len(csv_files)} files")
            
            if csv_files:
                stats = []
                for f in csv_files[:10]:
                    try:
                        df = pd.read_csv(f)
                        stats.append({
                            'symbol': f.stem.replace(f'_{interval}', ''),
                            'rows': len(df),
                            'size': f.stat().st_size / (1024**2)
                        })
                    except:
                        pass
                
                stats.sort(key=lambda x: x['rows'], reverse=True)
                print("   Top coins theo so luong rows:")
                for s in stats[:5]:
                    print(f"   - {s['symbol']}: {s['rows']:,} rows ({s['size']:.1f} MB)")
        
        print("\n" + "="*60)


def main():
    """
    Hàm chính
    """
    print("""
    ============================================================
        BINANCE SPOT DATA DOWNLOADER - WINDOWS VERSION
            Danh cho backtest chien luoc
    ============================================================
    """)
    
    # Khởi tạo downloader
    downloader = BinanceDataDownloader()
    
    # Bước 1: Lấy top coins
    print("\n[CHART] Dang lay top coins tu Binance...")
    symbols = downloader.get_top_volume_symbols(limit=TOP_COINS_LIMIT)
    
    if not symbols:
        print("[ERROR] Khong the lay danh sach coins. Kiem tra ket noi.")
        return
    
    # Bước 2: Hiển thị danh sách
    print(f"\n[LIST] Danh sach top {len(symbols)} coins:")
    for i, symbol in enumerate(symbols[:20], 1):
        print(f"   {i:2d}. {symbol}")
    print("   ...")
    
    # Bước 3: Lọc bỏ invalid symbols
    symbols = [s for s in symbols if s not in downloader.invalid_symbols]
    print(f"\n[OK] Sau khi loc: {len(symbols)} coins hop le")
    
    # Bước 4: Hỏi người dùng
    choice = input(f"\n[SYNC] Tai tat ca {len(symbols)} coins? (y/n, default=y): ").strip().lower()
    
    if choice == 'n':
        custom_input = input("Nhap symbols cach nhau bang dau phay (VD: BTCUSDT,ETHUSDT,SOLUSDT): ")
        symbols = [s.strip().upper() for s in custom_input.split(',') if s.strip()]
        symbols = [s for s in symbols if s not in downloader.invalid_symbols]
        print(f"[LIST] Se tai {len(symbols)} coins: {', '.join(symbols)}")
    else:
        print(f"[LIST] Se tai {len(symbols)} coins")
    
    # Bước 5: Xác nhận intervals
    print(f"\n[TIME] Khung thoi gian se tai: {INTERVALS}")
    
    # Bước 6: Số luồng
    workers = input(f"\n[TOOL] So luong tai song song (default=3, de xuat 2-3 cho may i5): ").strip()
    if workers.isdigit():
        max_workers = int(workers)
    else:
        max_workers = 3
    
    # Bước 7: Bắt đầu
    confirm = input(f"\n[ROCKET] Bat dau tai voi {max_workers} luong? (y/n, default=y): ").strip().lower()
    
    if confirm != 'n':
        downloader.download_bulk(symbols, intervals=INTERVALS, max_workers=max_workers)
    else:
        print("[ERROR] Da huy")


if __name__ == "__main__":
    main()