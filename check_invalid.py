from database.postgres_client import PostgresClient

p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("SELECT title, validation_reasons FROM job_segments WHERE is_validated = FALSE")
    for row in cur.fetchall():
        print(row)
p.close()
