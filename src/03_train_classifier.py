"""
03_train_classifier.py
----------------------
Reads labeled_dataset.csv, engineers time-series features using a
rolling window, then trains and saves two supervised classifiers:
  1. Random Forest  → models/rf_model.pkl
  2. XGBoost        → models/xgb_model.pkl

Usage:
    python 03_train_classifier.py

Requirements:
    pip install scikit-learn xgboost pandas numpy joblib
"""

import os
import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(__file__)
DATASET_FILE  = os.path.join(BASE_DIR, "labeled_dataset.csv")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
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

    # Group by label so windows don't span across different fault sessions
    for label, group in df.groupby("label", sort=False):
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
            records.append(feat)

    return pd.DataFrame(records)


# ── Training ───────────────────────────────────────────────────────────────────

def train(df_features: pd.DataFrame, label_encoder: LabelEncoder):
    """Train Random Forest and XGBoost, return fitted models."""
    feature_cols = [c for c in df_features.columns if c != "label"]
    X = df_features[feature_cols].values
    y = label_encoder.transform(df_features["label"])

    # Imputer handles any remaining NaN values
    imputer = SimpleImputer(strategy="mean")

    print(f"\n{'═'*60}")
    print(f"  Training on {len(X)} windows | {len(feature_cols)} features | {len(label_encoder.classes_)} classes")
    print(f"  Classes: {list(label_encoder.classes_)}")
    print(f"{'═'*60}\n")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # ── 1. Random Forest ─────────────────────────────────────────────────────
    print("▶ Training Random Forest ...")
    rf_pipe = Pipeline([
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
    rf_scores = cross_val_score(rf_pipe, X, y, cv=cv, scoring="f1_weighted", n_jobs=-1)
    rf_pipe.fit(X, y)

    print(f"  Random Forest — Weighted F1: {rf_scores.mean():.4f} ± {rf_scores.std():.4f}")

    # ── 2. XGBoost ───────────────────────────────────────────────────────────
    try:
        from xgboost import XGBClassifier
        print("\n▶ Training XGBoost ...")
        xgb_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="mean")),
            ("clf", XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="mlogloss",
                random_state=42,
                n_jobs=-1,
                verbosity=0,
            )),
        ])
        xgb_scores = cross_val_score(xgb_pipe, X, y, cv=cv, scoring="f1_weighted", n_jobs=-1)
        xgb_pipe.fit(X, y)
        print(f"  XGBoost        — Weighted F1: {xgb_scores.mean():.4f} ± {xgb_scores.std():.4f}")
        best_model = xgb_pipe if xgb_scores.mean() >= rf_scores.mean() else rf_pipe
        best_name = "XGBoost" if xgb_scores.mean() >= rf_scores.mean() else "Random Forest"
    except ImportError:
        print("  [WARN] XGBoost not installed — using Random Forest only.")
        print("         Install with: pip install xgboost")
        xgb_pipe = None
        best_model = rf_pipe
        best_name = "Random Forest"

    return rf_pipe, xgb_pipe, best_model, best_name, feature_cols


# ── Save ───────────────────────────────────────────────────────────────────────

def save_models(rf_pipe, xgb_pipe, label_encoder, feature_cols):
    os.makedirs(MODELS_DIR, exist_ok=True)

    joblib.dump({
        "pipeline":      rf_pipe,
        "label_encoder": label_encoder,
        "feature_cols":  feature_cols,
        "window_size":   WINDOW_SIZE,
    }, os.path.join(MODELS_DIR, "rf_model.pkl"))
    print(f"\n  ✓ Random Forest saved → models/rf_model.pkl")

    if xgb_pipe is not None:
        joblib.dump({
            "pipeline":      xgb_pipe,
            "label_encoder": label_encoder,
            "feature_cols":  feature_cols,
            "window_size":   WINDOW_SIZE,
        }, os.path.join(MODELS_DIR, "xgb_model.pkl"))
        print(f"  ✓ XGBoost       saved → models/xgb_model.pkl")

    # Save feature column list for inference script
    joblib.dump(feature_cols, os.path.join(MODELS_DIR, "feature_cols.pkl"))
    joblib.dump(label_encoder, os.path.join(MODELS_DIR, "label_encoder.pkl"))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # 1. Load dataset
    if not os.path.isfile(DATASET_FILE):
        print(f"[ERROR] labeled_dataset.csv not found at: {DATASET_FILE}")
        print("  Run: python 02_build_dataset.py   first.")
        sys.exit(1)

    print(f"Loading dataset from: {DATASET_FILE}")
    df = pd.read_csv(DATASET_FILE)
    print(f"  {len(df)} rows | {df['label'].nunique()} classes")

    # 2. Engineer features
    print(f"\nEngineering features (window = {WINDOW_SIZE}s) ...")
    df_features = engineer_features(df, window=WINDOW_SIZE)
    print(f"  Feature matrix: {df_features.shape[0]} windows × {df_features.shape[1]-1} features")

    # Drop windows where label is missing
    df_features.dropna(subset=["label"], inplace=True)

    # 3. Encode labels
    label_encoder = LabelEncoder()
    label_encoder.fit(df_features["label"])

    # 4. Train
    rf_pipe, xgb_pipe, best_model, best_name, feature_cols = train(df_features, label_encoder)

    # 5. Save
    save_models(rf_pipe, xgb_pipe, label_encoder, feature_cols)

    print(f"\n{'═'*60}")
    print(f"  Best model: {best_name}")
    print(f"  Training complete. Next step:")
    print(f"    python 04_evaluate_model.py")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
