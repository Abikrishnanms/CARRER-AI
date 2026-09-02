"""
Multi-factor recommendation and skill-gap analysis engine.
Ranks verified jobs against candidate profiles and generates transparent match explanations.

Scoring weights:
- Skill Match:          40%
- Title Similarity:     20%
- Experience Match:     15%
- Education / Certs:    10%
- Location / Remote:    15%
"""

from __future__ import annotations

import re
from typing import Any

# Skill category labels for display
SKILL_CATEGORY_LABELS: dict[str, str] = {
    "programming_languages": "Languages",
    "web_frameworks": "Frameworks",
    "databases": "Databases",
    "cloud_devops": "Cloud & DevOps",
    "data_ml": "Data & AI/ML",
    "messaging": "Messaging",
    "methodologies": "Methodologies",
    "soft_skills": "Soft Skills",
    "other": "Other",
}

# Rough category map for strength grouping
_SKILL_CATEGORY_MAP: dict[str, str] = {
    # Languages
    **{s.lower(): "programming_languages" for s in [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
        "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "html", "css",
        "perl", "matlab", "bash", "shell", "dart", "elixir", "haskell",
    ]},
    # Web frameworks
    **{s.lower(): "web_frameworks" for s in [
        "react", "react native", "next.js", "vue.js", "angular", "node.js",
        "express", "django", "fastapi", "flask", "spring boot", "asp.net",
        "laravel", "nestjs", "svelte", "nuxt.js", "ruby on rails", "gin",
    ]},
    # Databases
    **{s.lower(): "databases" for s in [
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "qdrant",
        "dynamodb", "cassandra", "snowflake", "bigquery", "firebase", "sqlite",
        "mariadb", "neo4j", "cockroachdb", "pinecone", "weaviate",
    ]},
    # Cloud & DevOps
    **{s.lower(): "cloud_devops" for s in [
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
        "jenkins", "ci/cd", "linux", "nginx", "microservices", "serverless",
        "helm", "argocd", "prometheus", "grafana", "datadog", "github actions",
        "gitlab ci", "circleci",
    ]},
    # Data & ML
    **{s.lower(): "data_ml" for s in [
        "machine learning", "deep learning", "artificial intelligence", "nlp",
        "computer vision", "pytorch", "tensorflow", "scikit-learn", "pandas",
        "numpy", "opencv", "data analysis", "data science", "etl", "spark",
        "hadoop", "airflow", "kafka", "mlflow", "hugging face", "langchain",
        "llamaindex", "xgboost", "lightgbm", "spacy", "nltk", "matplotlib",
        "scipy", "seaborn", "plotly", "dbt",
    ]},
    # Methodologies
    **{s.lower(): "methodologies" for s in [
        "rest api", "graphql", "grpc", "system design", "agile", "scrum",
        "jira", "unit testing", "pytest", "jest", "figma", "ui/ux",
        "project management", "product management", "kanban", "tdd", "bdd",
        "event-driven architecture", "istio", "rabbitmq",
    ]},
}


def score_job_match(profile: dict[str, Any], job: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """
    Calculate multi-factor job match percentage (0–100%) and match explanation signals.

    Weights:
    - Skill Match:       40%
    - Title Similarity:  20%
    - Experience Match:  15%
    - Education / Certs: 10%
    - Location / Remote: 15%
    """
    cand_skills = {s.lower().strip() for s in profile.get("skills", [])}
    cand_titles = [t.lower().strip() for t in profile.get("target_titles", [])]
    cand_exp_years = float(profile.get("experience_years", 0))
    cand_exp_level = (profile.get("experience_level") or "entry").lower()
    cand_degrees = {d.lower() for d in profile.get("education_degrees", [])}
    cand_certs = profile.get("certifications", [])
    cand_projects = profile.get("projects", [])

    loc_pref = (profile.get("location_preference") or "").lower().strip()
    remote_pref = (profile.get("remote_preference") or "").lower().strip()

    job_title = (job.get("title") or "").lower().strip()
    job_req_skills = [s for s in job.get("required_skills", []) if s]
    job_skills_lower = [s.lower().strip() for s in job_req_skills]
    job_exp_level = (job.get("experience_level") or "entry").lower()
    job_remote_type = (job.get("remote_type") or "unknown").lower()
    job_location = (job.get("location_city") or job.get("location_raw") or "").lower()

    # ── 1. Skill Match Score (40%) ──────────────────────────────────
    matched_skills: list[str] = []
    missing_skills: list[str] = []

    for orig_skill, skill_low in zip(job_req_skills, job_skills_lower):
        if skill_low in cand_skills or any(skill_low in cs for cs in cand_skills):
            matched_skills.append(orig_skill)
        else:
            missing_skills.append(orig_skill)

    total_job_skills = max(1, len(job_req_skills))
    skill_match_ratio = len(matched_skills) / total_job_skills
    skill_score = skill_match_ratio * 40.0

    # ── 2. Title Similarity Score (20%) ────────────────────────────
    title_score = 0.0
    if job_title:
        title_tokens = set(re.findall(r"\w+", job_title))
        best_token_overlap = 0
        for ct in cand_titles:
            ct_tokens = set(re.findall(r"\w+", ct))
            overlap = len(title_tokens & ct_tokens)
            best_token_overlap = max(best_token_overlap, overlap)

        if best_token_overlap >= 2 or any(ct in job_title or job_title in ct for ct in cand_titles):
            title_score = 20.0
        elif best_token_overlap == 1:
            title_score = 12.0
        else:
            title_score = 6.0

    # ── 3. Experience Match Score (15%) ────────────────────────────
    exp_score = 10.0
    level_order = {"entry": 1, "mid": 2, "senior": 3, "lead": 4}
    c_lvl = level_order.get(cand_exp_level, 1)
    j_lvl = level_order.get(job_exp_level, 1)

    if c_lvl == j_lvl:
        exp_score = 15.0
    elif c_lvl > j_lvl:
        exp_score = 12.0  # Overqualified — still a good fit
    elif c_lvl == j_lvl - 1:
        exp_score = 10.0  # Slight stretch goal
    else:
        exp_score = 4.0

    # ── 4. Education + Certification Score (10%) ───────────────────
    edu_score = 5.0
    if cand_degrees:
        edu_score = 8.0
    if cand_certs:
        edu_score = min(10.0, edu_score + (2.0 if len(cand_certs) >= 2 else 1.0))

    # ── 5. Location / Remote Preference Score (15%) ────────────────
    loc_score = 8.0
    location_matched = False

    if job_remote_type == "remote":
        loc_score = 15.0
        location_matched = True
    elif remote_pref == "remote" and job_remote_type in ("remote", "hybrid"):
        loc_score = 13.0
        location_matched = True
    elif loc_pref and job_location and loc_pref in job_location:
        loc_score = 15.0
        location_matched = True
    elif job_remote_type == "hybrid":
        loc_score = 11.0

    # ── Composite Match Percentage (capped 30%–98%) ────────────────
    total_raw = skill_score + title_score + exp_score + edu_score + loc_score
    final_pct = round(min(98.0, max(30.0, total_raw)), 1)

    # ── Build Positive Signals & Warnings ──────────────────────────
    positives: list[str] = []
    warnings: list[str] = []

    if job_req_skills:
        positives.append(f"✓ {len(matched_skills)}/{len(job_req_skills)} required skills matched")
    else:
        positives.append("✓ Strong profile keyword alignment")

    if c_lvl == j_lvl:
        positives.append(f"✓ Experience level matches ({cand_exp_level.capitalize()})")
    elif c_lvl > j_lvl:
        positives.append(f"✓ Overqualified — strong candidate ({cand_exp_level.capitalize()})")
    elif c_lvl == j_lvl - 1:
        positives.append("✓ Excellent career growth opportunity")

    if title_score >= 12.0:
        positives.append(f"✓ Job title aligns with your target roles")

    if cand_degrees:
        positives.append("✓ Educational qualification verified")

    if cand_certs:
        cert_str = ", ".join(cand_certs[:2])
        positives.append(f"✓ Relevant certifications: {cert_str}")

    if cand_projects:
        positives.append("✓ Relevant project experience detected")

    if location_matched:
        if job_remote_type == "remote":
            positives.append("✓ Fully remote — location preference matches")
        elif loc_pref:
            positives.append(f"✓ Location preference matches ({loc_pref.title()})")
        else:
            positives.append("✓ Hybrid/remote work mode available")

    if missing_skills:
        miss_count = len(missing_skills)
        miss_str = ", ".join(missing_skills[:2])
        if miss_count > 2:
            miss_str += f" (+{miss_count - 2} more)"
        warnings.append(f"⚠ Missing skill: {miss_str}")

    if c_lvl < j_lvl - 1:
        warnings.append(f"⚠ Role requires {job_exp_level.capitalize()} level experience")

    explanation: dict[str, Any] = {
        "match_percentage": final_pct,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "positive_signals": positives,
        "warning_signals": warnings,
        "score_breakdown": {
            "skill_score": round(skill_score, 1),
            "title_score": round(title_score, 1),
            "experience_score": round(exp_score, 1),
            "education_score": round(edu_score, 1),
            "location_score": round(loc_score, 1),
        },
    }

    return final_pct, explanation


def compute_skill_gap_analysis(
    profile: dict[str, Any],
    recommended_jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate an aggregated candidate skill gap report based on top recommended jobs.
    Returns:
    - candidate skills with categories
    - high-demand missing skills with demand counts
    - recommended learning path
    - top strength categories
    """
    cand_skills: list[str] = profile.get("skills", [])
    cand_skills_set = {s.lower().strip() for s in cand_skills}

    # Count missing skills across all recommendations
    missing_counts: dict[str, int] = {}
    for item in recommended_jobs:
        match_info = item.get("match", {})
        for missing in match_info.get("missing_skills", []):
            if missing:
                missing_counts[missing] = missing_counts.get(missing, 0) + 1

    sorted_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)
    high_demand_missing = [
        {
            "skill": skill,
            "demand_count": count,
            "importance": "High" if count >= 3 else ("Medium" if count >= 2 else "Low"),
            "demand_pct": round(count / max(1, len(recommended_jobs)) * 100),
        }
        for skill, count in sorted_missing[:8]
    ]

    learning_path = [m["skill"] for m in high_demand_missing[:4]]

    # Categorize candidate strengths
    categorized_strengths: dict[str, list[str]] = {}
    for skill in cand_skills:
        cat = _SKILL_CATEGORY_MAP.get(skill.lower(), "other")
        categorized_strengths.setdefault(cat, []).append(skill)

    # Top strength categories (by count)
    top_strength_categories = sorted(
        [{"category": SKILL_CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
          "skills": skills,
          "count": len(skills)}
         for cat, skills in categorized_strengths.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:4]

    return {
        "total_skills_count": len(cand_skills),
        "candidate_skills": cand_skills,
        "top_strengths": cand_skills[:10],
        "top_strength_categories": top_strength_categories,
        "missing_high_demand_skills": high_demand_missing,
        "recommended_learning_path": learning_path,
        "certifications": profile.get("certifications", []),
        "experience_level": profile.get("experience_level", "entry"),
        "experience_years": profile.get("experience_years", 0),
    }
