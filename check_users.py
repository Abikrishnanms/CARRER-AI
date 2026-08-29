# check_users.py
from database.postgres_client import PostgresClient

p = PostgresClient()
with p.conn.cursor() as cur:
    cur.execute("SELECT id, username, email, full_name, location, created_at FROM users")
    for row in cur.fetchall():
        print(row)