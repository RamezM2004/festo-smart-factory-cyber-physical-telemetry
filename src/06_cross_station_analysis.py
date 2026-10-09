"""
06_cross_station_analysis.py
----------------------------
Performs cross-station transfer learning evaluation for Smart Factory maintenance fault classification.
Evaluates same-station, cross-station (transfer learning), and combined models.

Usage:
    python 06_cross_station_analysis.py
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, accuracy_score

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(__file__)
DATASET_FILE  = os.path.join(BASE_DIR, "labeled_dataset.csv")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
REPORT_FILE   = os.path.join(MODELS_DIR, "cross_station_report.txt")
WINDOW_SIZE   = 5   # seconds — rolling window for feature aggregation

FEATURE_COLS = [
    "Pressure", "Flow",
    "ActivePowerL1", "ActivePowerL2", "ActivePowerL3", "ActivePowerTotal",
    "CurrentL1", "CurrentL2", "CurrentL3",
    "VoltageL1", "VoltageL2", "VoltageL3",
    "PowerFactorL1", "PowerFactorL2", "PowerFactorL3",
    "ReactivePowerL1", "ReactivePowerL2", "ReactivePowerL3", "ReactivePowerTotal",
]

# ── Feature Engineering ────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame, window: int = WINDOW_SIZE) -> pd.DataFrame:
    """
    Transform raw 1-second sensor readings into window-level features.
    Each output row summarises 'window' seconds of data.
    Retains station and label information.
    """
    records = []

    # Group by station and label so windows don't span across different fault sessions or stations
    for (station, label), group in df.groupby(["station", "label"], sort=False):
        group = group.reset_index(drop=True)
        raw = group[FEATURE_COLS].copy()

        # Slide window across the group
        for i in range(0, len(raw) - window + 1, window):
            win = raw.iloc[i : i + window]
            feat = {}

            for col in FEATURE_COLS:
                vals = win[col].dropna()
                if len(vals) == 0:
                    feat[f"{col}_mean"] = np.nan
                    feat[f"{col}_std"]  = np.nan
                    feat[f"{col}_min"]  = np.nan
                    feat[f"{col}_max"]  = np.nan
                    feat[f"{col}_delta"] = np.nan
                else:
                    feat[f"{col}_mean"] = vals.mean()
                    feat[f"{col}_std"]  = vals.std() if len(vals) > 1 else 0.0
                    feat[f"{col}_min"]  = vals.min()
                    feat[f"{col}_max"]  = vals.max()
                    # Rate of change: last - first value
                    feat[f"{col}_delta"] = float(vals.iloc[-1]) - float(vals.iloc[0])

            # ── Engineered Compound Features ──────────────────────────────────

            # Pneumatic ratio: Flow / Pressure  (flags blockage / overpressure)
            p_mean = feat.get("Pressure_mean", np.nan)
            f_mean = feat.get("Flow_mean", np.nan)
            feat["flow_pressure_ratio"] = (
                f_mean / p_mean if (p_mean and p_mean != 0) else np.nan
            )

            # Phase power imbalance: max(L1,L2,L3) - min(L1,L2,L3)
            phase_means = [
                feat.get("ActivePowerL1_mean", np.nan),
                feat.get("ActivePowerL2_mean", np.nan),
                feat.get("ActivePowerL3_mean", np.nan),
            ]
            phase_means_valid = [v for v in phase_means if not np.isnan(v)]
            feat["phase_imbalance"] = (
                max(phase_means_valid) - min(phase_means_valid)
                if len(phase_means_valid) == 3 else np.nan
            )

            # Power-to-flow ratio: high power with low flow → overload / idle
            feat["power_flow_ratio"] = (
                feat.get("ActivePowerTotal_mean", np.nan) / f_mean
                if (f_mean and f_mean > 0) else np.nan
            )

            # Current imbalance
            curr = [
                feat.get("CurrentL1_mean", np.nan),
                feat.get("CurrentL2_mean", np.nan),
                feat.get("CurrentL3_mean", np.nan),
            ]
            curr_valid = [v for v in curr if not np.isnan(v)]
            feat["current_imbalance"] = (
                max(curr_valid) - min(curr_valid)
                if len(curr_valid) == 3 else np.nan
            )

            # Pressure variability (high std = intermittent / oscillating pressure)
            feat["pressure_variability"] = feat.get("Pressure_std", np.nan)

            feat["label"] = label
            feat["station"] = station
            records.append(feat)

    return pd.DataFrame(records)

# ── Pipeline Creation ──────────────────────────────────────────────────────────

def create_pipeline():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])

# ── Evaluation Models ──────────────────────────────────────────────────────────

def evaluate_train_test(df_train, df_test, label_encoder, feature_cols):
    X_train = df_train[feature_cols].values
    y_train = label_encoder.transform(df_train["label"])
    
    X_test = df_test[feature_cols].values
    y_test = label_encoder.transform(df_test["label"])

    pipe = create_pipeline()
    pipe.fit(X_train, y_train)
    
    preds = pipe.predict(X_test)
    f1 = f1_score(y_test, preds, average="weighted")
    acc = accuracy_score(y_test, preds)
    return f1, acc

def evaluate_cv(df_combined, label_encoder, feature_cols):
    X = df_combined[feature_cols].values
    y = label_encoder.transform(df_combined["label"])
    
    pipe = create_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    scores = cross_validate(pipe, X, y, cv=cv, scoring=["f1_weighted", "accuracy"], n_jobs=-1)
    return scores["test_f1_weighted"].mean(), scores["test_accuracy"].mean()

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.isfile(DATASET_FILE):
        print(f"[ERROR] labeled_dataset.csv not found at: {DATASET_FILE}")
        sys.exit(1)

    print(f"Loading dataset from: {DATASET_FILE}")
    df = pd.read_csv(DATASET_FILE)

    if "station" not in df.columns:
        print("[ERROR] 'station' column not found in dataset.")
        sys.exit(1)

    stations = df["station"].unique()
    print(f"Stations found: {list(stations)}")

    print(f"\nEngineering features (window = {WINDOW_SIZE}s) ...")
    df_features = engineer_features(df, window=WINDOW_SIZE)
    df_features.dropna(subset=["label"], inplace=True)
    
    feature_cols = [c for c in df_features.columns if c not in ["label", "station"]]
    
    label_encoder = LabelEncoder()
    label_encoder.fit(df_features["label"])

    has_rass = "RASS" in stations
    has_mpress = "MPRESS" in stations

    results = []

    if has_rass and has_mpress:
        df_rass = df_features[df_features["station"] == "RASS"]
        df_mpress = df_features[df_features["station"] == "MPRESS"]
        df_combined = pd.concat([df_rass, df_mpress])

        # RASS -> RASS
        f1_rr, acc_rr = evaluate_train_test(df_rass, df_rass, label_encoder, feature_cols)
        results.append(("RASS → RASS (same-station)", f1_rr, acc_rr))

        # MPRESS -> MPRESS
        f1_mm, acc_mm = evaluate_train_test(df_mpress, df_mpress, label_encoder, feature_cols)
        results.append(("MPRESS → MPRESS", f1_mm, acc_mm))

        # RASS -> MPRESS
        f1_rm, acc_rm = evaluate_train_test(df_rass, df_mpress, label_encoder, feature_cols)
        results.append(("RASS → MPRESS (transfer)", f1_rm, acc_rm))

        # MPRESS -> RASS
        f1_mr, acc_mr = evaluate_train_test(df_mpress, df_rass, label_encoder, feature_cols)
        results.append(("MPRESS → RASS (transfer)", f1_mr, acc_mr))

        # Combined (cross-val)
        f1_c, acc_c = evaluate_cv(df_combined, label_encoder, feature_cols)
        results.append(("Combined (cross-val)", f1_c, acc_c))
        
    elif has_rass:
        print("\nNote: Only RASS station data found. Running same-station evaluation only.")
        df_rass = df_features[df_features["station"] == "RASS"]
        f1_rr, acc_rr = evaluate_train_test(df_rass, df_rass, label_encoder, feature_cols)
        results.append(("RASS → RASS (same-station)", f1_rr, acc_rr))
        
    elif has_mpress:
        print("\nNote: Only MPRESS station data found. Running same-station evaluation only.")
        df_mpress = df_features[df_features["station"] == "MPRESS"]
        f1_mm, acc_mm = evaluate_train_test(df_mpress, df_mpress, label_encoder, feature_cols)
        results.append(("MPRESS → MPRESS (same-station)", f1_mm, acc_mm))
        
    else:
        print("\nNote: Neither RASS nor MPRESS station data found.")
        sys.exit(0)

    # Output formatting
    report_lines = []
    header = f"┌{'─'*29}┬{'─'*10}┬{'─'*12}┐"
    title_row = f"│ {'Scenario':<27} │ {'F1 Score':<8} │ {'Accuracy':<10} │"
    divider = f"├{'─'*29}┼{'─'*10}┼{'─'*12}┤"
    footer = f"└{'─'*29}┴{'─'*10}┴{'─'*12}┘"

    report_lines.append(header)
    report_lines.append(title_row)
    report_lines.append(divider)

    for scenario, f1, acc in results:
        report_lines.append(f"│ {scenario:<27} │ {f1:8.4f} │ {acc*100:9.1f}% │")

    report_lines.append(footer)
    
    report_text = "\n".join(report_lines)
    print("\nCross-Station Evaluation Results:")
    print(report_text)

    # Save to file
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    print(f"\nReport saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
