"""
SignalMLModel — Lightweight wrapper around the trained GradientBoosting model.

Loads the model saved by train_model.py and exposes a single method:

    score = model.predict_win_probability(features_dict)

Returns a float 0.0–1.0: estimated probability that the current setup leads to a WIN.
Returns None if model not loaded (degrades gracefully — signal logic continues without it).

Integration:
    Added as an optional confidence modifier in StrategyEngine.check_signal().
    Does NOT block signals on its own — only influences the confidence score.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "signal_model.pkl")
MIN_USEFUL_ROC_AUC = 0.55   # below this the model is no better than random — ignore it


class SignalMLModel:
    """
    Lazy-loading ML model for signal win-probability estimation.

    Usage:
        ml = SignalMLModel()
        prob = ml.predict_win_probability({"rsi": 62, "pcr": 1.1, "vix": 14, ...})
        # prob is float 0-1 or None if model unavailable
    """

    def __init__(self, model_path: str = MODEL_PATH):
        self._path = model_path
        self._bundle = None
        self._failed = False   # stop re-trying after a load error

    def _load(self):
        """Lazy-load model bundle. Safe to call multiple times."""
        if self._bundle is not None or self._failed:
            return

        if not os.path.exists(self._path):
            logger.debug(f"SignalMLModel: model file not found at {self._path}. "
                         f"Run train_model.py to build it.")
            self._failed = True
            return

        try:
            import joblib
            bundle = joblib.load(self._path)
            roc = bundle.get("roc_auc", 0)
            n   = bundle.get("n_samples", 0)

            if roc < MIN_USEFUL_ROC_AUC:
                logger.warning(
                    f"SignalMLModel: ROC-AUC={roc:.3f} < {MIN_USEFUL_ROC_AUC} threshold — "
                    f"model trained on {n} samples is not yet reliable. Predictions disabled."
                )
                self._failed = True
                return

            self._bundle = bundle
            logger.info(
                f"SignalMLModel loaded: n_samples={n} | ROC-AUC={roc:.3f} | "
                f"trained_at={bundle.get('trained_at','?')}"
            )

        except Exception as e:
            logger.warning(f"SignalMLModel: failed to load model — {e}")
            self._failed = True

    @property
    def is_available(self) -> bool:
        """True if model is loaded and reliable."""
        self._load()
        return self._bundle is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """Return model metadata for API / frontend display."""
        if not self.is_available:
            return {"available": False, "reason": "Model not trained yet — run train_model.py"}
        b = self._bundle
        return {
            "available":   True,
            "n_samples":   b.get("n_samples"),
            "win_rate":    round(b.get("win_rate", 0) * 100, 1),
            "roc_auc":     round(b.get("roc_auc", 0), 3),
            "trained_at":  b.get("trained_at"),
        }

    def predict_win_probability(self, features: Dict[str, Any]) -> Optional[float]:
        """
        Predict probability of a winning trade given entry-state features.

        Args:
            features: Dict with any subset of the training features.
                      Missing values are imputed by the pipeline.

        Returns:
            float 0.0–1.0 win probability, or None if model unavailable.
        """
        self._load()
        if not self._bundle:
            return None

        try:
            import pandas as pd
            import numpy as np

            bundle = self._bundle
            pipeline = bundle["pipeline"]
            encoders = bundle["encoders"]
            all_features = bundle["features"]
            cat_features = bundle["categorical_features"]

            row = {}
            for feat in all_features:
                row[feat] = features.get(feat, np.nan)

            # Encode categoricals using fitted LabelEncoder
            for col in cat_features:
                le = encoders.get(col)
                if le is None:
                    row[col] = 0
                    continue
                val = str(row[col]) if row[col] is not None and not (
                    isinstance(row[col], float) and np.isnan(row[col])
                ) else "UNKNOWN"
                # Handle unseen labels gracefully
                if val not in le.classes_:
                    val = "UNKNOWN" if "UNKNOWN" in le.classes_ else le.classes_[0]
                row[col] = int(le.transform([val])[0])

            X = pd.DataFrame([row])[all_features]
            prob = float(pipeline.predict_proba(X)[0][1])
            return round(prob, 3)

        except Exception as e:
            logger.debug(f"SignalMLModel.predict failed: {e}")
            return None


# Module-level singleton — import and use anywhere
_default_model: Optional[SignalMLModel] = None


def get_model() -> SignalMLModel:
    """Return module-level singleton SignalMLModel."""
    global _default_model
    if _default_model is None:
        _default_model = SignalMLModel()
    return _default_model
