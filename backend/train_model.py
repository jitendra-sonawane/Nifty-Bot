"""
Signal Quality ML Model — Training Script
==========================================

Trains a GradientBoostingClassifier on labeled trade data collected by
AIDataCollector, then saves the model to app/intelligence/signal_model.pkl.

Usage:
    python train_model.py
    python train_model.py --csv path/to/ai_training_data.csv
    python train_model.py --min-samples 50   # lower threshold for early runs

The model predicts: P(outcome=WIN | features_at_entry)
This score is used in check_signal() as an optional confidence booster.
"""

import argparse
import sys
import os
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# ── Config ──────────────────────────────────────────────────────────────────

MODEL_OUT   = os.path.join(os.path.dirname(__file__), "app", "intelligence", "signal_model.pkl")
DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "ai_training_data.csv")
MIN_SAMPLES = 50   # minimum labeled trades before training is meaningful

# Features used for training (must match AIDataCollector.FEATURE_COLS)
NUMERIC_FEATURES = [
    "rsi", "supertrend", "ema_diff_pct", "atr_pct",
    "pcr", "ce_delta", "pe_delta", "ce_theta", "pe_theta", "ce_iv", "pe_iv",
    "vix", "adx", "iv_rank",
    "hour", "minute", "day_of_week",
]

CATEGORICAL_FEATURES = ["signal", "pcr_trend", "regime", "breadth_bias"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_data(csv_path: str) -> pd.DataFrame:
    """Load and validate training CSV."""
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        sys.exit(1)

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        # Old format without header
        from app.utils.ai_data_collector import FEATURE_COLS
        df = pd.read_csv(csv_path, header=None, names=FEATURE_COLS)

    print(f"[INFO] Loaded {len(df)} rows from {csv_path}")

    # Drop rows without outcome label
    before = len(df)
    df = df[df["outcome"].notna()].copy()
    skipped = before - len(df)
    if skipped > 0:
        print(f"[WARN] Dropped {skipped} unlabeled rows (exits not yet recorded)")

    print(f"[INFO] Labeled samples: {len(df)}")

    if len(df) == 0:
        print("[ERROR] No labeled samples. Run the system longer to collect trade outcomes.")
        sys.exit(1)

    return df


def encode_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Encode categoricals, build full feature matrix."""
    encoders = {}

    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            le = LabelEncoder()
            df[col] = df[col].fillna("UNKNOWN")
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            df[col] = 0

    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    for col in all_features:
        if col not in df.columns:
            df[col] = np.nan

    return df[all_features], encoders


def train(csv_path: str, min_samples: int):
    df = load_data(csv_path)

    if len(df) < min_samples:
        print(
            f"[WARN] Only {len(df)} labeled samples (recommended ≥ {min_samples}). "
            f"Model will train but may not generalize. Collect more data for better accuracy."
        )

    # ── Class distribution ────────────────────────────────────────────────
    outcome = df["outcome"].astype(int)
    wins = outcome.sum()
    losses = len(outcome) - wins
    print(f"[INFO] Win/Loss: {wins}/{losses} = {wins/max(len(outcome),1)*100:.1f}% win rate")

    X, encoders = encode_features(df)
    y = outcome.values

    # ── Pipeline ─────────────────────────────────────────────────────────
    # Impute missing values → GradientBoosting
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=max(2, len(df) // 20),  # scale with data size
            random_state=42,
        )),
    ])

    # ── Cross-validation ─────────────────────────────────────────────────
    n_splits = min(5, max(2, wins, losses))  # at least 2, at most 5 splits
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(pipeline, X, y, cv=cv, scoring="roc_auc")
        print(f"[INFO] Cross-val ROC-AUC: {scores.mean():.3f} ± {scores.std():.3f} (splits={n_splits})")

    # ── Full fit ──────────────────────────────────────────────────────────
    pipeline.fit(X, y)

    # ── Train-set report ──────────────────────────────────────────────────
    y_pred = pipeline.predict(X)
    y_prob = pipeline.predict_proba(X)[:, 1]
    print("\n[REPORT] Training set performance:")
    print(classification_report(y, y_pred, target_names=["LOSS", "WIN"], zero_division=0))
    print(f"[INFO] Train ROC-AUC: {roc_auc_score(y, y_prob):.3f}")

    # ── Feature importance ────────────────────────────────────────────────
    model = pipeline.named_steps["model"]
    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    importances = sorted(
        zip(all_features, model.feature_importances_), key=lambda x: x[1], reverse=True
    )
    print("\n[INFO] Top 10 predictive features:")
    for feat, imp in importances[:10]:
        bar = "█" * int(imp * 100)
        print(f"  {feat:20s} {imp:.4f} {bar}")

    # ── Save model ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    bundle = {
        "pipeline":    pipeline,
        "encoders":    encoders,
        "features":    all_features,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "n_samples":   len(df),
        "win_rate":    wins / max(len(outcome), 1),
        "roc_auc":     float(roc_auc_score(y, y_prob)),
        "trained_at":  pd.Timestamp.now().isoformat(),
    }
    joblib.dump(bundle, MODEL_OUT)
    print(f"\n[OK] Model saved to {MODEL_OUT}")
    print(f"[OK] To use: load via SignalMLModel (app/intelligence/signal_model.py)")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train signal quality ML model")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to ai_training_data.csv")
    parser.add_argument("--min-samples", type=int, default=MIN_SAMPLES,
                        help="Minimum labeled rows before warning (default 50)")
    args = parser.parse_args()
    train(args.csv, args.min_samples)
