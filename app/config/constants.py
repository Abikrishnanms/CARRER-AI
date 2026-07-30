"""
Application Constants
"""

# ==============================
# Job Statuses
# ==============================
JOB_STATUS_NEW = "New"
JOB_STATUS_ACTIVE = "Active"
JOB_STATUS_CLOSING = "Closing"
JOB_STATUS_CLOSED = "Closed"

JOB_STATUSES = [
    JOB_STATUS_NEW,
    JOB_STATUS_ACTIVE,
    JOB_STATUS_CLOSING,
    JOB_STATUS_CLOSED,
]

# ==============================
# Experience Levels
# ==============================
EXPERIENCE_ENTRY = "Entry"
EXPERIENCE_MID = "Mid"
EXPERIENCE_SENIOR = "Senior"

EXPERIENCE_LEVELS = [
    EXPERIENCE_ENTRY,
    EXPERIENCE_MID,
    EXPERIENCE_SENIOR,
]

# ==============================
# Domains
# ==============================
DOMAIN_IT = "IT"
DOMAIN_FINANCE = "Finance"
DOMAIN_HEALTHCARE = "Healthcare"
DOMAIN_MANUFACTURING = "Manufacturing"
DOMAIN_OTHER = "Other"

DOMAINS = [
    DOMAIN_IT,
    DOMAIN_FINANCE,
    DOMAIN_HEALTHCARE,
    DOMAIN_MANUFACTURING,
    DOMAIN_OTHER,
]

# ==============================
# Job Types
# ==============================
JOB_TYPE_FULLTIME = "Full-time"
JOB_TYPE_PARTTIME = "Part-time"
JOB_TYPE_CONTRACT = "Contract"
JOB_TYPE_INTERNSHIP = "Internship"

JOB_TYPES = [
    JOB_TYPE_FULLTIME,
    JOB_TYPE_PARTTIME,
    JOB_TYPE_CONTRACT,
    JOB_TYPE_INTERNSHIP,
]

# ==============================
# Messages
# ==============================
ERROR_REQUIRED_FIELD = "Required field missing: {field}"
ERROR_INVALID_URL = "Invalid URL format"
ERROR_FETCH_FAILED = "Failed to fetch URL"
ERROR_PARSE_FAILED = "Failed to parse HTML"

SUCCESS_JOBS_SCRAPED = "Successfully scraped {count} jobs"
SUCCESS_DATA_VALIDATED = "Data validation successful"
SUCCESS_DATA_SAVED = "Successfully saved {count} jobs"