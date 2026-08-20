"""
Seed script — populates the database with sample jobs for development/testing.
Usage: python scripts/seed_data.py [--count 500] [--clear]
"""

from __future__ import annotations

import asyncio
import argparse
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from shared.utils.url import normalize_url

SAMPLE_TITLES = [
    "Senior Python Engineer", "Full Stack Developer", "Data Scientist",
    "Machine Learning Engineer", "Backend Developer", "DevOps Engineer",
    "Product Manager", "Data Analyst", "Cloud Architect", "Frontend Developer",
    "iOS Developer", "Android Developer", "Security Engineer", "SRE",
    "Platform Engineer", "AI Research Engineer", "MLOps Engineer",
    "Staff Software Engineer", "Principal Engineer", "Engineering Manager",
    "Tech Lead", "React Developer", "Vue.js Developer", "Next.js Engineer",
    "FastAPI Developer", "Django Developer", "Flutter Developer",
    "Kubernetes Engineer", "Terraform Specialist", "AWS Solutions Architect",
    "Azure Cloud Engineer", "GCP Data Engineer", "Penetration Tester",
    "Cybersecurity Analyst", "Blockchain Developer", "AR/VR Engineer",
    "Database Administrator", "Data Engineer", "Big Data Engineer",
    "NLP Engineer", "Computer Vision Engineer", "QA Automation Engineer",
    "Performance Engineer", "Site Reliability Engineer", "B.Tech Fresher",
    "Off Campus Drive 2025", "Graduate Engineer Trainee", "MBA Intern",
    "Summer Intern 2025", "Junior Software Developer", "Mid-Level Go Engineer",
    "Senior Rust Developer", "Node.js Backend Engineer", "PHP Laravel Developer",
]

SAMPLE_COMPANIES = [
    "Google", "Microsoft", "Amazon", "Flipkart", "Infosys", "TCS", "Wipro",
    "Razorpay", "Zepto", "Meesho", "CRED", "Groww", "PhonePe", "Swiggy",
    "Zomato", "Ola", "Dunzo", "Postman", "Browserstack", "Freshworks",
    "HCL Technologies", "Tech Mahindra", "L&T Infotech", "Mindtree",
    "Paytm", "BYJU'S", "Unacademy", "upGrad", "Cars24", "Urban Company",
    "Reliance Jio", "Tata Motors", "Adani Group", "ITC Infotech",
    "Accenture India", "Deloitte USI", "PwC India", "EY GDS", "KPMG India",
    "Goldman Sachs Bengaluru", "JP Morgan Chase", "Morgan Stanley",
    "Uber India", "Meta India", "Apple India", "Stripe India", "Rippling",
    "Atlassian Bengaluru", "Zendesk", "Zeta", "Slice", "OneCard",
    "Jupiter Money", "Fi Money", "Koo", "ShareChat", "Moj",
    "Dream11", "Mobile Premier League", "Gameskraft", "Nazara Technologies",
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
    ("Ahmedabad", "Gujarat", "IN"),
    ("Kolkata", "West Bengal", "IN"),
    ("Jaipur", "Rajasthan", "IN"),
    ("Indore", "Madhya Pradesh", "IN"),
    ("Cochin", "Kerala", "IN"),
    ("Chandigarh", "Chandigarh", "IN"),
    (None, None, "IN"),
    (None, None, "IN"),
]

SAMPLE_SKILLS = [
    "Python", "Java", "Go", "TypeScript", "JavaScript", "Rust", "Kotlin",
    "FastAPI", "Django", "Spring Boot", "React", "Vue.js", "Next.js",
    "PostgreSQL", "MongoDB", "Redis", "Kafka", "Kubernetes", "Docker",
    "AWS", "GCP", "Azure", "Terraform", "Spark", "dbt", "Airflow",
    "TensorFlow", "PyTorch", "scikit-learn", "LangChain", "MLflow",
    "Flutter", "React Native", "Swift", "GraphQL", "gRPC", "RabbitMQ",
    "MySQL", "Cassandra", "Elasticsearch", "Kibana", "Prometheus", "Grafana",
    "Ansible", "Jenkins", "CI/CD", "Nginx", "Linux", "Shell Scripting",
    "Pandas", "NumPy", "SQL", "Tableau", "Power BI", "Looker", "Snowflake",
    "Databricks", "Redshift", "BigQuery", "Solidity", "Web3.js",
    "Cybersecurity", "SIEM", "OWASP", "Wireshark", "Metasploit",
]

SAMPLE_SOURCES = [
    "adzuna", "greenhouse", "lever", "workday", "indeed", "naukri",
    "linkedin", "rss", "government", "company_careers",
]
REMOTE_TYPES = ["remote", "remote", "hybrid", "hybrid", "on_site", "on_site", "remote"]
EXP_LEVELS = ["entry", "entry", "mid", "mid", "mid", "senior", "senior", "lead", "principal"]
JOB_TYPES = ["full_time", "full_time", "full_time", "full_time", "contract", "internship", "apprenticeship"]


def make_sample_job(idx: int) -> dict[str, Any]:
    title = random.choice(SAMPLE_TITLES)
    company = random.choice(SAMPLE_COMPANIES)
    location = random.choice(SAMPLE_LOCATIONS)
    skills = random.sample(SAMPLE_SKILLS, k=random.randint(3, 9))
    remote_type = random.choice(REMOTE_TYPES)
    exp_level = random.choice(EXP_LEVELS)
    job_type = random.choice(JOB_TYPES)
    source = random.choice(SAMPLE_SOURCES)

    salary_multiples = {
        "entry": (2, 7), "mid": (7, 22), "senior": (18, 45),
        "lead": (28, 70), "principal": (50, 120),
    }
    sal_range = salary_multiples.get(exp_level, (5, 15))
    salary_min = random.randint(*sal_range) * 100_000
    salary_max = salary_min + random.randint(2, 12) * 100_000

    posted_at = datetime.utcnow() - timedelta(days=random.randint(0, 21), hours=random.randint(0, 23))

    city, state, country = location
    if city:
        loc_display = f"{city}, {country}"
    else:
        loc_display = f"Remote, {country}"

    scam_prob = random.choices([
        random.uniform(0.0, 0.1),
        random.uniform(0.1, 0.3),
        random.uniform(0.4, 0.8),
    ], weights=[0.78, 0.17, 0.05])[0]

    content_seed = f"{title}|{company}|{'|'.join(skills[:3])}|{idx % 500}"
    fingerprint = uuid.uuid5(uuid.NAMESPACE_DNS, content_seed).hex

    company_slug = company.lower().replace(" ", "").replace("'", "")
    job_type_human = job_type.replace("_", " ")

    return {
        "_id": str(uuid.uuid4()),
        "title": title,
        "company_name": company,
        "description": f"We are looking for a {title} to join our team at {company}. "
                       f"You will work on exciting projects using {', '.join(skills[:4])}. "
                       f"This is a {job_type_human} role for someone with {exp_level}-level experience. "
                       f"Location: {loc_display}. {remote_type.title()} work available. "
                       f"Apply today and build the future with us!",
        "source": source,
        "source_job_id": f"{source}_{idx}_{uuid.uuid4().hex[:8]}",
        "source_url": normalize_url(None, title=title, company_name=company, source=source),
        "apply_url": normalize_url(None, title=title, company_name=company, source=source),
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
        "quality_score": round(random.uniform(35, 97), 1),
        "content_fingerprint": fingerprint,
        "posted_at": posted_at,
        "created_at": posted_at,
        "updated_at": datetime.utcnow(),
        "retry_count": 0,
    }


async def seed(count: int = 500, clear: bool = False) -> None:
    import os
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri = os.getenv(
        "MONGO_URI",
        "mongodb://admin:admin123@localhost:27017/jobplatform?authSource=admin",
    )
    client = AsyncIOMotorClient(mongo_uri)
    db = client["jobplatform"]

    if clear:
        print("⚠️  Clearing existing seed jobs…")
        await db.jobs.delete_many({"source": {"$in": SAMPLE_SOURCES}})
        await db.pipeline_events.delete_many({})

    print(f"🌱 Seeding {count} sample jobs (sources: {len(SAMPLE_SOURCES)})…")
    BATCH_SIZE = 500
    total_inserted = 0
    for offset in range(0, count, BATCH_SIZE):
        chunk_size = min(BATCH_SIZE, count - offset)
        jobs = [make_sample_job(offset + i) for i in range(chunk_size)]
        try:
            result = await db.jobs.insert_many(jobs, ordered=False)
            total_inserted += len(result.inserted_ids)
            print(f"  ↳ Inserted batch {offset // BATCH_SIZE + 1}: {len(result.inserted_ids)} jobs")
        except Exception as e:
            print(f"  ↳ Batch {offset // BATCH_SIZE + 1} had issues: {e}")

    print(f"✅ Inserted {total_inserted} jobs total")

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
    parser.add_argument("--count", type=int, default=500, help="Number of jobs to seed (default 500)")
    parser.add_argument("--clear", action="store_true", help="Clear existing seed jobs + pipeline events first")
    args = parser.parse_args()
    asyncio.run(seed(args.count, args.clear))
