"""
ML Scam Detector — Rule-based + XGBoost ensemble model.
Trains on labeled job data and exports a model for use in the verifier service.

Usage:
  python ml/scam_detector/train.py --data data/labeled_jobs.csv --output ml/scam_detector/model.pkl
"""

from __future__ import annotations

import re
import pickle
import argparse
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Feature Extraction ───────────────────────────────────────────────────────

SCAM_KEYWORDS = [
    "earn from home", "work from home earn", "daily payment", "weekly payout",
    "no experience required", "earn 1 lakh", "guaranteed income",
    "registration fee", "pay to work", "whatsapp", "telegram join",
    "mlm", "network marketing", "referral chain", "unlimited income",
    "part time earn", "data entry earn", "simple typing job",
    "100% genuine", "no investment", "free laptop", "money back guarantee",
]

TRUSTED_SOURCES = {"greenhouse", "lever", "workday", "linkedin", "naukri_api", "indeed_direct"}
TRUSTED_DOMAINS = {"google.com", "microsoft.com", "amazon.com", "flipkart.com", "accenture.com"}
SUSPICIOUS_DOMAINS = {"whatsapp.com", "t.me", "telegram.me", "bit.ly", "tinyurl.com"}


def extract_features(job: dict[str, Any]) -> dict[str, float]:
    """Extract numerical features from a raw job dict."""
    desc = (job.get("description") or "").lower()
    title = (job.get("title") or "").lower()
    company = (job.get("company_name") or "").lower()
    apply_url = (job.get("apply_url") or "").lower()
    source = (job.get("source") or "").lower()
    salary_raw = (job.get("salary_raw") or "").lower()
    skills = job.get("required_skills") or []

    # Keyword density
    n_scam_keywords = sum(1 for kw in SCAM_KEYWORDS if kw in desc)
    desc_words = len(desc.split()) or 1

    # URL signals
    has_whatsapp_url = int("whatsapp" in apply_url or "wa.me" in apply_url)
    has_telegram_url = int("t.me" in apply_url or "telegram" in apply_url)
    has_suspicious_domain = int(any(d in apply_url for d in SUSPICIOUS_DOMAINS))
    has_trusted_domain = int(any(d in apply_url for d in TRUSTED_DOMAINS))

    # Source trust
    is_trusted_source = int(source in TRUSTED_SOURCES)

    # Salary signals
    has_unrealistic_salary = int(bool(re.search(r"[1-9][0-9]\s*lakh\s*per\s*month", salary_raw)))
    has_daily_weekly_payment = int(bool(re.search(r"\b(daily|weekly)\s*(payment|salary|earn)", salary_raw + desc)))

    # Content signals
    has_guaranteed = int("guaranteed" in desc)
    has_registration_fee = int(bool(re.search(r"(registration|joining|processing)\s*fee", desc)))
    has_upfront_payment = int(bool(re.search(r"(pay|payment|deposit).{0,30}(start|join|work)", desc)))
    short_description = int(desc_words < 100)
    too_many_exclamations = int(desc.count("!") > 5)
    has_phone_number = int(bool(re.search(r"(\+91|0[6-9][0-9]{8})", desc + title)))

    # Company signals
    company_name_length = len(company.split())
    has_pvt_ltd = int("pvt" in company or "private limited" in company)
    suspicious_company_name = int(company_name_length <= 1 or len(company) < 4)

    # Skills
    num_skills = len(skills)

    return {
        "n_scam_keywords": n_scam_keywords,
        "scam_keyword_density": n_scam_keywords / desc_words,
        "has_whatsapp_url": has_whatsapp_url,
        "has_telegram_url": has_telegram_url,
        "has_suspicious_domain": has_suspicious_domain,
        "has_trusted_domain": has_trusted_domain,
        "is_trusted_source": is_trusted_source,
        "has_unrealistic_salary": has_unrealistic_salary,
        "has_daily_weekly_payment": has_daily_weekly_payment,
        "has_guaranteed": has_guaranteed,
        "has_registration_fee": has_registration_fee,
        "has_upfront_payment": has_upfront_payment,
        "short_description": short_description,
        "too_many_exclamations": too_many_exclamations,
        "has_phone_number": has_phone_number,
        "company_name_length": company_name_length,
        "has_pvt_ltd": has_pvt_ltd,
        "suspicious_company_name": suspicious_company_name,
        "num_skills": num_skills,
        "description_length": desc_words,
    }


FEATURE_COLUMNS = list(extract_features({}).keys())


def train(data_path: str, output_path: str) -> None:
    """Train the XGBoost scam detector model."""
    try:
        from xgboost import XGBClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.metrics import classification_report, roc_auc_score
    except ImportError:
        raise SystemExit("Install: pip install xgboost scikit-learn pandas")

    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

    if "is_scam" not in df.columns:
        raise ValueError("CSV must have 'is_scam' column (0=legitimate, 1=scam)")

    # Extract features
    features = df.apply(lambda row: extract_features(row.to_dict()), axis=1)
    X = pd.DataFrame(list(features))[FEATURE_COLUMNS]
    y = df["is_scam"].astype(int)

    logger.info(f"Dataset: {len(df)} samples, {y.sum()} scam ({y.mean()*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    model = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        scale_pos_weight=(y == 0).sum() / (y == 1).sum(),  # class imbalance
        subsample=0.8, colsample_bytree=0.8,
        use_label_encoder=False, eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    logger.info(f"\n{classification_report(y_test, y_pred)}")
    logger.info(f"AUC-ROC: {auc:.4f}")

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "auc": auc}, f)
    logger.info(f"Model saved to {output_path}")


def predict(model_path: str, job: dict) -> float:
    """Load model and predict scam probability for a single job."""
    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]
    cols = bundle["feature_columns"]
    features = extract_features(job)
    X = np.array([[features.get(c, 0) for c in cols]])
    return float(model.predict_proba(X)[0][1])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Train TalentLens Scam Detector")
    parser.add_argument("--data", required=True, help="Path to labeled CSV file")
    parser.add_argument("--output", default="ml/scam_detector/model.pkl")
    args = parser.parse_args()
    train(args.data, args.output)
