from database.postgres_client import PostgresClient

p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    print([r[0] for r in cur.fetchall()])
p.close()