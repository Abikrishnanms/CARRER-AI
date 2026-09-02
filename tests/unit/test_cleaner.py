"""
Unit tests for the CleanerService — field normalization, HTML stripping, salary parsing,
location extraction, and job-type detection.
"""

from __future__ import annotations

import pytest


# ─── HTML / Text Cleaning ──────────────────────────────────────────────────────

class TestHtmlStripping:
    """Test the strip_html helper."""

    def test_removes_basic_tags(self):
        from services.cleaner.main import strip_html
        assert strip_html("<b>Hello</b> <i>World</i>") == "Hello World"

    def test_removes_html_entities(self):
        from services.cleaner.main import strip_html
        result = strip_html("Salary &amp; Benefits &nbsp;here")
        assert "&amp;" not in result
        assert "Benefits" in result

    def test_collapses_whitespace(self):
        from services.cleaner.main import strip_html
        result = strip_html("<p>  Multiple   spaces  </p>")
        assert "  " not in result.strip()

    def test_none_input(self):
        from services.cleaner.main import strip_html
        assert strip_html(None) == ""

    def test_empty_string(self):
        from services.cleaner.main import strip_html
        assert strip_html("") == ""

    def test_nested_tags(self):
        from services.cleaner.main import strip_html
        raw = "<div><ul><li>Item 1</li><li>Item 2</li></ul></div>"
        result = strip_html(raw)
        assert "<" not in result
        assert "Item 1" in result and "Item 2" in result


# ─── Location Normalization ────────────────────────────────────────────────────

class TestLocationNormalization:
    """Test normalize_location helper."""

    def test_city_state_country(self):
        from services.cleaner.main import normalize_location
        result = normalize_location("Bangalore, Karnataka, India")
        assert result["city"] == "Bangalore"
        assert result["state"] == "Karnataka"
        assert result["country"] == "India"

    def test_city_only(self):
        from services.cleaner.main import normalize_location
        result = normalize_location("Mumbai")
        assert result["city"] == "Mumbai"

    def test_india_inferred_for_known_city(self):
        from services.cleaner.main import normalize_location
        result = normalize_location("Bengaluru")
        # Should detect India automatically from known city list
        assert result["country"] == "India"

    def test_none_location(self):
        from services.cleaner.main import normalize_location
        result = normalize_location(None)
        assert result["city"] is None
        assert result["country"] is None

    def test_raw_preserved(self):
        from services.cleaner.main import normalize_location
        raw = "Pune, Maharashtra"
        result = normalize_location(raw)
        assert result["raw"] == raw


# ─── Salary Parsing ───────────────────────────────────────────────────────────

class TestSalaryParsing:
    """Test parse_salary helper in services.cleaner.main."""

    def test_lpa_range(self):
        from services.cleaner.main import parse_salary
        result = parse_salary("5-10 LPA")
        assert result["min"] is not None
        assert result["max"] is not None
        assert result["currency"] == "INR"
        assert result["period"] == "yearly"

    def test_lakh_shorthand(self):
        from services.cleaner.main import parse_salary
        result = parse_salary("₹5L-10L PA")
        assert result["min"] == pytest.approx(500_000, rel=0.01)
        assert result["max"] == pytest.approx(1_000_000, rel=0.01)

    def test_monthly_salary(self):
        from services.cleaner.main import parse_salary
        result = parse_salary("₹50,000 per month")
        assert result["period"] == "monthly"
        assert result["min"] > 0

    def test_no_salary_returns_empty(self):
        from services.cleaner.main import parse_salary
        result = parse_salary(None)
        assert result["min"] is None
        assert result["max"] is None

    def test_as_per_standards_returns_empty(self):
        from services.cleaner.main import parse_salary
        result = parse_salary("As per industry standards")
        assert result["min"] is None

    def test_is_estimated_false_for_explicit(self):
        from services.cleaner.main import parse_salary
        result = parse_salary("12-18 LPA")
        # Explicit salary should not be marked estimated
        assert result.get("is_estimated") is False


# ─── Job Type Detection ───────────────────────────────────────────────────────

class TestJobTypeDetection:
    """Test detect_job_type if it exists in cleaner."""

    @pytest.mark.parametrize("text,expected", [
        ("Full time position", "full_time"),
        ("part-time opportunity", "part_time"),
        ("6-month contract role", "contract"),
        ("Summer internship 2024", "internship"),
        ("Freelance project", "freelance"),
    ])
    def test_job_type_detection(self, text, expected):
        try:
            from services.cleaner.main import detect_job_type
        except ImportError:
            pytest.skip("detect_job_type not yet extracted")
        result = detect_job_type(text)
        assert result == expected


# ─── CleanerService Integration (unit-level, no Kafka) ───────────────────────

class TestCleanerServiceUnit:
    """Test the CleanerService._clean_job method without Kafka."""

    def _get_cleaner(self):
        from services.cleaner.main import CleanerService
        svc = CleanerService()
        return svc

    def test_clean_job_strips_html_from_description(self):
        svc = self._get_cleaner()
        raw_job = {
            "title": "  Python Developer  ",
            "description": "<p>Build <b>scalable</b> APIs</p>",
            "company_name": "TechCorp",
            "location_raw": "Bangalore",
            "salary_raw": "10-20 LPA",
            "source": "adzuna",
            "source_job_id": "abc123",
        }
        cleaned = svc._clean_job(raw_job)
        assert "<" not in cleaned.get("description", "")
        assert "Build" in cleaned.get("description", "")

    def test_clean_job_strips_title_whitespace(self):
        svc = self._get_cleaner()
        raw_job = {
            "title": "   Senior Engineer   ",
            "description": "Great role",
            "company_name": "Corp",
            "location_raw": "Mumbai",
            "source": "adzuna",
            "source_job_id": "xyz",
        }
        cleaned = svc._clean_job(raw_job)
        assert cleaned.get("title") == "Senior Engineer"

    def test_clean_job_preserves_source(self):
        svc = self._get_cleaner()
        raw_job = {
            "title": "Dev",
            "description": "Work",
            "company_name": "Co",
            "location_raw": "Delhi",
            "source": "greenhouse",
            "source_job_id": "g123",
        }
        cleaned = svc._clean_job(raw_job)
        assert cleaned.get("source") == "greenhouse"

    def test_empty_description_handled(self):
        svc = self._get_cleaner()
        raw_job = {
            "title": "Dev",
            "description": None,
            "company_name": "Co",
            "location_raw": "Pune",
            "source": "rss",
            "source_job_id": "r1",
        }
        cleaned = svc._clean_job(raw_job)
        assert cleaned.get("description") is not None  # Should be "" or missing gracefully
