"""
database/postgres_client.py

Thin wrapper around PostgreSQL for storing job segmentation results,
user accounts, resumes, and job applications.
"""

import psycopg2
from app.config.settings import settings
from app.utils.logger import get_logger


class PostgresClient:
    def __init__(self):
        self.logger = get_logger("postgres_client")
        self.conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        self.conn.autocommit = True
        self._ensure_schema()

    def _ensure_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS job_segments (
                    id SERIAL PRIMARY KEY,
                    job_url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    company TEXT,
                    source TEXT,
                    segment_id INTEGER,
                    segment_label TEXT,
                    is_validated BOOLEAN DEFAULT TRUE,
                    validation_reasons TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    full_name TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    job_url TEXT NOT NULL,
                    status TEXT DEFAULT 'applied',
                    applied_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) UNIQUE,
                    resume_text TEXT,
                    filename TEXT,
                    uploaded_at TIMESTAMP DEFAULT NOW()
                );
            """)
        self.logger.info("Ensured job_segments, users, applications, resumes tables exist")

    def upsert_segment(self, job_url: str, title: str, company: str, source: str,
                        segment_id: int, segment_label: str = None,
                        is_validated: bool = True, validation_reasons: str = None):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_segments (job_url, title, company, source, segment_id, segment_label, is_validated, validation_reasons)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_url) DO UPDATE SET
                    segment_id = EXCLUDED.segment_id,
                    segment_label = EXCLUDED.segment_label,
                    is_validated = EXCLUDED.is_validated,
                    validation_reasons = EXCLUDED.validation_reasons;
            """, (job_url, title, company, source, segment_id, segment_label, is_validated, validation_reasons))
        self.logger.info(f"Upserted segment for {job_url}: segment_id={segment_id}")

    def get_by_url(self, url: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM job_segments WHERE job_url = %s", (url,))
            return cur.fetchone()

    def create_user(self, username: str, email: str, hashed_password: str, full_name: str = None, location: str = None):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (username, email, hashed_password, full_name, location)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (username, email, hashed_password, full_name, location))
            user_id = cur.fetchone()[0]
        self.logger.info(f"Created user: {username}")
        return user_id

    def get_user_by_username(self, username: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, username, email, hashed_password, full_name, location FROM users WHERE username = %s", (username,))
            return cur.fetchone()

    def add_application(self, user_id: int, job_url: str, status: str = "applied"):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO applications (user_id, job_url, status)
                VALUES (%s, %s, %s);
            """, (user_id, job_url, status))
        self.logger.info(f"User {user_id} applied to {job_url}")

    def get_applications(self, user_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT a.job_url, a.status, a.applied_at, j.title, j.company
                FROM applications a
                LEFT JOIN job_segments j ON a.job_url = j.job_url
                WHERE a.user_id = %s
                ORDER BY a.applied_at DESC;
            """, (user_id,))
            return cur.fetchall()

    def upsert_resume(self, user_id: int, resume_text: str, filename: str):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO resumes (user_id, resume_text, filename)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    resume_text = EXCLUDED.resume_text,
                    filename = EXCLUDED.filename,
                    uploaded_at = NOW();
            """, (user_id, resume_text, filename))
        self.logger.info(f"Upserted resume for user {user_id}")

    def get_resume(self, user_id: int):
        with self.conn.cursor() as cur:
            cur.execute("SELECT resume_text, filename, uploaded_at FROM resumes WHERE user_id = %s", (user_id,))
            return cur.fetchone()

    def close(self):
        self.conn.close()