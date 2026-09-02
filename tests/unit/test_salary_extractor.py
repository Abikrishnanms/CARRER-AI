"""
Unit tests for the Salary Extractor / Estimator stack:
  - services.enrichment.agents.salary_extractor (SalaryExtractionAgent)
  - ml.salary_estimator.estimator (SalaryEstimator — rule-based engine)
  - ml.salary_estimator.model (SalaryModel — inference wrapper)
"""

from __future__ import annotations

import pytest


# ─── SalaryExtractionAgent (regex / rule-based) ───────────────────────────────

class TestSalaryExtractionAgent:
    """Test the salary extraction agent used in the enrichment pipeline."""

    def setup_method(self):
        from services.enrichment.agents.salary_extractor import SalaryExtractionAgent
        self.agent = SalaryExtractionAgent(use_llm=False)

    # extract_from_raw tests

    def test_lpa_range(self):
        r = self.agent.extract_from_raw("5-10 LPA")
        assert r is not None
        assert r.min_value == pytest.approx(500_000)
        assert r.max_value == pytest.approx(1_000_000)
        assert r.currency == "INR"
        assert r.period == "yearly"

    def test_rupee_lakh_format(self):
        r = self.agent.extract_from_raw("₹5L-10L PA")
        assert r is not None
        assert r.min_value == pytest.approx(500_000)
        assert r.max_value == pytest.approx(1_000_000)

    def test_usd_k_format(self):
        r = self.agent.extract_from_raw("$50k-$80k")
        assert r is not None
        assert r.currency == "USD"
        assert r.min_value == pytest.approx(50_000)
        assert r.max_value == pytest.approx(80_000)

    def test_none_salary_returns_none(self):
        assert self.agent.extract_from_raw(None) is None

    def test_vague_string_returns_none(self):
        assert self.agent.extract_from_raw("As per industry standards") is None

    def test_monthly_salary(self):
        r = self.agent.extract_from_raw("₹80,000 per month")
        assert r is not None
        assert r.period == "monthly"
        assert r.min_value > 0

    def test_is_not_estimated_for_explicit(self):
        r = self.agent.extract_from_raw("12-18 LPA")
        assert r is not None
        assert r.is_estimated is False

    def test_confidence_high_for_explicit(self):
        r = self.agent.extract_from_raw("15-25 LPA")
        assert r is not None
        assert r.confidence >= 0.70

    # extract_from_description tests

    def test_salary_in_description(self):
        desc = "The CTC for this role is between 10 to 15 LPA based on experience."
        r = self.agent.extract_from_description(desc)
        assert r is not None
        assert r.min_value > 0

    def test_no_salary_in_description_returns_none(self):
        desc = "We are looking for a passionate developer to join our team."
        r = self.agent.extract_from_description(desc)
        # Should return None — no salary info
        assert r is None

    # experience-level estimation

    @pytest.mark.parametrize("level,expected_min", [
        ("entry", 300_000),
        ("mid", 700_000),
        ("senior", 1_500_000),
        ("lead", 2_500_000),
    ])
    def test_experience_estimation_ranges(self, level, expected_min):
        r = self.agent.estimate_from_experience(level)
        assert r.is_estimated is True
        assert r.min_value >= expected_min
        assert r.confidence <= 0.5

    def test_part_time_halves_estimate(self):
        full = self.agent.estimate_from_experience("mid", job_type="full_time")
        part = self.agent.estimate_from_experience("mid", job_type="part_time")
        assert part.min_value < full.min_value

    # midpoint property

    def test_midpoint_computed(self):
        r = self.agent.extract_from_raw("10-20 LPA")
        assert r is not None
        assert r.midpoint == pytest.approx(1_500_000)


# ─── SalaryEstimator rule-based engine ────────────────────────────────────────

class TestSalaryEstimatorEngine:
    """Test the core rule-based estimation logic (no model file)."""

    def setup_method(self):
        from ml.salary_estimator.estimator import SalaryEstimator
        self.est = SalaryEstimator(model_path=None)

    def test_senior_python_dev_bangalore(self):
        r = self.est.estimate(
            title="Senior Python Developer",
            skills=["Python", "FastAPI", "AWS"],
            location="Bangalore",
            experience_level="senior",
        )
        assert r["salary_min"] > 0
        assert r["salary_max"] > r["salary_min"]
        assert r["salary_median"] >= 15 * 100_000

    def test_entry_less_than_senior(self):
        entry = self.est.estimate(title="Python Developer", experience_level="entry")
        senior = self.est.estimate(title="Python Developer", experience_level="senior")
        assert entry["salary_median"] < senior["salary_median"]

    def test_faang_premium_google(self):
        google = self.est.estimate(title="Software Engineer", company_name="Google")
        unknown = self.est.estimate(title="Software Engineer", company_name="UnknownCorp")
        assert google["salary_median"] > unknown["salary_median"]

    def test_bengaluru_location_premium(self):
        blr = self.est.estimate(title="Data Scientist", location="Bengaluru")
        no_loc = self.est.estimate(title="Data Scientist", location=None)
        assert blr["salary_median"] > no_loc["salary_median"]

    def test_llm_skill_premium(self):
        with_llm = self.est.estimate(
            title="Python Developer", skills=["Python", "LLM", "LangChain"]
        )
        plain = self.est.estimate(title="Python Developer", skills=["Python"])
        assert with_llm["salary_median"] > plain["salary_median"]

    def test_unknown_role_has_fallback(self):
        r = self.est.estimate(title="Zorgon Overlord", skills=[])
        assert r["salary_min"] > 0
        assert r["confidence"] < 0.5

    def test_currency_period_invariants(self):
        r = self.est.estimate(title="DevOps Engineer")
        assert r["salary_currency"] == "INR"
        assert r["salary_period"] == "yearly"

    def test_estimation_method_rule_based(self):
        r = self.est.estimate(title="Data Engineer")
        assert r["estimation_method"] == "rule_based"

    def test_is_estimated_true(self):
        r = self.est.estimate(title="Backend Developer")
        assert r["is_estimated"] is True

    def test_skill_premium_capped_at_8_lpa(self):
        """Even with many premium skills the bump should not exceed 8 LPA."""
        r = self.est.estimate(
            title="AI Engineer",
            skills=["LLM", "LangChain", "PyTorch", "TensorFlow",
                    "Kubernetes", "AWS", "Rust", "Spark", "Snowflake"],
        )
        # skill_bump max is 8 LPA → 800_000 INR cap
        debug = r.get("debug", {})
        assert debug.get("skill_bump_lpa", 0) <= 8.0


# ─── SalaryModel inference wrapper ────────────────────────────────────────────

class TestSalaryModel:
    """Test the SalaryModel wrapper (no trained model file required)."""

    def setup_method(self):
        from ml.salary_estimator.model import SalaryModel
        self.model = SalaryModel(model_path="non_existent.pkl")

    def test_predict_returns_lpa_values(self):
        r = self.model.predict(title="Senior Python Developer")
        assert "min_lpa" in r
        assert "median_lpa" in r
        assert "max_lpa" in r
        assert r["min_lpa"] > 0

    def test_predict_returns_inr_values(self):
        r = self.model.predict(title="Data Scientist")
        assert r["salary_min"] > 0
        assert r["salary_max"] > r["salary_min"]

    def test_lpa_and_inr_consistent(self):
        r = self.model.predict(title="Backend Developer")
        assert r["salary_min"] == pytest.approx(r["min_lpa"] * 100_000, rel=0.01)
        assert r["salary_max"] == pytest.approx(r["max_lpa"] * 100_000, rel=0.01)

    def test_format_range_lpa(self):
        r = self.model.predict(title="DevOps Engineer")
        s = self.model.format_range(r, currency="LPA")
        assert "LPA" in s
        assert "₹" in s

    def test_format_range_inr(self):
        r = self.model.predict(title="DevOps Engineer")
        s = self.model.format_range(r, currency="INR")
        assert "per annum" in s

    def test_batch_predict_length(self):
        jobs = [
            {"title": "Python Developer", "skills": ["Python"]},
            {"title": "Data Scientist", "skills": ["Python", "ML"]},
            {"title": "DevOps Engineer", "skills": ["Kubernetes"]},
        ]
        results = self.model.predict_batch(jobs)
        assert len(results) == 3
        for r in results:
            assert r["salary_min"] > 0

    def test_is_ml_loaded_false_without_model(self):
        assert self.model.is_ml_loaded is False

    def test_confidence_between_0_and_1(self):
        r = self.model.predict(title="Software Engineer")
        assert 0.0 <= r["confidence"] <= 1.0
