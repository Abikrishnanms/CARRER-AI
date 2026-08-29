from database.postgres_client import PostgresClient

p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("ALTER TABLE job_segments ADD COLUMN IF NOT EXISTS is_validated BOOLEAN DEFAULT TRUE")
    cur.execute("ALTER TABLE job_segments ADD COLUMN IF NOT EXISTS validation_reasons TEXT")
print("Columns added")
p.close()