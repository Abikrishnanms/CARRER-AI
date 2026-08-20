# Per-line annotated: services/collector/main.py

This file contains the original source lines from `services/collector/main.py` followed by a concise explanation for each line or small group of lines.

---

1: """
2: Collector Service — Orchestrates all job collection activities.
3:
4: High-throughput improvements:
5: - Runs ALL collectors CONCURRENTLY via asyncio.gather (not serial for-loop)
6: - Publishes jobs using producer.send_batch() instead of one-at-a-time
7: - Scheduled interval shortened to every 90 minutes (4x more frequent)
8: - Default limit raised to 5,000 per run (was 1,000)
9: - Each collector's limit is proportional to source strength (scaled per source)
10: """
   Explanation: Module docstring describing purpose and performance notes.

11: from __future__ import annotations
   Explanation: Enable postponed evaluation of annotations for forward refs.

12: import asyncio
   Explanation: Async concurrency primitives used across the service.
13: import logging
   Explanation: Logging for info/debug messages.
14: import os
   Explanation: Environment access for configuration.
15: from datetime import datetime
   Explanation: Timestamps for summaries and events.

16: from shared.kafka.consumer import KafkaConsumerClient
   Explanation: Async Kafka consumer wrapper used to receive triggers.
17: from shared.kafka.producer import KafkaProducerClient
   Explanation: Async Kafka producer wrapper used to publish job batches.
18: from shared.kafka.topics import TOPICS
   Explanation: Centralized Kafka topic names.
19: from shared.models.job import CollectionSource
   Explanation: Enum for collection source identifiers.
20: from shared.utils.logging import setup_logging
   Explanation: Project logging setup helper (not shown here but used in main()).
21: from services.collector.agents import (
22:     COLLECTOR_REGISTRY,
23:     get_collector,
24:     get_all_sources,
25:     DEFAULT_SEARCH_TERMS,
26: )
   Explanation: Import collector registry and helper functions from agents module.

27: logger = logging.getLogger(__name__)
   Explanation: Module-level logger.

28: # ─── Per-source scaling weights (proportion of total limit) ──────────────────
29: SOURCE_WEIGHTS: dict[str, float] = {
30:     CollectionSource.ADZUNA: 0.15,
31:     CollectionSource.GREENHOUSE: 0.12,
32:     CollectionSource.LEVER: 0.10,
33:     CollectionSource.WORKDAY: 0.05,
34:     CollectionSource.INDEED: 0.08,
35:     CollectionSource.NAUKRI: 0.15,
36:     CollectionSource.LINKEDIN: 0.12,
37:     CollectionSource.RSS: 0.10,
38:     CollectionSource.GOVERNMENT: 0.03,
39:     CollectionSource.COMPANY_CAREERS: 0.10,
40: }
   Explanation: Weights used to split a total collection limit across sources.

41: def _scale_limits(total_limit: int, sources: list[str]) -> dict[str, int]:
42:     """Distribute total limit across sources using proportional weights."""
43:     active_weights = {s: SOURCE_WEIGHTS.get(s, 1.0 / max(1, len(sources))) for s in sources}
44:     total_w = sum(active_weights.values())
45:     normalized = {s: w / total_w for s, w in active_weights.items()}
46:     # First pass: floor allocation
47:     allocated = {s: max(5, int(total_limit * w)) for s, w in normalized.items()}
48:     used = sum(allocated.values())
49:     leftover = total_limit - used
50:     # Distribute leftover proportionally
51:     if leftover > 0:
52:         ordered = sorted(allocated.keys(), key=lambda s: normalized[s], reverse=True)
53:         for s in ordered:
54:             add = min(leftover, max(1, int(leftover * normalized[s])))
55:             allocated[s] += add
56:             leftover -= add
57:             if leftover <= 0:
58:                 break
59:     return allocated
   Explanation: Compute integer per-source limits ensuring minimum allocation and distributing any leftover.

60: class CollectorService:
61:     """
62:     Master collection orchestrator — runs collectors concurrently
63:     and publishes results in big Kafka batches.
64:     """
   Explanation: Orchestrator class for running collectors and publishing raw jobs.

65:     def __init__(self) -> None:
66:         self.producer = KafkaProducerClient()
67:         self.consumer = KafkaConsumerClient(topics=[TOPICS.COLLECTION_TRIGGER])
68:         self.running = False
69:         self._collection_lock = asyncio.Lock()
70:         self._last_collection_summary: dict[str, Any] = {}
   Explanation: Initialize producer/consumer, run state, lock and last summary store.

71:     async def start(self) -> None:
72:         await self.producer.start()
73:         await self.consumer.start()
74:         self.running = True
75:         logger.info("🚀 Collector service started (high-throughput mode)")

76:         asyncio.create_task(self._scheduled_collection())
77:         await self.consumer.consume(self._handle_trigger)
   Explanation: Start clients, mark running, spawn scheduled task and begin consuming trigger topic.

78:     async def stop(self) -> None:
79:         self.running = False
80:         await self.producer.stop()
81:         await self.consumer.stop()
   Explanation: Stop method to gracefully shutdown clients.

82:     async def _handle_trigger(self, message: dict, *args) -> None:
83:         """Handle a collection trigger message."""
84:         if self._collection_lock.locked():
85:             logger.warning("Collection already in progress — skipping trigger")
86:             return

87:         sources = message.get("sources") or get_all_sources()
88:         search_terms = message.get("search_terms") or None
89:         location = message.get("location") or None
90:         limit = int(message.get("limit") or os.getenv("COLLECTION_RUN_LIMIT", "5000"))

91:         logger.info(
92:             f"📥 Manual collection triggered: "
93:             f"sources={len(sources)}, terms={len(search_terms or DEFAULT_SEARCH_TERMS)}, limit={limit}"
94:         )
95:         async with self._collection_lock:
96:             self._last_collection_summary = await self._run_collection(
97:                 sources, search_terms, location, limit
98:             )
   Explanation: Extract trigger parameters and run collection under a lock to avoid concurrent runs.

99:     async def _scheduled_collection(self) -> None:
100:         """Run collection on schedule (every 90 minutes by default)."""
101:         interval_min = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "90"))
102:         interval_seconds = interval_min * 60
103:         logger.info(f"⏰ Scheduled collection every {interval_min} minutes")

104:         while self.running:
105:             # Stagger initial start slightly (5 seconds) so services come up
106:             await asyncio.sleep(5 if not self._last_collection_summary else interval_seconds)
107:             if not self.running:
108:                 break

109:             if self._collection_lock.locked():
110:                 logger.info("Previous collection still running — skipping this cycle")
111:                 continue

112:             logger.info(f"⏰ Scheduled collection starting (every {interval_min}m)")
113:             all_sources = get_all_sources()
114:             limit = int(os.getenv("COLLECTION_RUN_LIMIT", "5000"))

115:             async with self._collection_lock:
116:                 summary = await self._run_collection(
117:                     all_sources, None, None, limit
118:                 )
119:                 self._last_collection_summary = summary

120:             total = summary.get("total_published", 0)
121:             logger.info(
122:                 f"✅ Scheduled collection complete: {total} jobs published. "
123:                 f"Next run in {interval_min}m"
124:             )
   Explanation: Scheduler loop sleeps, checks lock, runs collection, logs summary.

125:     async def _run_collection(
126:         self,
127:         sources: list[str],
128:         search_terms: list[str] | None,
129:         location: str | None,
130:         limit: int,
131:     ) -> dict[str, Any]:
132:         """Run ALL sources concurrently, then batch-publish to Kafka."""
133:         t0 = asyncio.get_event_loop().time()
134:         per_source_limits = _scale_limits(limit, sources)

135:         summary: dict[str, Any] = {
136:             "started_at": datetime.utcnow().isoformat(),
137:             "sources_requested": list(sources),
138:             "total_limit": limit,
139:             "per_source_limits": per_source_limits,
140:         }
   Explanation: Prepare timing and per-source limits and initialize summary dict.

141:         async def _run_one(source_name: str) -> tuple[str, list]:
142:             source_limit = per_source_limits.get(source_name, limit // max(1, len(sources)))
143:             try:
144:                 collector = get_collector(source_name)
145:                 logger.info(f"  ▶ Collecting {source_name} (up to {source_limit} jobs)...")
146:                 async with collector:
147:                     jobs = await collector.collect(
148:                         search_terms=search_terms,
149:                         location=location,
150:                         limit=source_limit,
151:                     )
152:                 logger.info(f"  ✔ {source_name}: collected {len(jobs)} jobs")
153:                 return source_name, list(jobs)
154:             except Exception as e:
155:                 logger.exception(f"  ❌ Collection failed for {source_name}: {e}")
156:                 return source_name, []
   Explanation: Task to run a single collector using async context manager and return collected jobs, catching exceptions.

157:         # Run every source concurrently
158:         tasks = [asyncio.create_task(_run_one(s)) for s in sources]
159:         results = await asyncio.gather(*tasks, return_exceptions=False)

160:         source_job_map: dict[str, list] = {s: j for s, j in results}
161:         summary["collected_per_source"] = {s: len(j) for s, j in source_job_map.items()}
162:         total_collected = sum(len(j) for j in source_job_map.values())

163:         logger.info(f"📦 Collected {total_collected} raw jobs across {len(results)} sources")
   Explanation: Run all source tasks concurrently, gather results, compute totals and log.

164:         # ─── Batch publish to Kafka ─────────────────────────────────────────
165:         published_per_source: dict[str, int] = {}
166:         total_published = 0

167:         for source_name, jobs in source_job_map.items():
168:             if not jobs:
169:                 published_per_source[source_name] = 0
170:                 continue

171:             # Build (payload, key) tuples for send_batch
172:             to_send: list[tuple[Any, str]] = []
173:             for job in jobs:
174:                 try:
175:                     payload = job.model_dump(mode="json")
176:                     key = str(job.id)
177:                     to_send.append((payload, key))
178:                 except Exception as e:
179:                     logger.debug(f"Skip serialize {source_name} job: {e}")

180:             if to_send:
181:                 pub_count = await self.producer.send_batch(TOPICS.JOB_RAW, to_send)
182:             else:
183:                 pub_count = 0

184:             published_per_source[source_name] = pub_count
185:             total_published += pub_count
186:             logger.info(f"📨 {source_name}: published {pub_count}/{len(jobs)} to {TOPICS.JOB_RAW}")
   Explanation: Serialize jobs to JSON, create (payload,key) list and publish via producer.send_batch; tally results.

187:         duration_s = asyncio.get_event_loop().time() - t0
188:         summary["published_per_source"] = published_per_source
189:         summary["total_collected"] = total_collected
190:         summary["total_published"] = total_published
191:         summary["duration_seconds"] = round(duration_s, 2)
192:         summary["jobs_per_second"] = round(total_published / max(0.1, duration_s), 1)
193:         summary["finished_at"] = datetime.utcnow().isoformat()

194:         logger.info(
195:             f"🏁 Collection complete: {total_published}/{total_collected} "
196:             f"jobs published to Kafka in {duration_s:.1f}s "
197:             f"({summary['jobs_per_second']} j/s)"
198:         )
199:         return summary
   Explanation: Complete summary stats, compute durations and throughput, and return summary dict.

200: async def main() -> None:
201:     setup_logging()
202:     service = CollectorService()
203:     try:
204:         await service.start()
205:     except KeyboardInterrupt:
206:         await service.stop()


207: if __name__ == "__main__":
208:     asyncio.run(main())
   Explanation: Standard async main runner that initialises logging and starts the service; allows running as script.
