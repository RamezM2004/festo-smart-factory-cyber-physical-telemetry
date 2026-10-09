"""
07_hierarchical_diagnostic.py
-----------------------------
Compares fault classification accuracy across different data views:
Local station only (RASS), Central header only (CP_LINE), and Fused.

Performs Pillar 1 of the Plan B research scope.

Usage:
    python 07_hierarchical_diagnostic.py
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, accuracy_score

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(__file__)
DATASET_FILE  = os.path.join(BASE_DIR, "labeled_dataset.csv")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
REPORT_FILE   = os.path.join(MODELS_DIR, "hierarchical_diagnostic_report.txt")
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
    """
    records = []

    # Group by station and label so windows don't span across different fault sessions
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

            feat["station"] = station
            feat["label"] = label
            records.append(feat)

    return pd.DataFrame(records)

# ── Experiments ────────────────────────────────────────────────────────────────

def build_pipeline():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])

def evaluate_cv(X, y):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pipeline = build_pipeline()
    
    y_pred = cross_val_predict(pipeline, X, y, cv=cv, n_jobs=-1)
    
    f1 = f1_score(y, y_pred, average="weighted")
    acc = accuracy_score(y, y_pred)
    
    return f1, acc

def evaluate_transfer(X_train, y_train, X_test, y_test):
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    
    f1 = f1_score(y_test, y_pred, average="weighted")
    acc = accuracy_score(y_test, y_pred)
    
    return f1, acc

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.isfile(DATASET_FILE):
        print(f"[ERROR] labeled_dataset.csv not found at: {DATASET_FILE}")
        sys.exit(1)

    print(f"Loading dataset from: {DATASET_FILE}")
    df = pd.read_csv(DATASET_FILE)
    
    if "station" not in df.columns or "label" not in df.columns:
        print("[ERROR] Dataset missing 'station' or 'label' columns.")
        sys.exit(1)
        
    df = df[df["station"].isin(["RASS", "CP_LINE"])]
    if len(df) == 0:
        print("[ERROR] No RASS or CP_LINE data found.")
        sys.exit(1)
        
    rass_labels = set(df[df["station"] == "RASS"]["label"].unique())
    cp_labels = set(df[df["station"] == "CP_LINE"]["label"].unique())
    
    common_labels = rass_labels.intersection(cp_labels)
    if not common_labels:
        print("[ERROR] No common labels between RASS and CP_LINE views.")
        sys.exit(1)
        
    df = df[df["label"].isin(common_labels)]
    print(f"Filtered to common labels: {common_labels}")
    print(f"Engineering features (window = {WINDOW_SIZE}s) ...")
    
    df_features = engineer_features(df, window=WINDOW_SIZE)
    df_features.dropna(subset=["label"], inplace=True)
    
    label_encoder = LabelEncoder()
    df_features["label_enc"] = label_encoder.fit_transform(df_features["label"])
    
    df_rass = df_features[df_features["station"] == "RASS"]
    df_cp = df_features[df_features["station"] == "CP_LINE"]
    
    if len(df_rass) == 0 or len(df_cp) == 0:
        print("[ERROR] Insufficient data after feature engineering for one or both views.")
        sys.exit(1)
        
    feature_cols = [c for c in df_features.columns if c not in ["station", "label", "label_enc"]]
    
    X_rass = df_rass[feature_cols].values
    y_rass = df_rass["label_enc"].values
    
    X_cp = df_cp[feature_cols].values
    y_cp = df_cp["label_enc"].values
    
    X_fused = df_features[feature_cols].values
    y_fused = df_features["label_enc"].values
    
    print("Running Experiment A: RASS-Only...")
    f1_a, acc_a = evaluate_cv(X_rass, y_rass)
    
    print("Running Experiment B: CP_LINE-Only...")
    f1_b, acc_b = evaluate_cv(X_cp, y_cp)
    
    print("Running Experiment C: RASS → CP_LINE...")
    f1_c1, acc_c1 = evaluate_transfer(X_rass, y_rass, X_cp, y_cp)
    
    print("Running Experiment C: CP_LINE → RASS...")
    f1_c2, acc_c2 = evaluate_transfer(X_cp, y_cp, X_rass, y_rass)
    
    print("Running Experiment D: Fused RASS+CP_LINE...")
    f1_d, acc_d = evaluate_cv(X_fused, y_fused)
    
    report_lines = [
        "┌──────────────────────────────────────────┬──────────┬────────────┐",
        "│ Experiment                               │ F1 Score │ Accuracy   │",
        "├──────────────────────────────────────────┼──────────┼────────────┤",
        f"│ A: RASS-Only (Local Station)             │  {f1_a:.4f}  │  {acc_a*100:5.1f}%    │",
        f"│ B: CP_LINE-Only (Central Header)         │  {f1_b:.4f}  │  {acc_b*100:5.1f}%    │",
        f"│ C: RASS → CP_LINE (Cross-View Transfer)  │  {f1_c1:.4f}  │  {acc_c1*100:5.1f}%    │",
        f"│ C: CP_LINE → RASS (Cross-View Transfer)  │  {f1_c2:.4f}  │  {acc_c2*100:5.1f}%    │",
        f"│ D: Fused RASS+CP_LINE (Combined)         │  {f1_d:.4f}  │  {acc_d*100:5.1f}%    │",
        "└──────────────────────────────────────────┴──────────┴────────────┘"
    ]
    
    report_str = "\n".join(report_lines)
    print("\n" + report_str)
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("Hierarchical Diagnostic Report\n")
        f.write("==============================\n\n")
        f.write(report_str + "\n")
        
    print(f"\nReport saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
