#%%


import argparse
import io
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

# FRED CSV for the CBOE VIX series (daily closes)
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
# Where to save the cleaned VIX history on this machine
OUTPUT_FILE = r"C:\Users\andre\Downloads\vix_close.csv"


def fetch_fred():
    df = pd.read_csv(FRED_CSV_URL)

 # Normalize column names to lower case so we can handle DATE vs observation_date
    cols = {c.lower().strip(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("observation_date")
    value_col = cols.get("vixcls")
 
 # Fail fast if FRED ever changes the header names unexpectedly
    if not date_col or not value_col:
        raise RuntimeError(f"Unexpected FRED columns: {list(df.columns)}")

# Keep only the date and VIX close columns, and rename for consistency
    out = df[[date_col, value_col]].copy()
    out.columns = ["date", "close"]

# Convert to proper date/float types and drop any bad rows
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")

    out = out.dropna(subset=["date", "close"]).sort_values("date")
    return out


def write_output(df, output_path):
    output_path = Path(output_path).expanduser()
    # Make sure the folder exists before we try to write the file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Format dates as YYYY-MM-DD strings for a clean CSV
    df2 = df.copy()
    df2["date"] = df2["date"].dt.strftime("%Y-%m-%d")
    # Write to a temporary file first, then atomically move into place
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df2.to_csv(tmp, index=False)
    shutil.move(str(tmp), str(output_path))


def main():
    try:
        df = fetch_fred()
        write_output(df, OUTPUT_FILE)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    latest = df.iloc[-1]
    print(f"Saved {len(df):,} rows to {OUTPUT_FILE}")
    print(f"Latest close: {latest['date'].date()} = {latest['close']}")


if __name__ == "__main__":
    main()
 

# %%
