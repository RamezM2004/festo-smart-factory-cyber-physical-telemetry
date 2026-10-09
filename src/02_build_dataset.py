"""
02_build_dataset.py
-------------------
Reads all labeled CSV files from the /data/ folder and assembles them
into a single labeled_dataset.csv for model training.

File naming convention (must match exactly):
    RASS_NORMAL_session1.csv
    RASS_FM01_pressure_drop.csv
    RASS_FM02_flow_restrict.csv
    ...etc.

The label is inferred from the filename:
    - Any file containing 'NORMAL' → label = 'NORMAL'
    - Any file containing 'FM01'   → label = 'FM01_PRESSURE_DROP'
    - ...etc.

Usage:
    python 02_build_dataset.py
"""

import os
import pandas as pd
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "labeled_dataset.csv")

# Maps filename keyword → class label
LABEL_MAP = {
    "NORMAL":      "NORMAL",
    "FM01":        "FM01_PRESSURE_DROP",
    "FM02":        "FM02_FLOW_RESTRICT",
    "FM03":        "FM03_FLOW_BLOCK",
    "FM04":        "FM04_OVERLOAD",
    "FM05":        "FM05_IDLE_NO_LOAD",
    "FM06":        "FM06_SPEED_REDUCTION",
    "FM07":        "FM07_PHASE_IMBALANCE",
    "FM08":        "FM08_SENSOR_OBSTRUCT",
    "FM09":        "FM09_INTERMITTENT",
    "FM10":        "FM10_OVERPRESSURE",
    "FM01_LOW01":  "FM01_PRESSURE_LOW01",   # Mild pressure drop (~6.5 bar)
    "FM01_LOW02":  "FM01_PRESSURE_LOW02",   # Moderate pressure drop (~5.5 bar)
    "FM01_LOW03":  "FM01_PRESSURE_LOW03",   # Severe pressure drop (~4.5 bar)
    "STANDBY":     "STANDBY",               # Static/quiescent baseline (no conveyor, no products)
    "IDLE":        "FM05_IDLE_NO_LOAD",     # Idle running without workload
}

# Canonical feature columns (must exist in every CSV after loading)
FEATURE_COLS = [
    "Pressure", "Flow",
    "ActivePowerL1", "ActivePowerL2", "ActivePowerL3", "ActivePowerTotal",
    "CurrentL1", "CurrentL2", "CurrentL3",
    "VoltageL1", "VoltageL2", "VoltageL3",
    "PowerFactorL1", "PowerFactorL2", "PowerFactorL3",
    "ReactivePowerL1", "ReactivePowerL2", "ReactivePowerL3", "ReactivePowerTotal",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def infer_station(filename: str) -> str:
    """Infer the station from the filename prefix."""
    fname_upper = filename.upper()
    if fname_upper.startswith("RASS_"):
        return "RASS"
    elif fname_upper.startswith("MPRESS_"):
        return "MPRESS"
    elif fname_upper.startswith("ASRS_"):
        return "ASRS"
    elif fname_upper.startswith("LINEAR_"):
        return "LINEAR"
    elif fname_upper.startswith("MAGAZINE_"):
        return "MAGAZINE"
    elif fname_upper.startswith("CP_ALL_"):
        return "CP_LINE"
    return "UNKNOWN"


def infer_label(filename: str) -> str | None:
    """Return the class label for a filename, or None if unrecognised."""
    fname_upper = filename.upper()
    sorted_keywords = sorted(LABEL_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in fname_upper:
            return LABEL_MAP[keyword]
    return None


def load_and_normalise(filepath: str, label: str, station: str) -> pd.DataFrame:
    """
    Load a single MES4 CSV export, normalise column names,
    keep only the feature columns that exist, fill missing with NaN,
    and append the label.
    """
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    # Handle duplicate columns by keeping the first occurrence
    df = df.loc[:, ~df.columns.duplicated()]

    # Handle the alternative column name from 'pallet one.csv' format
    col_remap = {
        "0 - Active Power Total [W]": "ActivePowerTotal",
        "Pressure1": "Pressure",   # some exports use Pressure1 as the main channel
        "Flow1":     "Flow",
    }
    df.rename(columns=col_remap, inplace=True)

    # Re-check duplicates after renaming
    df = df.loc[:, ~df.columns.duplicated()]

    # Replace 'null' string with NaN
    df.replace("null", np.nan, inplace=True)

    # Ensure all feature columns exist (fill missing ones with NaN)
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # Convert feature columns to numeric
    for col in FEATURE_COLS:
        series = df[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        df[col] = pd.to_numeric(series, errors="coerce")

    # Keep only feature columns + station + label
    df = df[FEATURE_COLS].copy()
    df["station"] = station
    df["label"] = label

    # Drop rows where ALL features are NaN
    df.dropna(how="all", subset=FEATURE_COLS, inplace=True)

    return df


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.isdir(DATA_DIR):
        print(f"[ERROR] Data directory not found: {DATA_DIR}")
        print("  Create the 'data/' folder and place your MES4 CSV exports inside it.")
        return

    csv_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".csv")]
    if not csv_files:
        print(f"[ERROR] No CSV files found in: {DATA_DIR}")
        print("  Export sessions from MES4 and save them using the naming convention.")
        return

    print(f"Found {len(csv_files)} CSV file(s) in {DATA_DIR}\n")

    frames = []
    label_counts = {}
    station_counts = {}

    for fname in sorted(csv_files):
        label = infer_label(fname)
        if label is None:
            print(f"  [SKIP] {fname} — cannot infer label from filename")
            continue

        station = infer_station(fname)
        filepath = os.path.join(DATA_DIR, fname)
        try:
            df = load_and_normalise(filepath, label, station)
            frames.append(df)
            label_counts[label] = label_counts.get(label, 0) + len(df)
            station_counts[station] = station_counts.get(station, 0) + len(df)
            print(f"  [OK]   {fname:45s}  → {station:10s} | {label:30s}  ({len(df)} rows)")
        except Exception as e:
            print(f"  [ERR]  {fname} — {e}")

    if not frames:
        print("\n[ERROR] No usable data frames assembled.")
        return

    dataset = pd.concat(frames, ignore_index=True)
    dataset.to_csv(OUTPUT_FILE, index=False)

    print(f"\n{'─'*60}")
    print(f"Dataset saved → {OUTPUT_FILE}")
    print(f"Total rows   : {len(dataset)}")
    print(f"\nClass distribution:")
    for label, count in sorted(label_counts.items()):
        bar = "█" * (count // 10)
        print(f"  {label:30s}  {count:>5} rows  {bar}")
        
    print(f"\nStation distribution:")
    for st, count in sorted(station_counts.items()):
        print(f"  {st:30s}  {count:>5} rows")

    print(f"\nFeature columns ({len(FEATURE_COLS)}): {', '.join(FEATURE_COLS)}")
    print(f"Station column: 'station'")
    print(f"Label column: 'label'")
    print(f"\nNext step: run  python 03_train_classifier.py")


if __name__ == "__main__":
    main()
