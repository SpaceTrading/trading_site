import sqlite3

conn = sqlite3.connect("market.db")
cur = conn.cursor()

cur.execute("SELECT name, ticker, sector FROM companies")
rows = cur.fetchall()

for row in rows:
    print(row)

conn.close()