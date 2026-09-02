**Salary Estimator — `ml/salary_estimator/estimator.py` (Annotated copy)**

Summary: Rule-based salary estimator for the Indian market with optional ML model fallback. Produces INR yearly min/median/max with confidence and debug metadata.

---

```python
"""
Salary Estimator — Rule-based + Gradient Boosting salary estimation pipeline.
Estimates salary range (INR, yearly) for Indian job market.

Usage:
  python ml/salary_estimator/estimator.py --title "Senior Python Developer" --skills "Python,FastAPI,AWS"
  python ml/salary_estimator/estimator.py --train --data data/labeled_salaries.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Salary Benchmarks (INR, yearly, 2024 Indian market) ─────────────────────

# Role category → (min_lpa, median_lpa, max_lpa) in Lakhs Per Annum
ROLE_SALARY_MAP: dict[str, tuple[float, float, float]] = {
    ...
}

# Experience, location, skill and company multipliers are defined next

# ─── Feature Extraction helpers: `_detect_experience_level`, `_match_role`, `_skill_premium` etc.

# ─── Main Estimator: `SalaryEstimator`
class SalaryEstimator:
    """
    Rule-based salary estimator for the Indian job market.
    Estimates salary range in INR (Lakhs Per Annum).

    Falls back to a trained scikit-learn model if available at model_path.
    """

    def __init__(self, model_path: str | None = None) -> None:
        # Loads pickled ML model bundle if present, otherwise keeps model=None
        ...

    def estimate(self, title: str, description: str = "", skills: list[str] | None = None, company_name: str = "", location: str | None = None, experience_level: str | None = None) -> dict[str, Any]:
        # Compose rule-based estimate:
        # 1) role_range = _match_role(title)
        # 2) exp_mult = EXPERIENCE_MULTIPLIERS[exp_level]
        # 3) loc_mult = LOCATION_MULTIPLIERS[loc_key]
        # 4) skill_bump = _skill_premium(skills)
        # 5) company_mult = COMPANY_MULTIPLIERS[company_type]
        # Combine into salary_min_lpa, salary_max_lpa, salary_median_lpa
        # Convert LPA→INR and pack confidence/debug fields
        # If ML model loaded, attempt prediction override
        ...

    def _extract_ml_features(self, title: str, description: str, skills: list[str], exp_level: str, loc_key: str | None) -> dict[str, float]:
        # Returns numerical features used by the ML model
        ...


def train(data_path: str, output_path: str = "ml/salary_estimator/model.pkl") -> None:
    """Train a gradient boosting salary estimator from labeled CSV data."""
    # Uses pandas + sklearn to train and pickle a model bundle
    ...

if __name__ == "__main__":
    # CLI entry for train or estimate
    ...
```

Grouped explanations:

- The module provides a strong rule-based baseline tuned for the Indian market using `ROLE_SALARY_MAP`, experience/location/company multipliers, and additive skill premiums.
- `SalaryEstimator.estimate()` composes these signals into a salary range (LPA → INR) and returns `confidence` and `debug` details.
- If a pickled ML model exists at `model_path`, the estimator will load it and use it to override the median/min/max when `model.predict` succeeds.
- `train()` builds a GradientBoostingRegressor from labeled CSV (`title`, `salary_lpa`, optional `skills`, `location`, etc.) and saves a model bundle with feature columns.

Notes:
- Tuning knobs: `ROLE_SALARY_MAP`, `EXPERIENCE_MULTIPLIERS`, `LOCATION_MULTIPLIERS`, `SKILL_PREMIUMS`, and `COMPANY_MULTIPLIERS` are the primary levers for domain calibration.
- The estimator intentionally returns both rule-based and ML-derived fields (via `estimation_method` and `debug`) to assist in A/B and regression analysis.
