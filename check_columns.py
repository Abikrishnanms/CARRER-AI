from database.postgres_client import PostgresClient

p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'job_segments'")
    print([r[0] for r in cur.fetchall()])
p.close()