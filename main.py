import psycopg2
import os

print('STARTING')
conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode="require")
cursor = conn.cursor()
print(cursor)
cursor.execute("CREATE TABLE IF NOT EXISTS reputation_points (member_id INTEGER PRIMARY KEY, points INTEGER);")
conn.commit()
print('TABLE CREATED')
cursor.execute("INSERT INTO reputation_points (member_id, points) VALUES (%s, %s);", (596743813385682945, 1))
print('ENTRY ADDED')
conn.commit()