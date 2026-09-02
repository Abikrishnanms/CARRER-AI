"""
Resume text extractor and candidate profile parser.
Supports PDF (.pdf), Microsoft Word (.docx), and Plain Text (.txt) formats.
Extracts: skills, experience, education, certifications, projects, location preference, remote preference.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

CANONICAL_SKILLS: list[str] = [
    # Programming Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "SQL", "HTML", "CSS",
    "Perl", "MATLAB", "Bash", "Shell", "Dart", "Elixir", "Haskell",
    # Web Frameworks
    "React", "React Native", "Next.js", "Vue.js", "Angular", "Node.js",
    "Express", "Django", "FastAPI", "Flask", "Spring Boot", "ASP.NET",
    "Laravel", "NestJS", "Svelte", "Nuxt.js", "Ruby on Rails", "Gin",
    # Data & AI / ML
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "NLP",
    "Computer Vision", "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas",
    "NumPy", "OpenCV", "Data Analysis", "Data Science", "ETL", "Spark",
    "Hadoop", "Airflow", "Kafka", "MLflow", "Hugging Face", "LangChain",
    "LlamaIndex", "XGBoost", "LightGBM", "spaCy", "NLTK", "Matplotlib",
    "SciPy", "Seaborn", "Plotly", "dbt",
    # Cloud & DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible",
    "Jenkins", "CI/CD", "Linux", "Bash", "Shell", "Git", "GitHub", "GitLab",
    "Nginx", "Microservices", "Serverless", "Helm", "ArgoCD", "Prometheus",
    "Grafana", "Datadog", "GitHub Actions", "GitLab CI", "CircleCI",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Qdrant",
    "DynamoDB", "Cassandra", "Snowflake", "BigQuery", "Firebase", "SQLite",
    "MariaDB", "Neo4j", "CockroachDB", "Pinecone", "Weaviate",
    # Software Engineering & Management
    "REST API", "GraphQL", "gRPC", "System Design", "Agile", "Scrum",
    "Jira", "Unit Testing", "PyTest", "Jest", "Figma", "UI/UX",
    "Project Management", "Product Management", "Kanban", "TDD", "BDD",
    "Microservices", "Event-Driven Architecture", "Istio", "RabbitMQ",
]

JOB_TITLE_KEYWORDS: list[str] = [
    "Software Engineer", "Backend Developer", "Frontend Engineer",
    "Full Stack Developer", "Data Scientist", "Machine Learning Engineer",
    "DevOps Engineer", "Cloud Architect", "Site Reliability Engineer",
    "Data Analyst", "Data Engineer", "Product Manager", "Project Manager",
    "UI/UX Designer", "QA Engineer", "Mobile App Developer",
    "Security Engineer", "System Administrator", "Solutions Architect",
    "AI Engineer", "Platform Engineer", "MLOps Engineer",
    "Android Developer", "iOS Developer", "Embedded Engineer",
]

DEGREE_PATTERNS: list[str] = [
    r"\b(b\.?tech|b\.?e\.?|bachelor of technology|bachelor of engineering)\b",
    r"\b(m\.?tech|m\.?e\.?|master of technology|master of engineering)\b",
    r"\b(b\.?s\.?c\.?|bachelor of science|b\.?c\.?a\.?)\b",
    r"\b(m\.?s\.?c\.?|master of science|m\.?c\.?a\.?)\b",
    r"\b(m\.?b\.?a\.?|master of business administration)\b",
    r"\b(ph\.?d\.?|doctor of philosophy)\b",
    r"\b(bachelor|master|diploma|associate)\b",
]

CERTIFICATION_PATTERNS: list[tuple[str, str]] = [
    (r"\baws\s+certified\b", "AWS Certified"),
    (r"\bazure\s+certified\b", "Azure Certified"),
    (r"\bgcp\s+certified\b|google\s+cloud\s+certified\b", "GCP Certified"),
    (r"\bcertified\s+kubernetes\b|ckad\b|cka\b", "Certified Kubernetes"),
    (r"\bpmp\b", "PMP"),
    (r"\bscrum\s+master\b|csm\b", "Scrum Master"),
    (r"\bcissp\b", "CISSP"),
    (r"\bcompTIA\b|comptia\s+a\+\b|comptia\s+security\+\b", "CompTIA"),
    (r"\bgoogle\s+analytics\b", "Google Analytics"),
    (r"\bmeta\s+certified\b|facebook\s+blueprint\b", "Meta Certified"),
    (r"\btensorflow\s+developer\b", "TensorFlow Developer"),
    (r"\bhashicorp\s+certified\b", "HashiCorp Certified"),
    (r"\bccna\b|ccnp\b", "Cisco Certified"),
    (r"\bpython\s+certified\b|pcep\b|pcap\b", "Python Certified"),
    (r"\bdatadog\s+certified\b", "Datadog Certified"),
]

# Indian and common global tech cities
LOCATION_CITIES: list[str] = [
    "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai",
    "pune", "kolkata", "noida", "gurugram", "gurgaon", "ahmedabad",
    "kochi", "jaipur", "indore", "bhopal", "chandigarh", "coimbatore",
    "new york", "san francisco", "london", "berlin", "singapore",
    "dubai", "toronto", "sydney", "amsterdam", "paris", "tokyo",
]

REMOTE_SIGNALS: list[str] = [
    "remote", "work from home", "wfh", "fully remote", "distributed team",
    "remote-first", "remote friendly", "work remotely",
]


def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    """Extract raw text from PDF, DOCX, or TXT file bytes."""
    fname = (filename or "").lower()

    if fname.endswith(".docx"):
        return _extract_docx(file_bytes)
    elif fname.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    else:
        # Fallback to plain text decoding
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore")


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfminer."""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(io.BytesIO(file_bytes))
        return text or ""
    except Exception:
        # Fallback regex extraction if pdfminer encounters binary formatting issues
        raw = file_bytes.decode("latin-1", errors="ignore")
        clean = re.sub(r"[^\w\s\.,\-\+]", " ", raw)
        return clean


def _extract_docx(file_bytes: bytes) -> str:
    """Extract paragraph text from Word DOCX bytes via zipfile XML parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            texts = []
            for elem in tree.iter():
                if elem.tag.endswith("}t") and elem.text:
                    texts.append(elem.text)
            return " ".join(texts)
    except Exception:
        return ""


def parse_candidate_profile(raw_text: str, filename: str = "") -> dict[str, Any]:
    """Parse raw resume text into a structured candidate profile."""
    text = raw_text or ""
    text_lower = text.lower()

    # 1. Extract Skills
    found_skills: set[str] = set()
    for skill in CANONICAL_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found_skills.add(skill)

    # 2. Extract Experience Years & Level
    exp_years = 0.0
    exp_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+|\-)?\s*(?:years?|yrs?)\b", text_lower)
    if exp_matches:
        try:
            years_list = [float(y) for y in exp_matches if float(y) <= 35]
            if years_list:
                exp_years = max(years_list)
        except ValueError:
            pass

    if exp_years >= 8 or "lead" in text_lower or "principal" in text_lower or "architect" in text_lower:
        exp_level = "lead"
    elif exp_years >= 5 or "senior" in text_lower or "sr." in text_lower:
        exp_level = "senior"
    elif exp_years >= 2 or "mid" in text_lower or "associate" in text_lower:
        exp_level = "mid"
    else:
        exp_level = "entry"

    # 3. Extract Target Job Titles
    found_titles: set[str] = set()
    for title in JOB_TITLE_KEYWORDS:
        pattern = r"\b" + re.escape(title.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found_titles.add(title)

    # 4. Extract Education Degrees
    found_degrees: set[str] = set()
    for degree_pat in DEGREE_PATTERNS:
        match = re.search(degree_pat, text_lower)
        if match:
            found_degrees.add(match.group(0).upper())

    # 5. Extract Certifications (broad patterns)
    certs: list[str] = []
    for pattern, cert_label in CERTIFICATION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            if cert_label not in certs:
                certs.append(cert_label)

    # 6. Extract Project Highlights
    projects: list[str] = []
    proj_section = re.split(r"\b(projects?|portfolio|key achievements)\b", text_lower)
    if len(proj_section) > 2:
        snippet = proj_section[2][:500].strip()
        lines = [l.strip() for l in snippet.split("\n") if len(l.strip()) > 15]
        projects = lines[:3]

    # 7. Extract Location Preference
    location_preference = ""
    for city in LOCATION_CITIES:
        if re.search(r"\b" + re.escape(city) + r"\b", text_lower):
            location_preference = city.title()
            break

    # 8. Detect Remote Preference
    remote_preference = ""
    for signal in REMOTE_SIGNALS:
        if signal in text_lower:
            remote_preference = "remote"
            break

    return {
        "filename": filename,
        "raw_text": text[:5000],
        "skills": sorted(list(found_skills)),
        "experience_years": exp_years,
        "experience_level": exp_level,
        "target_titles": sorted(list(found_titles)) or ["Software Engineer"],
        "education_degrees": sorted(list(found_degrees)),
        "certifications": certs,
        "projects": projects,
        "location_preference": location_preference,
        "remote_preference": remote_preference,
    }
