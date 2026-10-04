from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit.config import (
    COLUMN_RENAME,
    FEATURE_COLUMNS,
    PROCESSED_DATA_PATH,
    RAW_DATA_PATH,
    TARGET,
)


def load_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or RAW_DATA_PATH
    df = pd.read_csv(path, sep=r"\s+")
    missing = set(COLUMN_RENAME) - set(df.columns)
    if missing:
        raise ValueError(f"Unexpected columns in raw file; missing: {sorted(missing)}")
    return df.rename(columns=COLUMN_RENAME)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    expected = FEATURE_COLUMNS + [TARGET]
    missing = set(expected) - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")

    out = df[expected].copy()
    for col in expected:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    n_before = len(out)
    out = out.dropna().astype(int)
    n_dropped = n_before - len(out)
    if n_dropped:
        print(f"Dropped {n_dropped} rows with missing/non-numeric values")

    if not set(out[TARGET].unique()).issubset({0, 1}):
        raise ValueError(f"Target must be 0/1; got {sorted(out[TARGET].unique())}")

    return out.reset_index(drop=True)


def save_processed(df: pd.DataFrame, path: Path | None = None) -> Path:
    path = path or PROCESSED_DATA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_processed(path: Path | None = None) -> pd.DataFrame:
    path = path or PROCESSED_DATA_PATH
    return pd.read_csv(path)


def prepare_dataset(
    raw_path: Path | None = None,
    processed_path: Path | None = None,
) -> pd.DataFrame:
    df = clean(load_raw(raw_path))
    save_processed(df, processed_path)
    return df
