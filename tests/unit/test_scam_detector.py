"""
Unit tests for the Scam Detector — rule-based feature extraction,
ScamDetectionAgent (verifier service), and ScamDetectorModel (ML wrapper).
"""

from __future__ import annotations

import pytest


# ─── Feature Extraction ───────────────────────────────────────────────────────

class TestFeatureExtraction:
    """Test ml.scam_detector.train.extract_features()."""

    def test_scam_keywords_counted(self):
        from ml.scam_detector.train import extract_features
        job = {
            "description": "earn from home guaranteed income no experience required",
            "title": "", "company_name": "", "apply_url": "",
            "source": "", "salary_raw": "", "required_skills": [],
        }
        feats = extract_features(job)
        assert feats["n_scam_keywords"] >= 2

    def test_whatsapp_url_detected(self):
        from ml.scam_detector.train import extract_features
        job = {
            "description": "Apply now",
            "title": "Job", "company_name": "Co",
            "apply_url": "https://wa.me/919999999999",
            "source": "", "salary_raw": "", "required_skills": [],
        }
        feats = extract_features(job)
        assert feats["has_whatsapp_url"] == 1

    def test_trusted_source_flagged(self):
        from ml.scam_detector.train import extract_features
        job = {
            "description": "Senior developer role",
            "title": "Dev", "company_name": "Google",
            "apply_url": "https://careers.google.com",
            "source": "greenhouse",
            "salary_raw": "20-30 LPA", "required_skills": ["Python"],
        }
        feats = extract_features(job)
        assert feats["is_trusted_source"] == 1

    def test_registration_fee_detected(self):
        from ml.scam_detector.train import extract_features
        job = {
            "description": "Pay a registration fee of Rs 500 to start work",
            "title": "Data Entry", "company_name": "XYZ",
            "apply_url": "http://fake.com",
            "source": "rss", "salary_raw": "", "required_skills": [],
        }
        feats = extract_features(job)
        assert feats["has_registration_fee"] == 1

    def test_clean_job_zero_scam_keywords(self):
        from ml.scam_detector.train import extract_features
        job = {
            "description": "We are looking for a senior Python engineer to join our product team. "
                           "You will design scalable microservices and mentor junior developers.",
            "title": "Senior Python Engineer",
            "company_name": "Accenture",
            "apply_url": "https://careers.accenture.com/jobs/12345",
            "source": "greenhouse",
            "salary_raw": "20-30 LPA",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        }
        feats = extract_features(job)
        assert feats["n_scam_keywords"] == 0
        assert feats["has_registration_fee"] == 0
        assert feats["has_whatsapp_url"] == 0


# ─── ScamDetectionAgent (verifier service) ────────────────────────────────────

class TestScamDetectionAgent:
    """Test the rule-based ScamDetectionAgent used in the verifier pipeline."""

    def _run_scam(self, job: dict):
        """Helper: run the async analyze() method synchronously."""
        import asyncio
        from services.verifier.agents.scam_detector import ScamDetectionAgent
        agent = ScamDetectionAgent()
        return asyncio.run(agent.analyze(
            job_id=job.get("_id", "test-id"),
            title=job.get("title", ""),
            description=job.get("description", ""),
            company_name=job.get("company_name", ""),
            apply_url=job.get("apply_url"),
        ))

    def _scam_job(self):
        return {
            "_id": "scam-001",
            "title": "Data Entry Operator",
            "company_name": "XYZ Corp",
            # Uses phrases that hit SCAM_PATTERNS: whatsapp_only + unrealistic_salary
            "description": (
                "Earn lakhs per day guaranteed income from home. "
                "Contact us on whatsapp wa.me for more details. "
                "No experience required, high salary assured."
            ),
            "apply_url": "https://wa.me/919876543210",
        }

    def _legit_job(self):
        return {
            "_id": "legit-001",
            "title": "Senior Python Engineer",
            "company_name": "Accenture",
            "description": "We are looking for an experienced Python engineer to join our fintech team. "
                           "You will work on high-scale APIs and mentor junior developers.",
            "apply_url": "https://careers.accenture.com/jobs/12345",
        }

    def test_scam_job_high_probability(self):
        result = self._run_scam(self._scam_job())
        assert result.scam_probability > 0.3
        assert len(result.triggered_rules) > 0

    def test_legitimate_job_low_probability(self):
        result = self._run_scam(self._legit_job())
        assert result.scam_probability < 0.6

    def test_triggered_rules_are_strings(self):
        result = self._run_scam(self._scam_job())
        for rule in result.triggered_rules:
            assert isinstance(rule, str)

    def test_probability_between_zero_and_one(self):
        for job in [self._scam_job(), self._legit_job()]:
            result = self._run_scam(job)
            assert 0.0 <= result.scam_probability <= 1.0


# ─── ScamDetectorModel (ML wrapper) ───────────────────────────────────────────

class TestScamDetectorModel:
    """Test ml.scam_detector.model.ScamDetectorModel (no trained model file needed)."""

    def setup_method(self):
        from ml.scam_detector.model import ScamDetectorModel
        # No model file → uses rule-based fallback
        self.model = ScamDetectorModel(model_path="non_existent_path.pkl")

    def test_scam_job_scores_high(self):
        prob = self.model.predict({
            "description": "registration fee guaranteed income earn from home",
            "title": "WFH Job",
            "company_name": "XYZ",
            "apply_url": "https://wa.me/99999",
            "source": "rss",
            "salary_raw": "",
            "required_skills": [],
        })
        assert prob > 0.5

    def test_legit_job_scores_low(self):
        prob = self.model.predict({
            "description": "Senior Python engineer for fintech team. Design scalable APIs.",
            "title": "Senior Python Engineer",
            "company_name": "Accenture",
            "apply_url": "https://careers.accenture.com/1234",
            "source": "greenhouse",
            "salary_raw": "20-30 LPA",
            "required_skills": ["Python"],
        })
        assert prob < 0.5

    def test_classify_returns_valid_label(self):
        for job in [
            {"description": "free laptop earn from home guaranteed income registration fee",
             "title": "Easy job", "company_name": "A", "apply_url": "https://wa.me/1",
             "source": "rss", "salary_raw": "", "required_skills": []},
            {"description": "Senior backend engineer AWS Kubernetes",
             "title": "Backend Engineer", "company_name": "Google",
             "apply_url": "https://google.com/careers",
             "source": "greenhouse", "salary_raw": "30-50 LPA", "required_skills": ["Python"]},
        ]:
            label = self.model.classify(job)
            assert label in ("scam", "suspicious", "legitimate")

    def test_batch_prediction_same_length(self):
        jobs = [
            {"description": "earn from home", "title": "WFH", "company_name": "X",
             "apply_url": "", "source": "", "salary_raw": "", "required_skills": []},
            {"description": "senior engineer role", "title": "Engineer",
             "company_name": "Google", "apply_url": "", "source": "greenhouse",
             "salary_raw": "25 LPA", "required_skills": ["Python"]},
        ]
        probs = self.model.predict_batch(jobs)
        assert len(probs) == 2
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_is_ml_loaded_false_without_model(self):
        assert self.model.is_ml_loaded is False
