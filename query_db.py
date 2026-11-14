import sys
import pymysql

try:
    conn = pymysql.connect(
        host="127.0.0.1", port=3306, user="swarm", password="change-me", database="swarm",
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM clusters LIMIT 1")
        print(cur.fetchone())
except Exception as e:
    print("Error:", e)
