"""Kafka topic definitions — single source of truth for all topic names.

Capacity-optimized configs:
- job.raw: 32 partitions (was 10) — high write throughput
- job.cleaned/deduplicated/enriched: 16 partitions each
- job.verified: 8 partitions (final stage, lower volume after dedup)
- notification.*: 8 partitions
- user.event/search.query: 16 partitions for analytics
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class KafkaTopics:
    # ─── Job Pipeline ──────────────────────────────────────────────────────────
    JOB_RAW = "job.raw"
    JOB_CLEANED = "job.cleaned"
    JOB_DEDUPLICATED = "job.deduplicated"
    JOB_ENRICHED = "job.enriched"
    JOB_VERIFIED = "job.verified"
    JOB_REJECTED = "job.rejected"
    JOB_EXPIRED = "job.expired"

    # ─── Dead Letter Queues ────────────────────────────────────────────────────
    JOB_RAW_DLQ = "job.raw.dlq"
    JOB_CLEANED_DLQ = "job.cleaned.dlq"
    JOB_ENRICHED_DLQ = "job.enriched.dlq"

    # ─── Notifications ─────────────────────────────────────────────────────────
    NOTIFICATION_EMAIL = "notification.email"
    NOTIFICATION_TELEGRAM = "notification.telegram"
    NOTIFICATION_WHATSAPP = "notification.whatsapp"
    NOTIFICATION_WEBHOOK = "notification.webhook"
    NOTIFICATION_IN_APP = "notification.in_app"

    # ─── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_JOB = "embedding.job"
    EMBEDDING_USER = "embedding.user"
    EMBEDDING_COMPLETE = "embedding.complete"

    # ─── Analytics & Events ───────────────────────────────────────────────────
    USER_EVENT = "user.event"
    SEARCH_QUERY = "search.query"
    FEEDBACK_RECEIVED = "feedback.received"

    # ─── Agent Commands ────────────────────────────────────────────────────────
    COLLECTION_TRIGGER = "collection.trigger"
    VERIFICATION_REQUEST = "verification.request"
    ENRICHMENT_REQUEST = "enrichment.request"


TOPICS = KafkaTopics()

# Topic configurations for Redpanda/Kafka admin (production-grade sizing)
TOPIC_CONFIGS = {
    TOPICS.JOB_RAW: {
        "num_partitions": int(__import__("os").getenv("KAFKA_PARTITIONS_RAW", "32")),
        "replication_factor": 1,            # Single-node dev; raise to 3 in prod
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "cleanup_policy": "delete",
        "segment_bytes": 1024 * 1024 * 256,  # 256MB segments for fast compaction
    },
    TOPICS.JOB_CLEANED: {
        "num_partitions": int(__import__("os").getenv("KAFKA_PARTITIONS_CLEANED", "16")),
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "segment_bytes": 1024 * 1024 * 256,
    },
    TOPICS.JOB_DEDUPLICATED: {
        "num_partitions": int(__import__("os").getenv("KAFKA_PARTITIONS_DEDUP", "16")),
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
    },
    TOPICS.JOB_ENRICHED: {
        "num_partitions": int(__import__("os").getenv("KAFKA_PARTITIONS_ENRICHED", "16")),
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
    },
    TOPICS.JOB_VERIFIED: {
        "num_partitions": int(__import__("os").getenv("KAFKA_PARTITIONS_VERIFIED", "8")),
        "replication_factor": 1,
        "retention_ms": 30 * 24 * 60 * 60 * 1000,
    },
    TOPICS.JOB_REJECTED: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 14 * 24 * 60 * 60 * 1000,
    },
    TOPICS.NOTIFICATION_EMAIL: {
        "num_partitions": 8,
        "replication_factor": 1,
        "retention_ms": 24 * 60 * 60 * 1000,
    },
    TOPICS.NOTIFICATION_TELEGRAM: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 24 * 60 * 60 * 1000,
    },
    TOPICS.NOTIFICATION_WHATSAPP: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 24 * 60 * 60 * 1000,
    },
    TOPICS.NOTIFICATION_IN_APP: {
        "num_partitions": 8,
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
    },
    TOPICS.USER_EVENT: {
        "num_partitions": 16,
        "replication_factor": 1,
        "retention_ms": 90 * 24 * 60 * 60 * 1000,
    },
    TOPICS.SEARCH_QUERY: {
        "num_partitions": 16,
        "replication_factor": 1,
        "retention_ms": 90 * 24 * 60 * 60 * 1000,
    },
    TOPICS.FEEDBACK_RECEIVED: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 365 * 24 * 60 * 60 * 1000,
    },
    TOPICS.EMBEDDING_JOB: {
        "num_partitions": 16,
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
    },
    TOPICS.EMBEDDING_USER: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 30 * 24 * 60 * 60 * 1000,
    },
    TOPICS.COLLECTION_TRIGGER: {
        "num_partitions": 4,
        "replication_factor": 1,
        "retention_ms": 24 * 60 * 60 * 1000,
    },
    # DLQs
    TOPICS.JOB_RAW_DLQ: {"num_partitions": 4, "replication_factor": 1, "retention_ms": 30 * 24 * 60 * 60 * 1000},
    TOPICS.JOB_CLEANED_DLQ: {"num_partitions": 4, "replication_factor": 1, "retention_ms": 30 * 24 * 60 * 60 * 1000},
    TOPICS.JOB_ENRICHED_DLQ: {"num_partitions": 4, "replication_factor": 1, "retention_ms": 30 * 24 * 60 * 60 * 1000},
}
