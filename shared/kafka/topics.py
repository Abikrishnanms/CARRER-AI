"""Kafka topic definitions — single source of truth for all topic names."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KafkaTopics:
    # ─── Job Pipeline ──────────────────────────────────────────────────────────
    JOB_RAW = "job.raw"                   # Raw jobs from collectors
    JOB_CLEANED = "job.cleaned"           # After DataCleaningAgent
    JOB_DEDUPLICATED = "job.deduplicated" # After DuplicateDetectionAgent
    JOB_ENRICHED = "job.enriched"         # After enrichment agents
    JOB_VERIFIED = "job.verified"         # After verification agents — ready to index
    JOB_REJECTED = "job.rejected"         # Failed verification or scam detected
    JOB_EXPIRED = "job.expired"           # Past expiry date

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
    EMBEDDING_JOB = "embedding.job"         # Request job embedding generation
    EMBEDDING_USER = "embedding.user"       # Request user profile embedding
    EMBEDDING_COMPLETE = "embedding.complete"

    # ─── Analytics & Events ───────────────────────────────────────────────────
    USER_EVENT = "user.event"               # Click, view, apply, save
    SEARCH_QUERY = "search.query"           # Search queries for analytics
    FEEDBACK_RECEIVED = "feedback.received" # User feedback on job classification

    # ─── Agent Commands ────────────────────────────────────────────────────────
    COLLECTION_TRIGGER = "collection.trigger"   # Trigger collection run
    VERIFICATION_REQUEST = "verification.request"
    ENRICHMENT_REQUEST = "enrichment.request"


TOPICS = KafkaTopics()

# Topic configurations for Redpanda/Kafka admin
TOPIC_CONFIGS = {
    TOPICS.JOB_RAW: {
        "num_partitions": 10,
        "replication_factor": 3,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,  # 7 days
    },
    TOPICS.JOB_CLEANED: {
        "num_partitions": 10,
        "replication_factor": 3,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
    },
    TOPICS.JOB_VERIFIED: {
        "num_partitions": 5,
        "replication_factor": 3,
        "retention_ms": 30 * 24 * 60 * 60 * 1000,  # 30 days
    },
    TOPICS.NOTIFICATION_EMAIL: {
        "num_partitions": 5,
        "replication_factor": 3,
        "retention_ms": 24 * 60 * 60 * 1000,  # 24 hours
    },
    TOPICS.USER_EVENT: {
        "num_partitions": 10,
        "replication_factor": 3,
        "retention_ms": 90 * 24 * 60 * 60 * 1000,  # 90 days
    },
}
