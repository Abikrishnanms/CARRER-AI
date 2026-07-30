"""
agents/embedding_agent.py

Consumes raw posting notifications from the queue, generates embeddings
via sentence-transformers, and stores them in Qdrant.
"""

from agents.base_agent import BaseAgent
from embedding.embedding_utils import embed_text


class EmbeddingAgent(BaseAgent):

    def __init__(self):
        super().__init__(agent_name="embedding_agent")

    def run(self):
        self.logger.info("Starting embedding agent, listening for raw_postings_ready...")
        self.queue.consume(queue_name="raw_postings_ready", callback=self.process_message)

    def process_message(self, message: dict):
        url = message.get("url")
        source = message.get("source")
        self.logger.info(f"Processing {url} from {source}")

        doc = self.mongo.get_by_url(url)
        if not doc:
            self.logger.warning(f"No Mongo document found for {url}")
            return

        text = f"{doc.get('title', '')} {doc.get('description', '')}".strip()
        if not text:
            self.logger.warning(f"Empty text for {url}, skipping embedding")
            return

        vector = embed_text(text)

        payload = {
            "title": doc.get("title"),
            "company": doc.get("company"),
            "source": source,
            "url": url,
        }

        self.qdrant.upsert_vector(job_url=url, vector=vector, payload=payload)
        self.logger.info(f"Embedded and stored: {url}")


if __name__ == "__main__":
    agent = EmbeddingAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.logger.info("Stopped by user")
    finally:
        agent.close()