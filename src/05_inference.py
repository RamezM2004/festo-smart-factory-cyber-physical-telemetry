"""
05_inference.py
---------------
Real-time fault classifier for new MES4 CSV exports.

Usage:
    python 05_inference.py <path_to_new_csv.csv>

    Example:
        python 05_inference.py data/RASS_unknown_run.csv

Output:
    - Prints a timestamped fault timeline to the terminal
    - Saves inference_report.txt with per-window predictions
    - Shows summary: fault class breakdown + recommended actions

Model used: XGBoost (if available), otherwise Random Forest
"""

import os
import sys
import argparse
import joblib
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(__file__)
MODELS_DIR  = os.path.join(BASE_DIR, "models")
WINDOW_SIZE = 5

FEATURE_COLS = [
    "Pressure", "Flow",
    "ActivePowerL1", "ActivePowerL2", "ActivePowerL3", "ActivePowerTotal",
    "CurrentL1", "CurrentL2", "CurrentL3",
    "VoltageL1", "VoltageL2", "VoltageL3",
    "PowerFactorL1", "PowerFactorL2", "PowerFactorL3",
    "ReactivePowerL1", "ReactivePowerL2", "ReactivePowerL3", "ReactivePowerTotal",
]

# Recommended maintenance actions for each fault class
RECOMMENDED_ACTIONS = {
    "NORMAL":               "✅ No action required — machine operating normally.",
    "FM01_PRESSURE_DROP":   "⚠️  Check pneumatic supply pressure. Inspect push-in fittings and seals for leaks. Re-tighten or replace as needed.",
    "FM02_FLOW_RESTRICT":   "⚠️  Check flow control valves and pneumatic tubing for partial blockages or kinks. Clean or replace valve.",
    "FM03_FLOW_BLOCK":      "🔴 STOP STATION. Check for fully blocked actuator circuit or seized solenoid valve. Inspect and clear obstruction before restarting.",
    "FM04_OVERLOAD":        "⚠️  Motor drawing excess current. Check conveyor belt tension and bearing condition. Remove excess load from pallet. Schedule bearing inspection.",
    "FM05_IDLE_NO_LOAD":    "⚠️  Station cycling without workpiece. Check pallet feed upstream. Verify pallet-presence sensor alignment and calibration.",
    "FM06_SPEED_REDUCTION": "⚠️  Conveyor running below normal speed. Inspect belt tension and drive roller condition. Check speed parameter in MES4.",
    "FM07_PHASE_IMBALANCE": "⚠️  Three-phase power imbalance detected. Inspect and tighten terminal connections on all phases. Check phase fuses.",
    "FM08_SENSOR_OBSTRUCT": "⚠️  RASS ultrasonic sensor detection degraded. Clean sensor lens with dry cloth. Check for dust/oil contamination. Inspect mounting.",
    "FM09_INTERMITTENT":    "🔴 Intermittent supply interruptions detected. Inspect main air supply valve and relay contacts. Check for loose main terminal connections.",
    "FM10_OVERPRESSURE":    "⚠️  Supply pressure above nominal. Inspect and recalibrate pressure regulator. Reduce to ~6.9 bar to prevent seal wear.",
    "FM01_PRESSURE_LOW01":  "⚠️  Mild pressure drop (~6.5 bar) detected. Monitor closely — early-stage seal wear or minor leak likely. Schedule FRL inspection.",
    "FM01_PRESSURE_LOW02":  "⚠️  Moderate pressure drop (~5.5 bar) detected. Actuator performance degrading. Inspect push-in fittings and FRL regulator. Replace worn seals.",
    "FM01_PRESSURE_LOW03":  "🔴 Severe pressure drop (~4.5 bar) detected. Actuators at risk of failure. Immediate FRL regulator and seal inspection required.",
    "STANDBY":              "ℹ️ Station in Standby / Quiescent state (no active motion, no carrier present).",
}

# RASS HMI Error Class context for each fault
RASS_ERROR_CLASS = {
    "NORMAL":               "Class 2 / No event",
    "STANDBY":              "Class 2 / No event (Standby)",
    "FM01_PRESSURE_DROP":   "Class 1 — Cycle Stop (Gripper/actuator timeout likely)",
    "FM02_FLOW_RESTRICT":   "Class 1 — Cycle Stop (Timeout: final position not reached)",
    "FM03_FLOW_BLOCK":      "Class 0 — CRITICAL (Stopper/actuator not releasing; immediate stop)",
    "FM04_OVERLOAD":        "Class 1 — Cycle Stop (Motor I²t overload warning possible)",
    "FM05_IDLE_NO_LOAD":    "Class 2 — Warning (Workpiece not detected; pick NOK)",
    "FM06_SPEED_REDUCTION": "Class 2 — Warning (Extended transport timeout possible)",
    "FM07_PHASE_IMBALANCE": "Class 1 — Cycle Stop (Power anomaly on one phase)",
    "FM08_SENSOR_OBSTRUCT": "Class 1 — Cycle Stop (Pick NOK; workpiece not gripped event)",
    "FM09_INTERMITTENT":    "Class 0 — CRITICAL (Emergency/supply interruption event)",
    "FM10_OVERPRESSURE":    "Class 2 — Warning (High pressure; monitor for seal degradation)",
    "FM01_PRESSURE_LOW01":  "Class 2 — Warning (Early pressure degradation; preventive check)",
    "FM01_PRESSURE_LOW02":  "Class 1 — Cycle Stop (Moderate pressure loss; actuator timeout risk)",
    "FM01_PRESSURE_LOW03":  "Class 0 — CRITICAL (Severe pressure loss; imminent actuator failure)",
}


# ── Feature Engineering ────────────────────────────────────────────────────────

def engineer_features_single(df: pd.DataFrame, window: int = WINDOW_SIZE) -> pd.DataFrame:
    """Build feature windows for inference (no label column needed)."""
    records = []
    raw = df[FEATURE_COLS].copy()
    timestamps = df.iloc[:, 0].values if df.columns[0] in ("Timestamp", "time") else [f"row_{i}" for i in range(len(df))]

    for i in range(0, len(raw) - window + 1, window):
        win = raw.iloc[i : i + window]
        feat = {"window_start": timestamps[i], "window_end": timestamps[min(i + window - 1, len(raw) - 1)]}

        for col in FEATURE_COLS:
            vals = win[col].dropna()
            feat[f"{col}_mean"]  = vals.mean()  if len(vals) > 0 else np.nan
            feat[f"{col}_std"]   = vals.std()   if len(vals) > 1 else 0.0
            feat[f"{col}_min"]   = vals.min()   if len(vals) > 0 else np.nan
            feat[f"{col}_max"]   = vals.max()   if len(vals) > 0 else np.nan
            feat[f"{col}_delta"] = (float(vals.iloc[-1]) - float(vals.iloc[0])) if len(vals) > 1 else 0.0

        p_mean = feat.get("Pressure_mean", np.nan)
        f_mean = feat.get("Flow_mean", np.nan)
        feat["flow_pressure_ratio"] = (f_mean / p_mean) if (p_mean and p_mean != 0) else np.nan
        ph = [feat.get(f"ActivePowerL{i}_mean", np.nan) for i in [1,2,3]]
        ph_v = [v for v in ph if not np.isnan(v)]
        feat["phase_imbalance"] = (max(ph_v) - min(ph_v)) if len(ph_v) == 3 else np.nan
        feat["power_flow_ratio"] = (feat.get("ActivePowerTotal_mean", np.nan) / f_mean) if (f_mean and f_mean > 0) else np.nan
        curr = [feat.get(f"CurrentL{j}_mean", np.nan) for j in [1,2,3]]
        curr_v = [v for v in curr if not np.isnan(v)]
        feat["current_imbalance"] = (max(curr_v) - min(curr_v)) if len(curr_v) == 3 else np.nan
        feat["pressure_variability"] = feat.get("Pressure_std", np.nan)

        records.append(feat)

    return pd.DataFrame(records)


# ── Load Model ─────────────────────────────────────────────────────────────────

def load_best_model():
    """Load XGBoost if available, fall back to Random Forest."""
    xgb_path = os.path.join(MODELS_DIR, "xgb_model.pkl")
    rf_path  = os.path.join(MODELS_DIR, "rf_model.pkl")

    if os.path.isfile(xgb_path):
        bundle = joblib.load(xgb_path)
        model_name = "XGBoost"
    elif os.path.isfile(rf_path):
        bundle = joblib.load(rf_path)
        model_name = "Random Forest"
    else:
        print("[ERROR] No trained model found in models/ directory.")
        print("  Run: python 03_train_classifier.py   first.")
        sys.exit(1)

    return bundle["pipeline"], bundle["label_encoder"], bundle["feature_cols"], model_name


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Real-time fault classifier for MES4 CSV exports.")
    parser.add_argument("csv_path", type=str, help="Path to the input CSV file")
    parser.add_argument("--station", type=str, default="auto", help="Station name (auto, RASS, MPRESS, CP_LINE)")
    args = parser.parse_args()

    csv_path = args.csv_path
    
    # Infer station
    station = args.station
    if station == "auto":
        fname = os.path.basename(csv_path).upper()
        if "RASS" in fname:
            station = "RASS"
        elif "MPRESS" in fname:
            station = "MPRESS"
        elif "CP" in fname:
            station = "CP_LINE"
        else:
            station = "UNKNOWN"

    if not os.path.isfile(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    # 1. Load CSV
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df.replace("null", np.nan, inplace=True)
    # Handle duplicate columns by keeping the first occurrence
    df = df.loc[:, ~df.columns.duplicated()]
    col_remap = {"0 - Active Power Total [W]": "ActivePowerTotal", "Pressure1": "Pressure", "Flow1": "Flow"}
    df.rename(columns=col_remap, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()]

    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan
        series = df[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        df[col] = pd.to_numeric(series, errors="coerce")

    print(f"\n{'═'*65}")
    print(f"  Smart Maintenance — Real-Time Fault Inference")
    print(f"  Station: {station}")
    print(f"  File   : {os.path.basename(csv_path)}")
    print(f"  Rows   : {len(df)} seconds of data")
    print(f"{'═'*65}")

    # 2. Load model
    pipeline, le, feat_cols, model_name = load_best_model()
    print(f"  Model  : {model_name}")

    # 3. Engineer features
    df_feat = engineer_features_single(df, window=WINDOW_SIZE)
    n_windows = len(df_feat)
    print(f"  Windows: {n_windows} (each = {WINDOW_SIZE}s)\n")

    if n_windows == 0:
        print("[ERROR] Not enough data rows to form even one window. Need at least 5 rows.")
        sys.exit(1)

    # 4. Predict
    X = df_feat[feat_cols].values
    y_pred_enc = pipeline.predict(X)
    y_prob     = pipeline.predict_proba(X)
    y_pred     = le.inverse_transform(y_pred_enc)
    confidence = np.max(y_prob, axis=1) * 100

    df_feat["prediction"]  = y_pred
    df_feat["confidence%"] = confidence.round(1)

    # 5. Print timeline
    print(f"  {'Window':<8}  {'Time':<12}  {'Prediction':<30}  {'Confidence':>10}")
    print(f"  {'─'*8}  {'─'*12}  {'─'*30}  {'─'*10}")
    for idx, row in df_feat.iterrows():
        flag = "🔴" if row["prediction"] not in ("NORMAL",) else "✅"
        print(f"  {idx+1:<8}  {str(row['window_start']):<12}  {flag} {row['prediction']:<28}  {row['confidence%']:>8.1f}%")

    # 6. Summary
    fault_counts = df_feat["prediction"].value_counts()
    dominant_fault = fault_counts.index[0]
    dominant_pct = fault_counts.iloc[0] / n_windows * 100

    print(f"\n{'─'*65}")
    print(f"  SUMMARY")
    print(f"{'─'*65}")
    for fault_class, count in fault_counts.items():
        pct = count / n_windows * 100
        bar = "█" * int(pct / 5)
        print(f"  {fault_class:<30}  {count:>3} windows  ({pct:5.1f}%)  {bar}")

    print(f"\n  ► DOMINANT CONDITION: {dominant_fault} ({dominant_pct:.1f}% of run)")
    print(f"\n  ► RECOMMENDED ACTION:")
    print(f"  {RECOMMENDED_ACTIONS.get(dominant_fault, 'Review data manually.')}")
    print(f"\n  ► RASS HMI ERROR CLASS:")
    print(f"  {RASS_ERROR_CLASS.get(dominant_fault, 'Unknown')}")

    # 7. Save report
    report_lines = [
        f"Smart Maintenance — Inference Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Station: {station}",
        f"File: {csv_path}",
        f"Model: {model_name}",
        f"Windows analysed: {n_windows}",
        f"",
        f"TIMELINE:",
    ]
    for idx, row in df_feat.iterrows():
        report_lines.append(f"  Window {idx+1}  {row['window_start']} → {row['window_end']}  |  {row['prediction']}  ({row['confidence%']}%)")

    report_lines += [
        f"",
        f"FAULT CLASS DISTRIBUTION:",
    ]
    for fault_class, count in fault_counts.items():
        report_lines.append(f"  {fault_class}: {count} windows ({count/n_windows*100:.1f}%)")

    report_lines += [
        f"",
        f"DOMINANT CONDITION: {dominant_fault}",
        f"RECOMMENDED ACTION: {RECOMMENDED_ACTIONS.get(dominant_fault, 'Review manually.')}",
        f"RASS HMI ERROR CLASS: {RASS_ERROR_CLASS.get(dominant_fault, 'Unknown')}",
    ]

    report_path = os.path.join(BASE_DIR, "inference_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n  ✓ Full report saved → inference_report.txt")
    print(f"{'═'*65}\n")


if __name__ == "__main__":
    main()
