import psycopg2
import os

conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode="require")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS reputation_points (member_id INTEGER PRIMARY KEY, points INTEGER);")
cursor.execute("INSERT INTO reputation_points (member_id, points) VALUES (%s, %s)", (1283619726397126731, 1))
conn.commit()