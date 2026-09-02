# Per-line annotated: services/deduplicator/main.py

This document contains a per-line (grouped) annotated copy of `services/deduplicator/main.py`.

---

1: """
2: Deduplicator Service — Duplicate Detection Agent.
3: Consumes from Kafka topic: job.cleaned
4: Publishes to Kafka topic: job.deduplicated
5: """
   Explanation: Module docstring describing service inputs and outputs.

6: from __future__ import annotations
   Explanation: Postponed annotations for forward references.

7: import asyncio
8: import hashlib
9: import logging
10: import time
11: import uuid
12: from datetime import datetime
13: from typing import Any
   Explanation: Standard imports for async, hashing, logging, timing, and typing.

14: from shared.kafka.consumer import KafkaConsumerClient
15: from shared.kafka.producer import KafkaProducerClient
16: from shared.kafka.topics import TOPICS
17: from shared.database.session import get_mongo_client
   Explanation: Kafka clients and MongoDB client helper.

18: logger = logging.getLogger(__name__)
   Explanation: Module logger.

19: def generate_fingerprint(title: str, company: str, location: str | None) -> str:
20:     """Generate a content-based fingerprint for similarity matching."""
21:     normalized = f"{title.lower().strip()}|{company.lower().strip()}|{(location or '').lower().strip()}"
22:     return hashlib.sha256(normalized.encode()).hexdigest()
   Explanation: Deterministic SHA-256 fingerprint from title|company|location to detect near-duplicates.

23: class DeduplicatorService:
24:     """
25:     Duplicate Detection Agent — HIGH-THROUGHPUT BATCH MODE.
26:
27:     Optimizations:
28:     - Batch consumption from job.cleaned (100+ msgs)
29:     - Bulk content-fingerprint + source_job_id dedup using ONE $in query
30:       (N DB round-trips → 3 total DB calls per batch)
31:     - MongoDB bulk_write for updates
32:     - Kafka send_batch for job.deduplicated
33:     """
   Explanation: Class docstring describing approach and optimizations.

34:     DEFAULT_BATCH_SIZE = int(__import__("os").getenv("DEDUP_BATCH_SIZE", "200"))
35:     CONCURRENT_TASKS = int(__import__("os").getenv("DEDUP_WORKERS", "40"))
   Explanation: Batch size and concurrency configurable via env.

36:     def __init__(self) -> None:
37:         self.producer = KafkaProducerClient()
38:         self.consumer = KafkaConsumerClient(
39:             topics=[TOPICS.JOB_CLEANED],
40:             group_id="deduplicator-service",
41:             max_poll_records=max(400, self.DEFAULT_BATCH_SIZE * 2),
42:         )
43:         self.running = False
44:         self._sem = asyncio.Semaphore(self.CONCURRENT_TASKS)
   Explanation: Initialize Kafka clients, running flag and semaphore.

45:     async def start(self) -> None:
46:         await self.producer.start()
47:         await self.consumer.start()
48:         self.running = True
49:         logger.info(
50:             f"🔍 Deduplicator service started (batch={self.DEFAULT_BATCH_SIZE}, "
51:             f"workers={self.CONCURRENT_TASKS})"
52:         )
53:         await self.consumer.consume_batch(
54:             self._handle_batch,
55:             batch_size=self.DEFAULT_BATCH_SIZE,
56:             timeout_ms=2000,
57:         )
   Explanation: Start producer/consumer and begin consuming batches with `_handle_batch`.

58:     async def stop(self) -> None:
59:         self.running = False
60:         await self.producer.stop()
61:         await self.consumer.stop()
   Explanation: Graceful stop logic.

62:     async def _handle_batch(self, messages: list[dict]) -> None:
63:         t0 = time.monotonic()
64:         if not messages:
65:             return
   Explanation: Measure start time and handle empty batches.

66:         client = get_mongo_client()
67:         db = client["jobplatform"]
   Explanation: Acquire Motor client and database reference.

68:         # Step 1: Pre-compute fingerprints for all messages
69:         prepared: list[dict] = []
70:         for msg in messages:
71:             job_id = msg.get("_id") or msg.get("id") or str(uuid.uuid4())
72:             fp = generate_fingerprint(
73:                 msg.get("title", ""),
74:                 msg.get("company_name", ""),
75:                 msg.get("location_city"),
76:             )
77:             prepared.append({
78:                 "job_id": job_id,
79:                 "source": msg.get("source", ""),
80:                 "source_job_id": msg.get("source_job_id", ""),
81:                 "fingerprint": fp,
82:                 "msg": msg,
83:             })
   Explanation: For each message compute fingerprint and collect metadata for bulk queries.

84:         # Step 2: ONE DB query for all exact source+source_job_id matches
85:         source_pairs: list[tuple[str, str]] = [
86:             (p["source"], p["source_job_id"]) for p in prepared
87:             if p["source"] and p["source_job_id"]
88:         ]
89:         exact_duplicates: dict[str, str] = {}
90:         if source_pairs:
91:             or_clauses = [
92:                 {"source": s, "source_job_id": sjid}
93:                 for (s, sjid) in source_pairs
94:             ]
95:             cursor = db.jobs.find(
96:                 {"$or": or_clauses},
97:                 {"_id": 1, "source": 1, "source_job_id": 1},
98:             )
99:             async for existing in cursor:
100:                key = f"{existing['source']}|{existing['source_job_id']}"
101:                exact_duplicates[key] = str(existing["_id"])
   Explanation: Bulk query existing jobs by source+source_job_id to detect exact duplicates.

102:        # Step 3: ONE DB query for all fingerprint near-duplicates
103:        fps = [p["fingerprint"] for p in prepared]
104:        near_duplicates: dict[str, str] = {}
105:        if fps:
106:            cursor = db.jobs.find(
107:                {"content_fingerprint": {"$in": fps}},
108:                {"_id": 1, "content_fingerprint": 1},
109:            )
110:            async for existing in cursor:
111:                near_duplicates[existing["content_fingerprint"]] = str(existing["_id"])
   Explanation: Query for matching content fingerprints to find near-duplicates.

112:        # Step 4: Classify each job (exact → near → unique) and mark dedup within-batch
113:        seen_in_batch_source_keys: set[str] = set()
114:        seen_in_batch_fps: set[str] = set()
115:        unique_messages: list[tuple[dict, str]] = []
116:        update_ops: list = []
117:        event_inserts: list = []

118:        try:
119:            from pymongo import UpdateOne, InsertOne
120:        except ImportError:
121:            UpdateOne = InsertOne = None

122:        for p in prepared:
123:            jid = p["job_id"]
124:            msg = dict(p["msg"])
125:            msg["_id"] = jid

126:            is_dup = False
127:            dup_of = None
128:            exact_key = f"{p['source']}|{p['source_job_id']}"

129:            if exact_key in exact_duplicates:
130:                is_dup = True
131:                dup_of = exact_duplicates[exact_key]
132:            elif exact_key in seen_in_batch_source_keys:
133:                is_dup = True
134:                dup_of = "batch_internal"
135:            else:
136:                fp = p["fingerprint"]
137:                if fp in near_duplicates:
138:                    is_dup = True
139:                    dup_of = near_duplicates[fp]
140:                elif fp in seen_in_batch_fps:
141:                    is_dup = True
142:                    dup_of = "batch_internal_fingerprint"
143:                else:
144:                    msg["content_fingerprint"] = fp
145:                    seen_in_batch_fps.add(fp)

146:            seen_in_batch_source_keys.add(exact_key)

147:            msg["is_duplicate"] = is_dup
148:            msg["duplicate_of_id"] = dup_of
149:            msg["status"] = "deduplicated" if not is_dup else "duplicate"
150:            msg.setdefault("updated_at", datetime.utcnow())

151:            if UpdateOne is not None:
152:                update_ops.append(UpdateOne({"_id": jid}, {"$set": msg}, upsert=True))
153:            else:
154:                await db.jobs.update_one({"_id": jid}, {"$set": msg}, upsert=True)

155:            if InsertOne is not None:
156:                event_inserts.append(InsertOne({
157:                    "_id": str(uuid.uuid4()),
158:                    "job_id": jid,
159:                    "event_type": "job.deduplicated",
160:                    "agent_name": "deduplicator",
161:                    "status": "duplicate" if is_dup else "unique",
162:                    "payload": {"duplicate_of": dup_of} if is_dup else {},
163:                    "duration_ms": 0.0,
164:                    "created_at": datetime.utcnow(),
165:                }))

156:            if not is_dup:
157:                unique_messages.append((msg, jid))
   Explanation: Classify and annotate each message, prepare UpdateOne and InsertOne ops and collect unique items to publish.

158:        # Step 5: Bulk upsert jobs + bulk insert events
159:        if update_ops:
160:            try:
161:                await db.jobs.bulk_write(update_ops, ordered=False)
162:            except Exception as e:
163:                logger.warning(f"Dedup bulk_write jobs failed: {e}")
164:        if event_inserts:
165:            try:
166:                await db.pipeline_events.bulk_write(event_inserts, ordered=False)
167:            except Exception:
168:                pass
   Explanation: Execute bulk DB operations with basic error handling.

169:        # Step 6: Batch publish unique jobs downstream
170:        published = 0
171:        if unique_messages:
172:            published = await self.producer.send_batch(TOPICS.JOB_DEDUPLICATED, unique_messages)

173:        elapsed = time.monotonic() - t0
174:        total = len(messages)
175:        duplicates = total - len(unique_messages)
176:        logger.info(
177:            f"🔍 Dedup batch: {total} in → {published} unique, {duplicates} dupes "
178:            f"in {elapsed*1000:.0f}ms ({total/max(0.001, elapsed):.0f} j/s)"
179:        )
   Explanation: Publish unique messages and log batch metrics.

180: async def main() -> None:
181:     logging.basicConfig(level=logging.INFO)
182:     service = DeduplicatorService()
183:     try:
184:         await service.start()
185:     except KeyboardInterrupt:
186:         await service.stop()

187: if __name__ == "__main__":
188:     asyncio.run(main())
