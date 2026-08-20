# Per-line annotated: services/embedder/main.py

This file contains the original source lines from `services/embedder/main.py` followed by concise explanations for each line or block.

---

1: """
2: Embedder Service — Vector Embedding Generator (BATCH MODE).
3: Consumes from Kafka topic: job.verified
4: Generates embeddings with batched SentenceTransformers.encode(),
5: batch-upserts to Qdrant, bulk-updates MongoDB with embedding_id + status="published".
6: """
   Explanation: Module docstring describing responsibilities.

7: from __future__ import annotations
   Explanation: Postponed annotations for forward references.

8: import asyncio
9: import logging
10: import os
11: import time
12: import uuid
13: from datetime import datetime
14: from typing import Any
   Explanation: Standard imports for async work, logging, env, timing and typing.

15: from shared.kafka.consumer import KafkaConsumerClient
16: from shared.kafka.topics import TOPICS
17: from shared.database.session import get_mongo_client
   Explanation: Kafka consumer wrapper, topic constants, and Mongo client helper.

18: logger = logging.getLogger(__name__)
   Explanation: Module logger.

19: EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
20: QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
21: QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
22: QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_JOBS", "job_embeddings")
23: VECTOR_SIZE = 384
   Explanation: Configuration defaults for embedding model and Qdrant connection.

24: DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDER_BATCH_SIZE", "96"))
25: CONCURRENT_DB_WRITES = int(os.getenv("EMBEDDER_DB_WORKERS", "40"))
   Explanation: Batch size and DB concurrency tuning parameters.

26: class EmbedderService:
27:     """
28:     Embedding Generator Agent (batch mode).
29:     - Batched SentenceTransformer.encode(list_of_texts) → 10–100× faster than per-job
30:     - Batched Qdrant upsert (one call per batch)
31:     - bulk_write MongoDB status=published updates
32:     """
   Explanation: Class purpose and optimizations summary.

33:     def __init__(self) -> None:
34:         self.batch_size = DEFAULT_BATCH_SIZE
35:         self.consumer = KafkaConsumerClient(
36:             topics=[TOPICS.JOB_VERIFIED],
37:             group_id="embedder-service",
38:             max_poll_records=max(150, self.batch_size * 2),
39:         )
40:         self.model = None
41:         self.qdrant_client = None
42:         self.running = False
   Explanation: Initialize consumer, placeholders for model & qdrant, and running flag.

43:     async def start(self) -> None:
44:         try:
45:             from sentence_transformers import SentenceTransformer
46:             self.model = SentenceTransformer(EMBEDDING_MODEL)
47:             logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
48:         except ImportError:
49:             logger.warning("sentence-transformers not installed — embedder will skip vectorization")
   Explanation: Attempt to load SentenceTransformers model; log and degrade if unavailable.

50:         try:
51:             from qdrant_client import QdrantClient
52:             from qdrant_client.models import Distance, VectorParams
53:
54:             self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
55:             collections = self.qdrant_client.get_collections().collections
56:             existing_names = [c.name for c in collections]
57:             if QDRANT_COLLECTION not in existing_names:
58:                 self.qdrant_client.create_collection(
59:                     collection_name=QDRANT_COLLECTION,
60:                     vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
61:                 )
62:                 logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
63:         except Exception as e:
64:             logger.warning(f"Qdrant not available: {e} — embeddings will be stored but not indexed")
   Explanation: Try to connect to Qdrant and create collection if missing; handle failures gracefully.

65:         await self.consumer.start()
66:         self.running = True
67:         logger.info("🧬 Embedder service started (batch=%d)", self.batch_size)
68:         await self.consumer.consume_batch(self._handle_batch, batch_size=self.batch_size, timeout_ms=3000)
   Explanation: Start consumer and begin batch consumption with `_handle_batch` as handler.

69:     async def stop(self) -> None:
70:         self.running = False
71:         await self.consumer.stop()
   Explanation: Stop consumer and mark service not running.

72:     async def _handle_batch(self, messages: list[dict]) -> None:
73:         start = time.monotonic()
74:         n = len(messages)
75:         if n == 0:
76:             return
   Explanation: Early return when no messages; measure start time for metrics.

77:         job_ids: list[str] = []
78:         embed_texts: list[str] = []
79:         payloads: list[dict[str, Any]] = []
80:         messages_by_id: dict[str, dict] = {}
   Explanation: Prepare lists to collect job ids, embedding texts and payload metadata.

81:         for m in messages:
82:             job_id = m.get("_id", m.get("id", str(uuid.uuid4())))
83:             job_ids.append(job_id)
84:             messages_by_id[job_id] = m

85:             title = m.get("title", "")
86:             description = (m.get("description", "") or "")[:1000]
87:             skills = " ".join(m.get("required_skills", []) or [])
88:             company = m.get("company_name", "")
89:             location = m.get("location_city", "") or ""
90:             embed_texts.append(f"{title}. {company}. {location}. Skills: {skills}. {description}")

91:             payloads.append({
92:                 "job_id": job_id,
93:                 "title": title,
94:                 "company_name": company,
95:                 "location": location,
96:                 "remote_type": m.get("remote_type", "unknown"),
97:                 "experience_level": m.get("experience_level", "unknown"),
98:                 "job_type": m.get("job_type", "unknown"),
99:                 "salary_min": m.get("salary", {}).get("min_value") if isinstance(m.get("salary"), dict) else m.get("salary_min"),
100:                "salary_max": m.get("salary", {}).get("max_value") if isinstance(m.get("salary"), dict) else m.get("salary_max"),
101:            })
   Explanation: Build embedding input text and corresponding payload metadata for Qdrant.

102:        embedding_ids = [str(uuid.uuid4()) for _ in job_ids]
   Explanation: Generate unique embedding IDs to use as Qdrant point IDs.

103:        vectors_list: list[list[float]] | None = None
104:        if self.model is not None:
105:            try:
106:                loop = asyncio.get_event_loop()
107:                vectors_np = await loop.run_in_executor(
108:                    None,
109:                    lambda: self.model.encode(embed_texts, batch_size=min(64, len(embed_texts)), show_progress_bar=False),
110:                )
111:                vectors_list = [v.tolist() for v in vectors_np]
112:            except Exception as e:
113:                logger.exception("Batched embedding encode failed: %s", e)
   Explanation: If model is loaded, encode texts in a thread pool to avoid blocking the event loop, convert numpy arrays to lists.

114:        if vectors_list is not None and self.qdrant_client is not None:
115:            try:
116:                from qdrant_client.models import PointStruct
117:                points = [
118:                    PointStruct(id=eid, vector=vec, payload=pl)
119:                    for eid, vec, pl in zip(embedding_ids, vectors_list, payloads)
120:                ]
121:                self.qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
122:            except Exception as e:
123:                logger.exception("Qdrant batch upsert failed: %s", e)
   Explanation: If Qdrant is available, upsert vector points (id, vector, payload) in batch.

124:        now_utc = datetime.utcnow()
125:        job_updates = []
126:        event_inserts = []

127:        for job_id, embedding_id in zip(job_ids, embedding_ids):
128:            set_doc = {
129:                "embedding_id": embedding_id,
130:                "embedding_model": EMBEDDING_MODEL,
131:                "status": "published",
132:                "updated_at": now_utc,
133:            }
134:            job_updates.append({"filter": {"_id": job_id}, "update": {"$set": set_doc}})
135:            event_inserts.append({
136:                "_id": str(uuid.uuid4()),
137:                "job_id": job_id,
138:                "event_type": "job.embedded",
139:                "agent_name": "embedder",
140:                "status": "success",
141:                "payload": {"embedding_id": embedding_id, "model": EMBEDDING_MODEL},
142:                "duration_ms": 0,
143:                "created_at": now_utc,
144:            })
   Explanation: Build MongoDB update operations and pipeline event documents for each job.

145:        client = get_mongo_client()
146:        db = client["jobplatform"]

147:        try:
148:            from pymongo import UpdateOne, InsertOne
149:            bulk_ops = [UpdateOne(**u) for u in job_updates]
150:            if bulk_ops:
151:                await db.jobs.bulk_write(bulk_ops, ordered=False)
152:        except Exception as e:
153:            logger.warning("Embedder bulk_write jobs failed (%s), falling back per-job", e)
154:            sem = asyncio.Semaphore(CONCURRENT_DB_WRITES)

155:            async def _update_one(job_id: str, embedding_id: str) -> None:
156:                async with sem:
157:                    try:
158:                        await db.jobs.update_one(
159:                            {"_id": job_id},
160:                            {"$set": {
161:                                "embedding_id": embedding_id,
162:                                "embedding_model": EMBEDDING_MODEL,
163:                                "status": "published",
164:                                "updated_at": now_utc,
165:                            }},
166:                        )
167:                    except Exception:
168:                        pass

169:            await asyncio.gather(*[
170:                asyncio.create_task(_update_one(jid, eid))
171:                for jid, eid in zip(job_ids, embedding_ids)
172:            ])
   Explanation: Attempt bulk_write; on failure, fall back to concurrent per-job updates with a semaphore to limit DB concurrency.

173:        try:
174:            from pymongo import InsertOne
175:            bulk_events = [InsertOne(e) for e in event_inserts]
176:            if bulk_events:
177:                await db.pipeline_events.bulk_write(bulk_events, ordered=False)
178:        except Exception as e:
179:            logger.warning("Embedder bulk_write events failed: %s", e)
   Explanation: Insert pipeline events in bulk; warn on failure.

180:        elapsed_ms = (time.monotonic() - start) * 1000
181:        jps = (len(job_ids) / elapsed_ms * 1000) if elapsed_ms > 0 else 0
182:        logger.info(
183:            "🧬 Embedder: %d jobs, vectors=%s, qdrant=%s in %.0fms (%.1f j/s)",
184:            len(job_ids),
185:            "yes" if vectors_list is not None else "no",
186:            "yes" if vectors_list is not None and self.qdrant_client is not None else "no",
187:            elapsed_ms, jps,
188:        )
   Explanation: Log throughput and whether embedding/Qdrant indexing occurred.

189: async def main() -> None:
190:     logging.basicConfig(level=logging.INFO)
191:     service = EmbedderService()
192:     try:
193:         await service.start()
194:     except KeyboardInterrupt:
195:         await service.stop()

196: if __name__ == "__main__":
197:     asyncio.run(main())
