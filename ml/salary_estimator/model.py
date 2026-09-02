"""
ml/salary_estimator/model.py — Inference-only wrapper for the trained salary estimator.

Provides a clean API over the pickled GradientBoosting model trained by estimator.py,
with graceful fallback to rule-based estimation when no model file exists.

Usage:
    from ml.salary_estimator.model import SalaryModel
    model = SalaryModel()
    result = model.predict(title="Senior Python Developer", skills=["Python", "AWS"], location="Bangalore")
    # → {"min_lpa": 18.2, "median_lpa": 24.1, "max_lpa": 32.6, "currency": "INR", "confidence": 0.82}
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

from ml.salary_estimator.estimator import (
    SalaryEstimator,
    _detect_experience_level,
    _detect_location_key,
    _detect_company_type,
    _skill_premium,
    ROLE_SALARY_MAP,
    EXPERIENCE_MULTIPLIERS,
    LOCATION_MULTIPLIERS,
    COMPANY_MULTIPLIERS,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.environ.get(
    "SALARY_MODEL_PATH",
    "ml/salary_estimator/model.pkl",
)

_LPA_TO_INR = 100_000  # 1 LPA = ₹1,00,000


class SalaryModel:
    """
    Thin inference wrapper around the trained GradientBoosting salary estimator.

    Delegates to SalaryEstimator (which already handles model loading + rule-based
    fallback). This class adds:
      - LPA-native output (alongside INR)
      - Batch prediction
      - Confidence band annotation
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or _DEFAULT_MODEL_PATH
        self._estimator = SalaryEstimator(model_path=self._model_path)
        logger.info(
            "SalaryModel ready (method=%s)",
            "ml_model" if self._estimator.model else "rule_based",
        )

    # ── Main API ───────────────────────────────────────────────────────────────

    def predict(
        self,
        title: str,
        description: str = "",
        skills: list[str] | None = None,
        company_name: str = "",
        location: str | None = None,
        experience_level: str | None = None,
    ) -> dict[str, Any]:
        """
        Predict salary range for a job.

        Returns a dict with both LPA and INR values:
        {
            min_lpa, median_lpa, max_lpa,
            salary_min, salary_median, salary_max,   # INR yearly
            currency, period, confidence, method,
            is_estimated, debug
        }
        """
        raw = self._estimator.estimate(
            title=title,
            description=description,
            skills=skills or [],
            company_name=company_name,
            location=location,
            experience_level=experience_level,
        )

        return {
            # LPA convenience values
            "min_lpa": round(raw["salary_min"] / _LPA_TO_INR, 2),
            "median_lpa": round(raw["salary_median"] / _LPA_TO_INR, 2),
            "max_lpa": round(raw["salary_max"] / _LPA_TO_INR, 2),
            # INR values (full)
            "salary_min": raw["salary_min"],
            "salary_median": raw["salary_median"],
            "salary_max": raw["salary_max"],
            "currency": raw["salary_currency"],
            "period": raw["salary_period"],
            "confidence": raw["confidence"],
            "method": raw["estimation_method"],
            "is_estimated": raw["is_estimated"],
            "debug": raw.get("debug", {}),
        }

    def predict_batch(
        self, jobs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Predict salary for a list of job dicts (each with title, skills, etc.)."""
        return [
            self.predict(
                title=j.get("title", ""),
                description=j.get("description", ""),
                skills=j.get("skills") or j.get("required_skills") or [],
                company_name=j.get("company_name", ""),
                location=j.get("location_raw") or j.get("location"),
                experience_level=j.get("experience_level"),
            )
            for j in jobs
        ]

    # ── Helpers ────────────────────────────────────────────────────────────────

    def format_range(self, result: dict[str, Any], currency: str = "INR") -> str:
        """Return a human-readable salary range string."""
        if currency == "LPA":
            return f"₹{result['min_lpa']}–{result['max_lpa']} LPA"
        min_inr = result["salary_min"]
        max_inr = result["salary_max"]
        if result["period"] == "yearly":
            return f"₹{min_inr / _LPA_TO_INR:.1f}L–₹{max_inr / _LPA_TO_INR:.1f}L per annum"
        return f"₹{min_inr:,.0f}–₹{max_inr:,.0f} per {result['period']}"

    @property
    def is_ml_loaded(self) -> bool:
        return self._estimator.model is not None

    @property
    def model_path(self) -> str:
        return self._model_path
