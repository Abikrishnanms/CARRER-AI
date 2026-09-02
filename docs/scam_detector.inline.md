**Scam Detector — `ml/scam_detector/model.py` (Annotated copy)**

Summary: Inference wrapper for the trained scam detector (XGBoost). Exposes `predict`, `classify`, and `predict_batch` with a rule-based fallback when no model is present.

---

```python
"""
ml/scam_detector/model.py — Inference-only wrapper for the trained scam detector.

Provides a clean, import-friendly API over the pickled XGBoost model trained
by train.py, without requiring xgboost at import time (lazy import on first use).
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

from ml.scam_detector.train import extract_features, FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.environ.get(
    "SCAM_MODEL_PATH",
    "ml/scam_detector/model.pkl",
)

# Thresholds
_SCAM_THRESHOLD = 0.70        # above → scam
_SUSPICIOUS_THRESHOLD = 0.40  # above → suspicious, below → legitimate


class ScamDetectorModel:
    """
    Inference wrapper around the trained XGBoost scam detector.

    Falls back gracefully to rule-based scoring if no trained model exists.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or _DEFAULT_MODEL_PATH
        self._model: Any = None
        self._feature_cols: list[str] = FEATURE_COLUMNS
        self._loaded = False
        self._load()

    def _load(self) -> None:
        # Load pickled model bundle if present; set _loaded flag
        ...

    def predict(self, job: dict[str, Any]) -> float:
        # Return scam probability. Use ML model if loaded, else use _rule_based_score
        ...

    def classify(self, job: dict[str, Any]) -> str:
        # Translate probability into 'scam'|'suspicious'|'legitimate'
        ...

    def predict_batch(self, jobs: list[dict[str, Any]]) -> list[float]:
        # Vectorised batch prediction with ML fallback to rule-based
        ...

    @staticmethod
    def _rule_based_score(features: dict[str, Any]) -> float:
        # Lightweight rule-based scoring using high/medium/low signals
        ...

    @property
    def is_ml_loaded(self) -> bool:
        return self._loaded

    @property
    def model_path(self) -> str:
        return self._model_path
```

Grouped explanations:

- `ScamDetectorModel._load()`: lazily loads a pickled model bundle containing `model` and `feature_columns`. If missing, logs and falls back to rule-based logic.
- `predict()`: builds features via `extract_features(job)`; when ML model available it returns `model.predict_proba(X)[0][1]`, else the rule-based `_rule_based_score()`.
- `_rule_based_score()`: uses weighted signals like registration fees, WhatsApp/Telegram links, unrealistic salary, number of scam keywords, upfront payment, and trust signals to compute a 0..1 score clamp.
- `predict_batch()`: vectorised path for many jobs; faster with ML model, otherwise maps the rule-based scorer over inputs.

Notes:
- The model and training pipeline live in `ml/scam_detector/train.py`; this wrapper keeps inference usage simple for services like `verifier`.
- Threshold constants `_SCAM_THRESHOLD` and `_SUSPICIOUS_THRESHOLD` are chosen to produce labels; they can be tuned based on validation ROC/PR curves.
