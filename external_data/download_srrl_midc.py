"""Download NREL SRRL BMS raw data through the public MIDC API.

This script intentionally downloads all BMS fields for a user-specified interval.
The exact redundant radiometer columns must be frozen only after checking the
SRRL instrument history, serial-number changes, calibration records, and DQS.

Authoritative dataset DOI: 10.7799/1052221
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pvlib.iotools import read_midc_raw_data_from_nrel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", default="srrl_bms_raw.csv")
    args = parser.parse_args()

    df = read_midc_raw_data_from_nrel("BMS", args.start, args.end)
    out = Path(args.out)
    df.to_csv(out)

    candidate = [c for c in df.columns if "global" in c.lower() or "cmp22" in c.lower()]
    print(f"saved {len(df):,} rows x {len(df.columns):,} columns to {out}")
    print("candidate global/CMP22 columns:")
    for c in candidate:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
