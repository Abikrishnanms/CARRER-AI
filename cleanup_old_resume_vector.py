from database.qdrant_client import QdrantClient
import uuid

q = QdrantClient()
point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "resume_1"))
q.client.delete(collection_name=q.COLLECTION_NAME, points_selector=[point_id])
print("Deleted old resume vector from job_embeddings")