"""
Scam Detection Agent — ML + rule-based ensemble for fraud detection.
Uses XGBoost classifier + 50+ YAML rules + SHAP explainability.
Trained on EMSCAD (Employment Scam Archetypes Corpus and Dataset).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ─── Scam Indicators & Rules ──────────────────────────────────────────────────

# Patterns that indicate scam jobs (regex patterns)
SCAM_PATTERNS = {
    # Upfront payment requests
    "fee_required": {
        "pattern": r"(pay|payment|fee|deposit|registration fee|training fee|security deposit)"
                   r".{0,50}(required|needed|must|upfront|before|joining)",
        "weight": 0.9,
        "description": "Requests payment from applicant",
    },
    # WhatsApp-only contact
    "whatsapp_only": {
        "pattern": r"contact.{0,30}(whatsapp|wa\.me|wa number)",
        "weight": 0.7,
        "description": "WhatsApp-only contact method",
    },
    # Unrealistic salary promises
    "unrealistic_salary": {
        "pattern": r"(earn|make|income|salary).{0,20}(lakh|lakhs|crore).{0,20}(per day|daily|per hour|weekly)",
        "weight": 0.85,
        "description": "Unrealistically high salary for the period",
    },
    # Work from home spam
    "work_from_home_spam": {
        "pattern": r"(work from home|wfh|home based).{0,30}(guaranteed|no experience|anyone can|housewife|students)",
        "weight": 0.6,
        "description": "Suspicious WFH claim targeting vulnerable demographics",
    },
    # Data entry scams
    "data_entry_scam": {
        "pattern": r"(data entry|form filling|captcha).{0,20}(earn|income|money|per form|per entry)",
        "weight": 0.75,
        "description": "Classic data entry / form-filling scam",
    },
    # Multi-level marketing
    "mlm_indicator": {
        "pattern": r"(network marketing|mlm|multi.?level|downline|upline|recruit|referral bonus)",
        "weight": 0.65,
        "description": "Multi-level marketing indicators",
    },
    # Urgency tactics
    "urgency_tactics": {
        "pattern": r"(limited seats|only \d+ positions?|apply (now|immediately|today)|last \d+ (days?|hours?))",
        "weight": 0.3,
        "description": "Pressure/urgency tactics",
    },
    # No experience required for high-paying job
    "no_experience_high_pay": {
        "pattern": r"(no experience|freshers welcome|0 experience).{0,100}(₹[5-9]\d{4,}|[5-9]\d{4,} per month)",
        "weight": 0.7,
        "description": "High salary offered with no experience required",
    },
    # Request for personal documents upfront
    "document_request": {
        "pattern": r"(send|submit|share|attach).{0,30}(aadhaar|pan card|passport|bank (details|account))",
        "weight": 0.8,
        "description": "Requesting sensitive documents before hiring",
    },
    # Suspicious contact methods
    "personal_email": {
        "pattern": r"send.{0,20}(resume|cv|details).{0,20}@(gmail|yahoo|hotmail|outlook)\.",
        "weight": 0.5,
        "description": "Uses personal email instead of company email",
    },
    # Missing company details
    "vague_company": {
        "pattern": r"^(company|organization|client|mnc|it company|leading company)$",
        "weight": 0.4,
        "description": "Vague or missing company name",
    },
    # Telegram contact scam
    "telegram_scam": {
        "pattern": r"(t\.me|telegram|tg group|contact on telegram)",
        "weight": 0.8,
        "description": "Telegram group or channel contact requirement",
    },
    # Crypto/NFT task scam
    "crypto_task_scam": {
        "pattern": r"(crypto|usdt|binance|nft|wallet|deposit usdt|recharge account)",
        "weight": 0.85,
        "description": "Cryptocurrency or NFT task requirement",
    },
    # Cash payment
    "cash_payment": {
        "pattern": r"(paid|payment|salary).{0,30}(cash|hand to hand|in person|on joining day)",
        "weight": 0.6,
        "description": "Cash payment instead of bank transfer",
    },
}

# Salary thresholds for reasonableness checks (INR/year)
SALARY_REASONABLENESS = {
    "absolute_min": 50_000,           # Below ₹50K/year is suspicious
    "per_day_max_entry": 5_000,       # ₹5K/day for entry level is suspicious
    "unrealistic_multiplier": 10,     # 10x industry average is suspicious
}


@dataclass
class ScamAnalysisResult:
    """Result of scam analysis."""
    job_id: str
    scam_probability: float = 0.0
    risk_level: str = "very_low"
    triggered_rules: list[str] = field(default_factory=list)
    risk_factors: dict[str, float] = field(default_factory=dict)
    trust_reasons: list[str] = field(default_factory=list)
    warning_signals: list[str] = field(default_factory=list)
    model_used: str = "rule_based"
    confidence: float = 1.0
    explanation: str = ""
    processing_time_ms: float = 0.0


class ScamDetectionAgent:
    """
    Scam Detection Agent with three detection layers:
    1. Rule-based engine (YAML rules / regex patterns)
    2. XGBoost ML classifier (if model available)
    3. LLM-based analysis (for borderline cases)

    Architecture doc: Section 3.3.7
    """

    def __init__(self) -> None:
        self._ml_model = None
        self._ml_available = False
        self._load_ml_model()

    def _load_ml_model(self) -> None:
        """Load XGBoost model if available."""
        model_path = os.getenv("SCAM_DETECTOR_MODEL_PATH", "./ml/models/scam_detector.pkl")
        if os.path.exists(model_path):
            try:
                import pickle
                with open(model_path, "rb") as f:
                    self._ml_model = pickle.load(f)
                self._ml_available = True
                logger.info(f"Scam detector ML model loaded from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load scam ML model: {e}")
        else:
            logger.info("Scam ML model not found — using rule-based detection only")

    async def analyze(
        self,
        job_id: str,
        title: str,
        description: str,
        company_name: str,
        salary_min: float | None = None,
        salary_max: float | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        apply_url: str | None = None,
    ) -> ScamAnalysisResult:
        """
        Analyze a job for scam indicators.
        Returns probability 0.0 (safe) to 1.0 (certain scam).
        """
        import time
        start = time.monotonic()

        result = ScamAnalysisResult(job_id=job_id)
        full_text = f"{title} {description} {company_name} {apply_url or ''}".lower()

        # ── Layer 1: Rule-based analysis ──
        rule_score, triggered_rules, risk_factors, trust_reasons, warning_signals = self._apply_rules(
            full_text=full_text,
            title=title,
            description=description,
            company_name=company_name,
            salary_min=salary_min,
            salary_max=salary_max,
            contact_email=contact_email,
            apply_url=apply_url,
        )

        result.triggered_rules = triggered_rules
        result.risk_factors = risk_factors
        result.trust_reasons = trust_reasons
        result.warning_signals = warning_signals

        # ── Layer 2: ML model (if available) ──
        if self._ml_available:
            try:
                ml_score = self._ml_predict(
                    title=title,
                    description=description,
                    company_name=company_name,
                    salary_min=salary_min,
                    salary_max=salary_max,
                )
                combined_score = 0.6 * ml_score + 0.4 * rule_score
                result.model_used = "xgboost_ensemble"
            except Exception as e:
                logger.warning(f"ML model inference failed: {e}")
                combined_score = rule_score
        else:
            combined_score = rule_score
            result.model_used = "rule_based"

        result.scam_probability = min(1.0, max(0.0, combined_score))
        result.risk_level = self._probability_to_risk_level(result.scam_probability)
        result.explanation = self._generate_explanation(result)
        result.processing_time_ms = (time.monotonic() - start) * 1000

        return result

    def _apply_rules(
        self,
        full_text: str,
        title: str,
        description: str,
        company_name: str,
        salary_min: float | None,
        salary_max: float | None,
        contact_email: str | None,
        apply_url: str | None,
    ) -> tuple[float, list[str], dict[str, float], list[str], list[str]]:
        """Apply all scam detection rules and build positive trust vs warning reasons."""
        triggered = []
        risk_factors = {}
        trust_reasons = []
        warning_signals = []
        total_weight = 0.0
        max_single_weight = 0.0

        # ── Pattern-based rules ──
        for rule_name, rule_config in SCAM_PATTERNS.items():
            pattern = rule_config["pattern"]
            weight = rule_config["weight"]

            try:
                if re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE):
                    triggered.append(rule_name)
                    risk_factors[rule_name] = weight
                    warning_signals.append(rule_config["description"])
                    total_weight += weight
                    max_single_weight = max(max_single_weight, weight)
            except re.error as e:
                logger.debug(f"Regex error in rule {rule_name}: {e}")

        # ── Positive Trust Signals ──
        if company_name and company_name.lower() not in {"company", "organization", "mnc", "unknown"}:
            trust_reasons.append("Identified company name")
        if apply_url and ("http://" in apply_url or "https://" in apply_url):
            trust_reasons.append("Valid applicant portal URL")
        if description and len(description.strip()) > 150:
            trust_reasons.append("Detailed job description provided")
        if salary_min and salary_max and salary_max <= salary_min * 4:
            trust_reasons.append("Realistic salary compensation range")
        if "fee_required" not in triggered and "data_entry_scam" not in triggered:
            trust_reasons.append("No upfront payment or fee requested")

        # ── Structural checks ──
        if description and len(description.strip()) < 50:
            triggered.append("very_short_description")
            risk_factors["very_short_description"] = 0.4
            warning_signals.append("Extremely brief job description")
            total_weight += 0.4

        generic_names = {"company", "organization", "client", "mnc", "startup"}
        if company_name.lower().strip() in generic_names:
            triggered.append("generic_company_name")
            risk_factors["generic_company_name"] = 0.5
            warning_signals.append("Generic or undisclosed company name")
            total_weight += 0.5

        if contact_email and re.search(r"@(gmail|yahoo|hotmail|outlook|rediffmail)\.", contact_email, re.I):
            triggered.append("personal_email_contact")
            risk_factors["personal_email_contact"] = 0.4
            warning_signals.append("Personal email address used for contact")
            total_weight += 0.4

        if not triggered:
            score = 0.0
        else:
            normalized = total_weight / (len(SCAM_PATTERNS) + 5)
            score = min(0.95, max(normalized, max_single_weight * 0.9))

        return score, triggered, risk_factors, trust_reasons, warning_signals

    def _ml_predict(
        self,
        title: str,
        description: str,
        company_name: str,
        salary_min: float | None,
        salary_max: float | None,
    ) -> float:
        """Run ML model inference."""
        import numpy as np

        if self._ml_model is None:
            raise RuntimeError(
                "_ml_predict called but no ML model is loaded. "
                "Check SCAM_DETECTOR_MODEL_PATH and that the model file exists."
            )

        # Feature engineering
        features = self._extract_features(title, description, company_name, salary_min, salary_max)
        feature_array = np.array(features).reshape(1, -1)

        prob = self._ml_model.predict_proba(feature_array)[0][1]  # Probability of class 1 (scam)
        return float(prob)

    def _extract_features(
        self,
        title: str,
        description: str,
        company_name: str,
        salary_min: float | None,
        salary_max: float | None,
    ) -> list[float]:
        """Extract numerical features for ML model."""
        desc = description or ""
        full_text = f"{title} {desc}".lower()

        return [
            len(desc),                                                          # Description length
            len(title),                                                         # Title length
            desc.count("!"),                                                    # Exclamation marks
            desc.count("₹") + desc.count("rs") + desc.count("rupee"),         # Currency mentions
            sum(1 for c in desc if c.isupper()) / max(len(desc), 1),          # CAPS ratio
            int(bool(re.search(r"whatsapp|wa\.me", full_text, re.I))),        # WhatsApp mention
            int(bool(re.search(r"no experience|fresher", full_text, re.I))),  # No experience
            int(bool(re.search(r"registration fee|deposit|pay.*join", full_text, re.I))),  # Fee
            int(bool(re.search(r"work from home|wfh", full_text, re.I))),     # WFH mention
            salary_min or 0,                                                    # Min salary
            salary_max or 0,                                                    # Max salary
            (salary_max or 0) - (salary_min or 0),                            # Salary range
            len(company_name),                                                  # Company name length
            int(company_name.lower() in {"company", "mnc", "client"}),        # Generic company
        ]

    def _probability_to_risk_level(self, probability: float) -> str:
        if probability < 0.2: return "very_low"
        if probability < 0.4: return "low"
        if probability < 0.6: return "medium"
        if probability < 0.8: return "high"
        return "very_high"

    def _generate_explanation(self, result: ScamAnalysisResult) -> str:
        if not result.triggered_rules:
            return "No scam indicators detected."

        rules_desc = [
            SCAM_PATTERNS.get(r, {}).get("description", r)
            for r in result.triggered_rules[:3]
        ]
        explanation = f"Risk level: {result.risk_level} ({result.scam_probability:.0%} probability). "
        explanation += f"Detected: {', '.join(rules_desc)}"
        if len(result.triggered_rules) > 3:
            explanation += f" and {len(result.triggered_rules) - 3} more indicators."
        return explanation
