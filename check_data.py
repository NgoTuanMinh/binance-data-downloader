from __future__ import annotations

import pandas as pd

from config import PROCESSED_DIR


def check_data_quality(symbol: str, interval: str) -> None:
    filepath = PROCESSED_DIR / f"{symbol}_{interval}.csv"
    if not filepath.exists():
        print(f"Missing file: {filepath}")
        return

    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    gap_threshold = pd.Timedelta(hours=2 if interval == "1h" else 5)
    gaps = df["timestamp"].diff().gt(gap_threshold).sum()

    print(f"\n{symbol} - {interval}")
    print(f"  Rows: {len(df):,}")
    print(f"  From: {df['timestamp'].min()}")
    print(f"  To: {df['timestamp'].max()}")
    print(f"  Avg interval: {df['timestamp'].diff().mean()}")
    print(f"  Missing timestamps (rough): {int(gaps)}")
    print(f"  Lowest price: ${df['low'].min():,.4f}")
    print(f"  Highest price: ${df['high'].max():,.4f}")
    print(f"  Avg volume: {df['volume'].mean():,.0f}")


if __name__ == "__main__":
    for _symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        for _interval in ["1h", "4h"]:
            check_data_quality(_symbol, _interval)
