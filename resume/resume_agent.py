"""
resume/resume_agent.py
"""

from resume.resume_parser import extract_resume_text
from embedding.embedding_utils import embed_text
from database.postgres_client import PostgresClient
from database.qdrant_client import QdrantClient


def process_resume(uploaded_file, user_id: int):
    text = extract_resume_text(uploaded_file)
    if not text or len(text.strip()) < 50:
        return {"success": False, "error": "Could not extract enough text from resume"}

    postgres = PostgresClient()
    qdrant = QdrantClient()
    try:
        postgres.upsert_resume(user_id=user_id, resume_text=text, filename=uploaded_file.name)

        vector = embed_text(text[:2000])
        qdrant.upsert_resume_vector(
            user_id=user_id,
            vector=vector,
            payload={"user_id": user_id, "type": "resume"},
        )
        return {"success": True, "text_length": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        postgres.close()