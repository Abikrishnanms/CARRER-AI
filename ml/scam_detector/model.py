"""
ml/scam_detector/model.py — Inference-only wrapper for the trained scam detector.

Provides a clean, import-friendly API over the pickled XGBoost model trained
by train.py, without requiring xgboost at import time (lazy import on first use).

Usage:
    from ml.scam_detector.model import ScamDetectorModel
    model = ScamDetectorModel()          # loads model from default path
    prob = model.predict(job_dict)       # float 0-1
    label = model.classify(job_dict)     # "scam" | "suspicious" | "legitimate"
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

    # ── Loading ────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        path = Path(self._model_path)
        if not path.exists():
            logger.info(
                "ScamDetectorModel: no trained model at %s — using rule-based fallback",
                self._model_path,
            )
            return
        try:
            with open(path, "rb") as f:
                bundle = pickle.load(f)
            self._model = bundle["model"]
            self._feature_cols = bundle.get("feature_columns", FEATURE_COLUMNS)
            self._loaded = True
            logger.info(
                "ScamDetectorModel loaded (AUC=%.4f, features=%d)",
                bundle.get("auc", 0.0),
                len(self._feature_cols),
            )
        except Exception as e:
            logger.warning("ScamDetectorModel: failed to load model — %s", e)

    # ── Prediction ─────────────────────────────────────────────────────────────

    def predict(self, job: dict[str, Any]) -> float:
        """
        Return scam probability (0.0 → legitimate, 1.0 → scam).
        Uses ML model when available, otherwise rule-based fallback.
        """
        features = extract_features(job)

        if self._loaded and self._model is not None:
            try:
                import numpy as np
                X = np.array([[features.get(c, 0) for c in self._feature_cols]])
                return float(self._model.predict_proba(X)[0][1])
            except Exception as e:
                logger.warning("ML prediction failed, using rule-based: %s", e)

        return self._rule_based_score(features)

    def classify(self, job: dict[str, Any]) -> str:
        """Return a human-readable label: 'scam' | 'suspicious' | 'legitimate'."""
        prob = self.predict(job)
        if prob >= _SCAM_THRESHOLD:
            return "scam"
        if prob >= _SUSPICIOUS_THRESHOLD:
            return "suspicious"
        return "legitimate"

    def predict_batch(self, jobs: list[dict[str, Any]]) -> list[float]:
        """Vectorised batch prediction (much faster for large datasets)."""
        if not jobs:
            return []

        features_list = [extract_features(j) for j in jobs]

        if self._loaded and self._model is not None:
            try:
                import numpy as np
                X = np.array([
                    [f.get(c, 0) for c in self._feature_cols]
                    for f in features_list
                ])
                return [float(p) for p in self._model.predict_proba(X)[:, 1]]
            except Exception as e:
                logger.warning("Batch ML prediction failed, falling back: %s", e)

        return [self._rule_based_score(f) for f in features_list]

    # ── Rule-based fallback ────────────────────────────────────────────────────

    @staticmethod
    def _rule_based_score(features: dict[str, Any]) -> float:
        """
        Lightweight rule-based scam score when no model is available.
        Uses the same feature dict that extract_features() produces.
        """
        score = 0.0

        # Hard signals (high weight)
        if features.get("has_registration_fee"):
            score += 0.40
        if features.get("has_whatsapp_url") or features.get("has_telegram_url"):
            score += 0.35
        if features.get("has_unrealistic_salary"):
            score += 0.25

        # Medium signals
        score += min(features.get("n_scam_keywords", 0) * 0.08, 0.30)
        if features.get("has_upfront_payment"):
            score += 0.20
        if features.get("has_guaranteed"):
            score += 0.10
        if features.get("suspicious_company_name"):
            score += 0.10
        if features.get("too_many_exclamations"):
            score += 0.05
        if features.get("short_description"):
            score += 0.05

        # Trust signals (reduce score)
        if features.get("is_trusted_source"):
            score -= 0.25
        if features.get("has_trusted_domain"):
            score -= 0.15

        return max(0.0, min(1.0, score))

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def is_ml_loaded(self) -> bool:
        """True if a trained ML model is in use."""
        return self._loaded

    @property
    def model_path(self) -> str:
        return self._model_path
