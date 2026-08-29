from database.qdrant_client import QdrantClient
from database.postgres_client import PostgresClient

qdrant = QdrantClient()
postgres = PostgresClient()

# Get the resume vector back out for user 1
points = qdrant.client.retrieve(collection_name=qdrant.COLLECTION_NAME, ids=[])  # not used, see below

# Simplest: re-fetch resume text and re-embed for the query
resume_row = postgres.get_resume(user_id=1)
resume_text = resume_row[0]

from embedding.embedding_utils import embed_text
vector = embed_text(resume_text[:2000])

results = qdrant.recommend_jobs(vector, limit=10)
for r in results:
    print(f"{r.score:.3f} - {r.payload.get('title')} @ {r.payload.get('company')}")

postgres.close()