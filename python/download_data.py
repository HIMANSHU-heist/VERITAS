import yfinance as yf
import pandas as pd
from pathlib import Path

OUT = Path("data/frozen")
OUT.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "NIFTY": "^NSEI",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "NIKKEI": "^N225",
    "CRUDE": "CL=F",
    "GOLD": "GC=F",
    "USDINR": "INR=X",
    "INDIAVIX": "^INDIAVIX",
}

ok, failed = [], []
for name, sym in TICKERS.items():
    try:
        df = yf.download(sym, period="5y", interval="1d", auto_adjust=False, progress=False)
        if df is None or df.empty:
            failed.append(name); continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index().rename(columns=str.lower)
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"{name:10s} rows={len(df):5d} {df['date'].min().date()} -> {df['date'].max().date()}")
        ok.append(name)
    except Exception as e:
        print(f"{name} FAILED: {e}")
        failed.append(name)

print("OK:", ok)
print("FAILED:", failed)
