"""
Seed script — populates the database with sample jobs for development/testing.
Usage: python scripts/seed_data.py [--count 100]
"""

from __future__ import annotations

import asyncio
import argparse
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

SAMPLE_TITLES = [
    "Senior Python Engineer", "Full Stack Developer", "Data Scientist",
    "Machine Learning Engineer", "Backend Developer", "DevOps Engineer",
    "Product Manager", "Data Analyst", "Cloud Architect", "Frontend Developer",
    "iOS Developer", "Android Developer", "Security Engineer", "SRE",
    "Platform Engineer", "AI Research Engineer", "MLOps Engineer",
]

SAMPLE_COMPANIES = [
    "Google", "Microsoft", "Amazon", "Flipkart", "Infosys", "TCS", "Wipro",
    "Razorpay", "Zepto", "Meesho", "CRED", "Groww", "PhonePe", "Swiggy",
    "Zomato", "Ola", "Dunzo", "Postman", "Browserstack", "Freshworks",
]

SAMPLE_LOCATIONS = [
    ("Bangalore", "Karnataka", "IN"),
    ("Mumbai", "Maharashtra", "IN"),
    ("Hyderabad", "Telangana", "IN"),
    ("Chennai", "Tamil Nadu", "IN"),
    ("Pune", "Maharashtra", "IN"),
    ("Delhi", "Delhi", "IN"),
    ("Gurgaon", "Haryana", "IN"),
    ("Noida", "Uttar Pradesh", "IN"),
    (None, None, "IN"),  # Remote
]

SAMPLE_SKILLS = [
    "Python", "Java", "Go", "TypeScript", "JavaScript", "Rust", "Kotlin",
    "FastAPI", "Django", "Spring Boot", "React", "Vue.js", "Next.js",
    "PostgreSQL", "MongoDB", "Redis", "Kafka", "Kubernetes", "Docker",
    "AWS", "GCP", "Azure", "Terraform", "Spark", "dbt", "Airflow",
    "TensorFlow", "PyTorch", "scikit-learn", "LangChain", "MLflow",
]

SAMPLE_SOURCES = ["adzuna", "greenhouse", "indeed", "rss"]
REMOTE_TYPES = ["remote", "hybrid", "on_site", "remote", "hybrid"]  # weighted
EXP_LEVELS = ["entry", "mid", "mid", "senior", "senior", "lead"]
JOB_TYPES = ["full_time", "full_time", "full_time", "contract", "internship"]


def make_sample_job(idx: int) -> dict[str, Any]:
    title = random.choice(SAMPLE_TITLES)
    company = random.choice(SAMPLE_COMPANIES)
    location = random.choice(SAMPLE_LOCATIONS)
    skills = random.sample(SAMPLE_SKILLS, k=random.randint(3, 8))
    remote_type = random.choice(REMOTE_TYPES)
    exp_level = random.choice(EXP_LEVELS)
    job_type = random.choice(JOB_TYPES)
    source = random.choice(SAMPLE_SOURCES)

    salary_multiples = {"entry": (3, 8), "mid": (8, 20), "senior": (20, 40), "lead": (30, 60)}
    sal_range = salary_multiples.get(exp_level, (5, 15))
    salary_min = random.randint(*sal_range) * 100_000
    salary_max = salary_min + random.randint(3, 10) * 100_000

    posted_at = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

    city, state, country = location
    loc_display = f"{city}, {country}" if city else f"Remote, {country}"

    scam_prob = random.choices([
        random.uniform(0.0, 0.1),
        random.uniform(0.1, 0.3),
        random.uniform(0.4, 0.8),
    ], weights=[0.75, 0.20, 0.05])[0]

    return {
        "_id": str(uuid.uuid4()),
        "title": title,
        "company_name": company,
        "description": f"We are looking for a {title} to join our team at {company}. "
                       f"You will work on exciting projects using {', '.join(skills[:3])}. "
                       f"This is a {job_type.replace('_', ' ')} role for someone with {exp_level}-level experience.",
        "source": source,
        "source_job_id": f"{source}_{idx}_{uuid.uuid4().hex[:8]}",
        "source_url": f"https://{source}.com/jobs/{idx}",
        "apply_url": f"https://{company.lower().replace(' ', '')}.com/careers/{idx}",
        "location_city": city,
        "location_state": state,
        "location_country": country,
        "location_raw": loc_display,
        "remote_type": remote_type,
        "job_type": job_type,
        "experience_level": exp_level,
        "required_skills": skills,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": "INR",
        "salary_period": "yearly",
        "salary_display": f"₹{salary_min // 100_000}L – ₹{salary_max // 100_000}L",
        "status": "published",
        "is_verified": scam_prob < 0.3,
        "is_duplicate": False,
        "scam_probability": round(scam_prob, 3),
        "scam_risk_level": "very_low" if scam_prob < 0.2 else "low" if scam_prob < 0.4 else "medium" if scam_prob < 0.6 else "high",
        "quality_score": round(random.uniform(40, 95), 1),
        "content_fingerprint": uuid.uuid4().hex,
        "posted_at": posted_at,
        "created_at": posted_at,
        "updated_at": datetime.utcnow(),
        "retry_count": 0,
    }


async def seed(count: int = 200, clear: bool = False) -> None:
    import os
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri = os.getenv(
        "MONGO_URI",
        "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin",
    )
    client = AsyncIOMotorClient(mongo_uri)
    db = client["jobplatform"]

    if clear:
        print("⚠️  Clearing existing jobs…")
        await db.jobs.delete_many({"source": {"$in": SAMPLE_SOURCES}})

    print(f"🌱 Seeding {count} sample jobs…")
    jobs = [make_sample_job(i) for i in range(count)]

    result = await db.jobs.insert_many(jobs, ordered=False)
    print(f"✅ Inserted {len(result.inserted_ids)} jobs")

    # Seed a default admin user
    existing_admin = await db.users.find_one({"email": "admin@talentlens.io"})
    if not existing_admin:
        import hashlib
        salt = os.getenv("PASSWORD_SALT", "job-platform-salt-2024")
        pw_hash = hashlib.sha256(f"{salt}admin123".encode()).hexdigest()
        await db.users.insert_one({
            "_id": str(uuid.uuid4()),
            "email": "admin@talentlens.io",
            "full_name": "Platform Admin",
            "password_hash": pw_hash,
            "role": "admin",
            "is_active": True,
            "email_verified": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        print("✅ Default admin created: admin@talentlens.io / admin123")
    else:
        print("ℹ️  Admin user already exists")

    client.close()
    print("🎉 Seeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the TalentLens database")
    parser.add_argument("--count", type=int, default=200, help="Number of jobs to seed")
    parser.add_argument("--clear", action="store_true", help="Clear existing seed jobs first")
    args = parser.parse_args()
    asyncio.run(seed(args.count, args.clear))
