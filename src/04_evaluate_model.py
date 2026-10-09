"""
04_evaluate_model.py
--------------------
Loads the trained models and produces a full evaluation report:
  - Classification report (precision, recall, F1 per class)
  - Confusion matrix heatmap
  - Feature importance plot (Random Forest)
  - Per-class accuracy summary

Usage:
    python 04_evaluate_model.py

Outputs (saved to models/):
    confusion_matrix.png
    feature_importance.png
    evaluation_report.txt
"""

import os
import sys
import warnings
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(__file__)
DATASET_FILE = os.path.join(BASE_DIR, "labeled_dataset.csv")
MODELS_DIR   = os.path.join(BASE_DIR, "models")
WINDOW_SIZE  = 5


FEATURE_COLS = [
    "Pressure", "Flow",
    "ActivePowerL1", "ActivePowerL2", "ActivePowerL3", "ActivePowerTotal",
    "CurrentL1", "CurrentL2", "CurrentL3",
    "VoltageL1", "VoltageL2", "VoltageL3",
    "PowerFactorL1", "PowerFactorL2", "PowerFactorL3",
    "ReactivePowerL1", "ReactivePowerL2", "ReactivePowerL3", "ReactivePowerTotal",
]


def engineer_features_local(df: pd.DataFrame, window: int = WINDOW_SIZE) -> pd.DataFrame:
    """Duplicate of the feature engineering logic so this script is self-contained."""
    records = []
    for label, group in df.groupby("label", sort=False):
        group = group.reset_index(drop=True)
        raw = group[FEATURE_COLS].copy()
        for i in range(0, len(raw) - window + 1, window):
            win = raw.iloc[i : i + window]
            feat = {}
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
            curr = [feat.get(f"CurrentL{i}_mean", np.nan) for i in [1,2,3]]
            curr_v = [v for v in curr if not np.isnan(v)]
            feat["current_imbalance"] = (max(curr_v) - min(curr_v)) if len(curr_v) == 3 else np.nan
            feat["pressure_variability"] = feat.get("Pressure_std", np.nan)
            feat["label"] = label
            records.append(feat)
    return pd.DataFrame(records)


# ── Plotting Helpers ───────────────────────────────────────────────────────────

PALETTE = {
    "bg":      "#0f1117",
    "panel":   "#1a1d27",
    "accent":  "#f59e0b",
    "green":   "#22c55e",
    "red":     "#ef4444",
    "text":    "#e2e8f0",
    "muted":   "#64748b",
}

def set_dark_style():
    plt.rcParams.update({
        "figure.facecolor":  PALETTE["bg"],
        "axes.facecolor":    PALETTE["panel"],
        "axes.edgecolor":    PALETTE["muted"],
        "axes.labelcolor":   PALETTE["text"],
        "xtick.color":       PALETTE["text"],
        "ytick.color":       PALETTE["text"],
        "text.color":        PALETTE["text"],
        "grid.color":        PALETTE["muted"],
        "grid.alpha":        0.3,
        "font.family":       "DejaVu Sans",
        "font.size":         10,
    })


def plot_confusion_matrix(y_true, y_pred, class_names, out_path):
    set_dark_style()
    cm = confusion_matrix(y_true, y_pred, labels=class_names)
    cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100

    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(PALETTE["bg"])

    sns.heatmap(
        cm_pct,
        annot=True,
        fmt=".1f",
        xticklabels=[c.replace("_", "\n") for c in class_names],
        yticklabels=[c.replace("_", "\n") for c in class_names],
        cmap="YlOrRd",
        linewidths=0.5,
        linecolor=PALETTE["muted"],
        ax=ax,
        cbar_kws={"label": "% of True Class"},
    )
    ax.set_title("Fault Classifier — Confusion Matrix (%)", fontsize=14,
                 color=PALETTE["accent"], fontweight="bold", pad=16)
    ax.set_xlabel("Predicted Label", fontsize=11)
    ax.set_ylabel("True Label", fontsize=11)
    ax.tick_params(axis="both", labelsize=8)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Confusion matrix saved → {os.path.relpath(out_path)}")


def plot_feature_importance(rf_pipeline, feature_cols, out_path, top_n=25):
    set_dark_style()
    rf_clf = rf_pipeline.named_steps["clf"]
    importances = rf_clf.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(PALETTE["bg"])

    colors = [PALETTE["accent"] if i < 5 else PALETTE["green"] for i in range(top_n)]
    bars = ax.barh(
        [feature_cols[i].replace("_", " ") for i in reversed(indices)],
        [importances[i] for i in reversed(indices)],
        color=list(reversed(colors)),
        edgecolor="none",
        height=0.7,
    )

    ax.set_title(f"Random Forest — Top {top_n} Feature Importances",
                 fontsize=14, color=PALETTE["accent"], fontweight="bold", pad=16)
    ax.set_xlabel("Mean Decrease in Impurity (MDI)", fontsize=11)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=1))
    ax.grid(axis="x", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Feature importance saved → {os.path.relpath(out_path)}")


def plot_per_class_f1(report_dict, class_names, out_path):
    set_dark_style()
    f1_scores = [report_dict.get(c, {}).get("f1-score", 0) for c in class_names]
    colors = [PALETTE["green"] if f >= 0.85 else PALETTE["accent"] if f >= 0.65 else PALETTE["red"]
              for f in f1_scores]

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor(PALETTE["bg"])

    bars = ax.bar([c.replace("_", "\n") for c in class_names], f1_scores,
                  color=colors, edgecolor="none", width=0.6)

    for bar, score in zip(bars, f1_scores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{score:.2f}", ha="center", va="bottom", fontsize=9,
                color=PALETTE["text"])

    ax.axhline(0.85, color=PALETTE["green"], linestyle="--", alpha=0.6, linewidth=1, label="World-class (0.85)")
    ax.axhline(0.65, color=PALETTE["accent"], linestyle="--", alpha=0.6, linewidth=1, label="Acceptable (0.65)")
    ax.set_ylim(0, 1.12)
    ax.set_title("Per-Class F1 Score", fontsize=14, color=PALETTE["accent"],
                 fontweight="bold", pad=16)
    ax.set_ylabel("F1 Score", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Per-class F1 chart saved → {os.path.relpath(out_path)}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # 1. Load dataset
    if not os.path.isfile(DATASET_FILE):
        print(f"[ERROR] labeled_dataset.csv not found. Run 02_build_dataset.py first.")
        sys.exit(1)

    df = pd.read_csv(DATASET_FILE)
    print(f"Dataset: {len(df)} rows | {df['label'].nunique()} classes")

    # 2. Engineer features
    print(f"Engineering features (window={WINDOW_SIZE}s) ...")
    df_feat = engineer_features_local(df, window=WINDOW_SIZE)
    df_feat.dropna(subset=["label"], inplace=True)

    # 3. Load models
    rf_path  = os.path.join(MODELS_DIR, "rf_model.pkl")
    xgb_path = os.path.join(MODELS_DIR, "xgb_model.pkl")

    if not os.path.isfile(rf_path):
        print("[ERROR] rf_model.pkl not found. Run 03_train_classifier.py first.")
        sys.exit(1)

    rf_bundle  = joblib.load(rf_path)
    rf_pipe    = rf_bundle["pipeline"]
    le         = rf_bundle["label_encoder"]
    feat_cols  = rf_bundle["feature_cols"]

    # 4. Hold-out test set (20%)
    feature_matrix = df_feat[feat_cols].values
    y_encoded      = le.transform(df_feat["label"])

    X_train, X_test, y_train, y_test = train_test_split(
        feature_matrix, y_encoded,
        test_size=0.2, stratify=y_encoded, random_state=42
    )

    # 5. Evaluate Random Forest
    print("\n── Random Forest Evaluation ──────────────────────────────────────")
    y_pred_rf = rf_pipe.predict(X_test)
    report_rf = classification_report(
        y_test, y_pred_rf,
        target_names=le.classes_,
        output_dict=True,
        zero_division=0,
    )
    print(classification_report(y_test, y_pred_rf, target_names=le.classes_, zero_division=0))

    # 6. Evaluate XGBoost (if available)
    xgb_pipe = None
    report_xgb = None
    if os.path.isfile(xgb_path):
        print("── XGBoost Evaluation ────────────────────────────────────────────")
        xgb_bundle = joblib.load(xgb_path)
        xgb_pipe   = xgb_bundle["pipeline"]
        y_pred_xgb = xgb_pipe.predict(X_test)
        report_xgb = classification_report(
            y_test, y_pred_xgb,
            target_names=le.classes_,
            output_dict=True,
            zero_division=0,
        )
        print(classification_report(y_test, y_pred_xgb, target_names=le.classes_, zero_division=0))

    # 7. Choose best model for plots
    if report_xgb:
        best_pred   = y_pred_xgb if report_xgb["weighted avg"]["f1-score"] >= report_rf["weighted avg"]["f1-score"] else y_pred_rf
        best_report = report_xgb if report_xgb["weighted avg"]["f1-score"] >= report_rf["weighted avg"]["f1-score"] else report_rf
        best_label  = "XGBoost" if report_xgb["weighted avg"]["f1-score"] >= report_rf["weighted avg"]["f1-score"] else "Random Forest"
    else:
        best_pred, best_report, best_label = y_pred_rf, report_rf, "Random Forest"

    print(f"\n★ Best model: {best_label}  (weighted F1 = {best_report['weighted avg']['f1-score']:.4f})")

    # 8. Generate plots
    os.makedirs(MODELS_DIR, exist_ok=True)
    class_names = list(le.classes_)

    plot_confusion_matrix(
        le.inverse_transform(y_test),
        le.inverse_transform(best_pred),
        class_names,
        os.path.join(MODELS_DIR, "confusion_matrix.png"),
    )

    plot_feature_importance(
        rf_pipe, feat_cols,
        os.path.join(MODELS_DIR, "feature_importance.png"),
    )

    plot_per_class_f1(
        best_report, class_names,
        os.path.join(MODELS_DIR, "per_class_f1.png"),
    )

    # 9. Save text report
    report_path = os.path.join(MODELS_DIR, "evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Smart Maintenance Fault Classifier - Evaluation Report\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"Best Model: {best_label}\n")
        f.write(f"Test Set Size: {len(y_test)} windows\n")
        f.write(f"Window Size: {WINDOW_SIZE} seconds\n")
        f.write(f"Classes: {', '.join(class_names)}\n\n")
        f.write("-- Random Forest --\n")
        f.write(classification_report(y_test, y_pred_rf, target_names=le.classes_, zero_division=0))
        if report_xgb:
            f.write("\n-- XGBoost --\n")
            f.write(classification_report(y_test, y_pred_xgb, target_names=le.classes_, zero_division=0))
    print(f"  [OK] Report saved -> {os.path.relpath(report_path)}")

    print(f"\n{'='*65}")
    print(f"  SUMMARY")
    print(f"{'='*65}")
    print(f"  All outputs saved to: models/")
    print(f"  Next step: python 05_inference.py <path_to_new_csv>")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
