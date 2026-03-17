# cleanup.py
import os
from pathlib import Path
from config import RAW_DIR

# Xóa các file lỗi
for f in RAW_DIR.glob("USD1USDT*.zip"):
    print(f"🗑️ Xóa {f}")
    f.unlink()

for f in RAW_DIR.glob("*USDC*.zip"):
    print(f"🗑️ Xóa {f}")
    f.unlink()

# Xóa file nhỏ hơn 1KB
for f in RAW_DIR.glob("*.zip"):
    if f.stat().st_size < 1000:
        print(f"🗑️ Xóa file nhỏ: {f}")
        f.unlink()