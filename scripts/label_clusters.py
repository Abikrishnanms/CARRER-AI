"""
scripts/label_clusters.py

Auto-generates human-readable labels for each cluster based on
the most common words in job titles within that cluster.
"""

import re
from collections import Counter, defaultdict
from database.postgres_client import PostgresClient

STOPWORDS = {"and", "the", "for", "with", "in", "of", "to", "a", "at", "on", "is", "are"}

def extract_label(titles: list) -> str:
    words = []
    for t in titles:
        cleaned = re.sub(r"[^a-zA-Z\s]", "", t.lower())
        words.extend(w for w in cleaned.split() if w not in STOPWORDS and len(w) > 2)
    common = Counter(words).most_common(3)
    return " ".join(w.title() for w, _ in common) if common else "Unlabeled"


p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("""
        SELECT segment_id, title FROM job_segments
        WHERE segment_id != -1
    """)
    rows = cur.fetchall()

groups = defaultdict(list)
for segment_id, title in rows:
    if title:
        groups[segment_id].append(title)

for segment_id, titles in groups.items():
    label = extract_label(titles)
    with p.conn.cursor() as cur:
        cur.execute("""
            UPDATE job_segments SET segment_label = %s WHERE segment_id = %s
        """, (label, segment_id))
    print(f"cluster_{segment_id} -> {label} ({len(titles)} jobs)")

p.close()
print("Done labeling clusters.")