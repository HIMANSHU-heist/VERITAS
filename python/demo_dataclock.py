import pandas as pd
from python.dataclock import DataClock

AS_OF = "2024-03-12 03:00:00+00:00"   # 08:30 AM IST on 12 Mar 2024
dc = DataClock(["NIFTY", "NIKKEI", "SP500", "CRUDE", "INDIAVIX"])
snap = dc.snapshot(AS_OF)

print(f"Decision time (UTC): {AS_OF}  (= 08:30 IST)\n")
for name, df in snap.items():
    last = df.iloc[-1]
    hidden = dc.frames[name].shape[0] - len(df)
    print(f"{name:9s} last visible bar: {last['date'].date()}   hidden future rows: {hidden}")
