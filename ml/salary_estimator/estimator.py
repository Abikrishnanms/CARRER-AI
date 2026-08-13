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
    # Software Engineering
    "software engineer":       (6.0,  12.0,  22.0),
    "backend developer":       (6.0,  14.0,  25.0),
    "frontend developer":      (5.0,  12.0,  20.0),
    "full stack developer":    (7.0,  14.0,  26.0),
    "python developer":        (7.0,  15.0,  28.0),
    "java developer":          (6.0,  13.0,  24.0),
    "mobile developer":        (6.0,  14.0,  26.0),
    "ios developer":           (7.0,  15.0,  28.0),
    "android developer":       (6.0,  14.0,  26.0),

    # Data & AI
    "data scientist":          (10.0, 18.0,  35.0),
    "data analyst":            (5.0,  10.0,  18.0),
    "data engineer":           (9.0,  17.0,  32.0),
    "machine learning engineer": (12.0, 22.0, 45.0),
    "ml engineer":             (12.0, 22.0,  45.0),
    "ai engineer":             (14.0, 25.0,  50.0),
    "nlp engineer":            (12.0, 22.0,  42.0),
    "deep learning engineer":  (14.0, 26.0,  50.0),

    # Platform / Infrastructure
    "devops engineer":         (9.0,  17.0,  32.0),
    "cloud engineer":          (9.0,  18.0,  35.0),
    "site reliability engineer": (12.0, 22.0, 40.0),
    "sre":                     (12.0, 22.0,  40.0),
    "platform engineer":       (12.0, 22.0,  40.0),
    "cloud architect":         (18.0, 32.0,  60.0),
    "solutions architect":     (18.0, 30.0,  55.0),

    # Management & Leadership
    "tech lead":               (18.0, 28.0,  50.0),
    "engineering manager":     (22.0, 35.0,  65.0),
    "product manager":         (14.0, 22.0,  40.0),
    "project manager":         (8.0,  14.0,  25.0),
    "cto":                     (30.0, 50.0,  100.0),

    # QA & Security
    "qa engineer":             (4.0,  8.0,   16.0),
    "test engineer":           (4.0,  8.0,   16.0),
    "security engineer":       (10.0, 18.0,  35.0),
    "cybersecurity":           (10.0, 18.0,  35.0),

    # Generalist fallback
    "software developer":      (5.0,  12.0,  22.0),
    "developer":               (4.0,  10.0,  20.0),
    "engineer":                (5.0,  10.0,  20.0),
}

# Experience level multipliers
EXPERIENCE_MULTIPLIERS: dict[str, float] = {
    "entry":     0.70,   # 0-2 years
    "mid":       1.00,   # 2-5 years (baseline)
    "senior":    1.55,   # 5-10 years
    "lead":      2.10,   # 8-12 years
    "executive": 3.00,   # 12+ years
    "unknown":   1.00,
}

# Location multipliers (metro premium)
LOCATION_MULTIPLIERS: dict[str, float] = {
    "bengaluru":      1.20,
    "bangalore":      1.20,
    "mumbai":         1.15,
    "delhi":          1.10,
    "ncr":            1.10,
    "gurugram":       1.12,
    "gurgaon":        1.12,
    "noida":          1.08,
    "hyderabad":      1.10,
    "pune":           1.05,
    "chennai":        1.05,
    "kolkata":        0.90,
    "remote":         1.05,  # Small remote premium
}

# High-value tech skills premium (additive LPA bump)
SKILL_PREMIUMS: dict[str, float] = {
    # AI / ML
    "machine learning": 2.5,
    "deep learning":    3.0,
    "pytorch":          3.0,
    "tensorflow":       2.5,
    "llm":              4.0,
    "langchain":        3.5,
    "rag":              3.5,
    "generative ai":    4.0,
    "transformers":     3.0,
    "llama":            3.5,

    # Cloud & Infra
    "aws":              2.0,
    "gcp":              2.0,
    "azure":            2.0,
    "kubernetes":       2.5,
    "terraform":        2.0,

    # Backend
    "rust":             3.5,
    "golang":           2.5,
    "kafka":            2.0,
    "graphql":          1.5,
    "grpc":             1.5,

    # Data
    "spark":            2.5,
    "airflow":          2.0,
    "dbt":              2.0,
    "snowflake":        2.5,

    # Security
    "penetration testing": 3.0,
    "security":         1.5,
}

# Company type multipliers
COMPANY_MULTIPLIERS: dict[str, float] = {
    "faang":     2.50,  # Google, Meta, Amazon, Apple, Netflix
    "mnc":       1.40,  # IBM, Accenture, TCS, Infosys large clients
    "startup":   1.10,  # Well-funded startups
    "product":   1.30,  # Product companies
    "service":   0.85,  # IT services / outsourcing
    "unknown":   1.00,
}

FAANG_COMPANIES = {"google", "meta", "amazon", "microsoft", "apple", "netflix",
                   "uber", "airbnb", "stripe", "databricks", "snowflake", "openai"}
SERVICES_COMPANIES = {"tcs", "infosys", "wipro", "hcl", "tech mahindra",
                      "cognizant", "capgemini", "accenture", "ibm"}


# ─── Feature Extraction ───────────────────────────────────────────────────────

def _detect_experience_level(text: str) -> str:
    """Detect experience level from text."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["0-2", "0-1", "fresher", "entry level", "junior", "graduate"]):
        return "entry"
    if any(k in text_lower for k in ["10+", "12+", "15+", "principal", "staff", "vp ", "vice president", "director"]):
        return "executive"
    if any(k in text_lower for k in ["8-", "9-", "10-", "lead", "tech lead", "architect"]):
        return "lead"
    if any(k in text_lower for k in ["5-", "6-", "7-", "senior", "sr.", "sr "]):
        return "senior"
    if any(k in text_lower for k in ["2-", "3-", "4-", "mid", "mid-level", "intermediate"]):
        return "mid"
    # Try to find years of experience numbers
    years_match = re.search(r"(\d+)[\s\-–]+(\d+)\s*(?:years?|yrs?)", text_lower)
    if years_match:
        min_years = int(years_match.group(1))
        if min_years >= 8:
            return "lead"
        elif min_years >= 5:
            return "senior"
        elif min_years >= 2:
            return "mid"
        else:
            return "entry"
    return "unknown"


def _detect_company_type(company_name: str) -> str:
    """Detect company type (FAANG, MNC, services, product, startup)."""
    name_lower = company_name.lower()
    if any(f in name_lower for f in FAANG_COMPANIES):
        return "faang"
    if any(s in name_lower for s in SERVICES_COMPANIES):
        return "service"
    return "unknown"


def _detect_location_key(location: str | None) -> str | None:
    """Extract a normalized location key."""
    if not location:
        return None
    loc_lower = location.lower()
    for key in LOCATION_MULTIPLIERS:
        if key in loc_lower:
            return key
    if "remote" in loc_lower:
        return "remote"
    return None


def _match_role(title: str) -> tuple[float, float, float] | None:
    """Match title to a role salary range."""
    title_lower = title.lower()
    # Try longest match first
    for role in sorted(ROLE_SALARY_MAP.keys(), key=len, reverse=True):
        if role in title_lower:
            return ROLE_SALARY_MAP[role]
    return None


def _skill_premium(skills: list[str]) -> float:
    """Calculate cumulative skill premium (capped at 8 LPA)."""
    total = 0.0
    for skill in skills:
        skill_lower = skill.lower()
        for kw, premium in SKILL_PREMIUMS.items():
            if kw in skill_lower:
                total += premium
                break  # One premium per skill
    return min(total, 8.0)


# ─── Main Estimator ───────────────────────────────────────────────────────────

class SalaryEstimator:
    """
    Rule-based salary estimator for the Indian job market.
    Estimates salary range in INR (Lakhs Per Annum).

    Falls back to a trained scikit-learn model if available at model_path.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model = None
        self.feature_cols: list[str] = []

        if model_path and Path(model_path).exists():
            try:
                import pickle
                with open(model_path, "rb") as f:
                    bundle = pickle.load(f)
                self.model = bundle["model"]
                self.feature_cols = bundle["feature_columns"]
                logger.info(f"Loaded salary model from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load salary model: {e} — using rule-based estimator")

    def estimate(
        self,
        title: str,
        description: str = "",
        skills: list[str] | None = None,
        company_name: str = "",
        location: str | None = None,
        experience_level: str | None = None,
    ) -> dict[str, Any]:
        """
        Estimate salary range for a job.

        Returns:
            {
                salary_min: float (INR yearly),
                salary_max: float (INR yearly),
                salary_currency: "INR",
                salary_period: "yearly",
                salary_median: float,
                is_estimated: True,
                confidence: float (0-1),
                estimation_method: str,
            }
        """
        skills = skills or []
        full_text = f"{title} {description}"

        # Step 1: Match role
        role_range = _match_role(title)
        if role_range is None:
            # Generic tech role fallback
            role_range = (4.0, 10.0, 20.0)
            confidence = 0.35
        else:
            confidence = 0.70

        base_min, base_median, base_max = role_range

        # Step 2: Experience level multiplier
        exp_level = experience_level or _detect_experience_level(full_text)
        exp_mult = EXPERIENCE_MULTIPLIERS.get(exp_level, 1.0)

        # Step 3: Location multiplier
        loc_key = _detect_location_key(location)
        loc_mult = LOCATION_MULTIPLIERS.get(loc_key, 1.0) if loc_key else 1.0

        # Step 4: Skills premium (in LPA)
        skill_bump = _skill_premium(skills)
        if skill_bump > 0:
            confidence = min(confidence + 0.10, 0.90)

        # Step 5: Company type multiplier
        company_type = _detect_company_type(company_name)
        company_mult = COMPANY_MULTIPLIERS.get(company_type, 1.0)

        # Compose final estimate
        salary_min_lpa = (base_min * exp_mult * loc_mult * company_mult) + (skill_bump * 0.5)
        salary_max_lpa = (base_max * exp_mult * loc_mult * company_mult) + skill_bump
        salary_median_lpa = (base_median * exp_mult * loc_mult * company_mult) + (skill_bump * 0.7)

        # Convert LPA → INR yearly (1 LPA = 100,000 INR)
        lpa_to_inr = 100_000

        result = {
            "salary_min": round(salary_min_lpa * lpa_to_inr),
            "salary_max": round(salary_max_lpa * lpa_to_inr),
            "salary_median": round(salary_median_lpa * lpa_to_inr),
            "salary_currency": "INR",
            "salary_period": "yearly",
            "is_estimated": True,
            "confidence": round(confidence, 2),
            "estimation_method": "rule_based",
            "debug": {
                "exp_level": exp_level,
                "location_key": loc_key,
                "company_type": company_type,
                "skill_bump_lpa": round(skill_bump, 1),
                "salary_min_lpa": round(salary_min_lpa, 1),
                "salary_max_lpa": round(salary_max_lpa, 1),
            },
        }

        # Override with ML model if available
        if self.model:
            try:
                import numpy as np
                features = self._extract_ml_features(title, description, skills, exp_level, loc_key)
                X = np.array([[features.get(c, 0) for c in self.feature_cols]])
                pred_lpa = float(self.model.predict(X)[0])
                result["salary_median"] = round(pred_lpa * lpa_to_inr)
                result["salary_min"] = round(pred_lpa * 0.75 * lpa_to_inr)
                result["salary_max"] = round(pred_lpa * 1.35 * lpa_to_inr)
                result["estimation_method"] = "ml_model"
                result["confidence"] = min(result["confidence"] + 0.15, 0.95)
            except Exception as e:
                logger.warning(f"ML prediction failed, using rule-based: {e}")

        return result

    def _extract_ml_features(
        self,
        title: str,
        description: str,
        skills: list[str],
        exp_level: str,
        loc_key: str | None,
    ) -> dict[str, float]:
        """Extract numerical features for the ML model."""
        text = f"{title} {description}".lower()
        return {
            "is_senior": float(exp_level == "senior"),
            "is_lead": float(exp_level == "lead"),
            "is_executive": float(exp_level == "executive"),
            "is_entry": float(exp_level == "entry"),
            "is_bengaluru": float(loc_key in ("bengaluru", "bangalore")),
            "is_mumbai": float(loc_key == "mumbai"),
            "is_remote": float(loc_key == "remote"),
            "has_ml": float(any("machine learning" in s.lower() or "ml" in s.lower() for s in skills)),
            "has_cloud": float(any(c in text for c in ["aws", "gcp", "azure"])),
            "has_kubernetes": float("kubernetes" in text),
            "has_rust_go": float(any(lang in text for lang in ["rust", "golang", "go "])),
            "has_ai_llm": float(any(k in text for k in ["llm", "generative ai", "langchain"])),
            "num_skills": float(len(skills)),
            "skill_premium": _skill_premium(skills),
            "title_is_data": float(any(d in title.lower() for d in ["data", "ml", "ai", "machine learning"])),
            "title_is_devops": float(any(d in title.lower() for d in ["devops", "sre", "platform", "cloud"])),
            "title_is_backend": float("backend" in title.lower() or "python" in title.lower()),
            "title_is_fullstack": float("full" in title.lower() and "stack" in title.lower()),
        }


def train(data_path: str, output_path: str = "ml/salary_estimator/model.pkl") -> None:
    """Train a gradient boosting salary estimator from labeled CSV data."""
    try:
        import pickle
        import pandas as pd
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.metrics import mean_absolute_error, r2_score
    except ImportError:
        raise SystemExit("Install: pip install scikit-learn pandas")

    df = pd.read_csv(data_path)
    required = ["title", "salary_lpa"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"CSV must have column: {col}")

    estimator = SalaryEstimator()

    def row_to_features(row: Any) -> dict[str, float]:
        skills = str(row.get("skills", "")).split(",") if row.get("skills") else []
        return estimator._extract_ml_features(
            title=str(row.get("title", "")),
            description=str(row.get("description", "")),
            skills=skills,
            exp_level=str(row.get("experience_level", "unknown")),
            loc_key=_detect_location_key(str(row.get("location", ""))),
        )

    features = df.apply(row_to_features, axis=1)
    X = pd.DataFrame(list(features))
    y = df["salary_lpa"].astype(float)

    logger.info(f"Dataset: {len(df)} samples, salary range {y.min():.1f}–{y.max():.1f} LPA")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=5, random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    logger.info(f"MAE: {mae:.2f} LPA | R²: {r2:.4f}")

    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    logger.info(f"CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump({
            "model": model,
            "feature_columns": list(X.columns),
            "mae_lpa": mae,
            "r2": r2,
        }, f)
    logger.info(f"Model saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="TalentLens Salary Estimator")
    parser.add_argument("--title", help="Job title to estimate salary for")
    parser.add_argument("--skills", help="Comma-separated skills list")
    parser.add_argument("--location", help="Job location")
    parser.add_argument("--company", default="", help="Company name")
    parser.add_argument("--experience-level", default="mid",
                        choices=["entry", "mid", "senior", "lead", "executive", "unknown"])
    parser.add_argument("--train", action="store_true", help="Train mode")
    parser.add_argument("--data", help="Path to labeled CSV (required for --train)")
    parser.add_argument("--model", default="ml/salary_estimator/model.pkl",
                        help="Model path (load or save)")
    args = parser.parse_args()

    if args.train:
        if not args.data:
            parser.error("--data is required when --train is specified")
        train(args.data, args.model)
    else:
        if not args.title:
            parser.error("--title is required")
        model_path = args.model if os.path.exists(args.model) else None
        est = SalaryEstimator(model_path=model_path)
        skills = [s.strip() for s in args.skills.split(",")] if args.skills else []
        result = est.estimate(
            title=args.title,
            skills=skills,
            company_name=args.company,
            location=args.location,
            experience_level=args.experience_level,
        )
        print(json.dumps(result, indent=2))
