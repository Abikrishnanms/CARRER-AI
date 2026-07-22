"""
Session 4: RabbitMQ Queue Names and Routing Keys.
Centralized constants to avoid typos across the system.
"""

# ===== Main Queues =====
RAW_JOBS_QUEUE = "raw_jobs"           # Freshly scraped jobs go here
CLEANED_JOBS_QUEUE = "cleaned_jobs"   # Jobs that passed the preprocessor
FEATURED_JOBS_QUEUE = "featured_jobs" # Jobs with ML features extracted

# ===== Dead Letter Queues (For errors) =====
DLQ_ERRORS = "dlq_errors"             # Jobs that failed 3 times

# ===== Exchange (For routing) =====
EXCHANGE_NAME = "careerai"
EXCHANGE_TYPE = "direct"

# ===== Routing Keys =====
ROUTING_KEYS = {
    "raw": "job.raw",
    "cleaned": "job.cleaned",
    "featured": "job.featured",
    "error": "job.error",
}