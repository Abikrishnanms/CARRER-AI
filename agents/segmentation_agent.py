"""
agents/segmentation_agent.py

Pulls all job embeddings from Qdrant, clusters them using HDBSCAN,
and writes segment assignments to PostgreSQL.
"""

import hdbscan
import numpy as np

from agents.base_agent import BaseAgent
from validation.qualiity_checks import quality_check


class SegmentationAgent(BaseAgent):

    def __init__(self):
        super().__init__(agent_name="segmentation_agent")

    def run(self, min_cluster_size: int = 4, min_samples : int = None):
        self.logger.info("Fetching all vectors from Qdrant...")
        points = self.qdrant.scroll_all(limit=1000)

        if not points:
            self.logger.warning("No points found in Qdrant. Nothing to segment.")
            return {"clustered": 0, "noise": 0, "skipped": 0}

        vectors = np.array([p.vector for p in points])
        payloads = [p.payload for p in points]

        self.logger.info(f"Running HDBSCAN on {len(vectors)} vectors...")
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,min_samples=min_samples, metric="euclidean")
        labels = clusterer.fit_predict(vectors)

        clustered = 0
        noise = 0
        skipped = 0

        for payload, label in zip(payloads, labels):
            job_url = payload.get("url")
            if not job_url:
                self.logger.warning(f"Skipping point with missing url: {payload}")
                skipped += 1
                continue
            check = quality_check({"title": payload.get("title"), "description": payload.get("description"), "url": job_url})
            segment_id = int(label)
            segment_label = "noise" if segment_id == -1 else f"cluster_{segment_id}"

            try:
                self.postgres.upsert_segment(
                    job_url=job_url,
                    title=payload.get("title"),
                    company=payload.get("company"),
                    source=payload.get("source"),
                    segment_id=segment_id,
                    segment_label=segment_label,
                    is_validated = check["is_valid"],
                    validation_reasons = ", ".join(check["reasons"]) if check["reasons"] else None,                 
                )
            except Exception as e:
                self.logger.error(f"Failed to upsert segment for {job_url}: {e}")
                skipped += 1
                continue

            if segment_id == -1:
                noise += 1
            else:
                clustered += 1

        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        self.logger.info(
            f"Done: {num_clusters} clusters found, {clustered} clustered, "
            f"{noise} noise points, {skipped} skipped"
        )
        return {
            "num_clusters": num_clusters,
            "clustered": clustered,
            "noise": noise,
            "skipped": skipped,
        }


if __name__ == "__main__":
    agent = SegmentationAgent()
    result = agent.run(min_cluster_size=4, min_samples = 2)
    print(result)
    agent.close()