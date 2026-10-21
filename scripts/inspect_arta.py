"""Inspect ARTA spreadsheets: sheet names, row counts, exact column names, and sample values.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATASETS_DIR = Path("data/raw/arta/extracted/ARTADataset_release1/Datasets")


def inspect_arta():
    results = {}
    for xlsx_file in sorted(DATASETS_DIR.glob("*.xlsx")):
        name = xlsx_file.name
        xl = pd.ExcelFile(xlsx_file)
        sheets_info = {}
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            cols = [str(c) for c in df.columns]
            sample = {}
            if not df.empty:
                for col in cols:
                    val = df.iloc[0][col]
                    sample[col] = str(val)[:100]
            sheets_info[sheet_name] = {
                "shape": list(df.shape),
                "columns": cols,
                "first_row_sample": sample,
                "null_counts": {col: int(df[col].isna().sum()) for col in cols},
            }
        results[name] = sheets_info

    out_file = Path("data/raw/arta/arta_inspection.json")
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved ARTA inspection to {out_file}")


if __name__ == "__main__":
    inspect_arta()
