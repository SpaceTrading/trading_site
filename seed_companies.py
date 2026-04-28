import sqlite3
from datetime import datetime

conn = sqlite3.connect("market.db")
cur = conn.cursor()

companies = [
    ("Apple", "AAPL", "Tech"),
    ("Microsoft", "MSFT", "Tech"),
    ("Google", "GOOGL", "Tech"),
    ("Amazon", "AMZN", "ConsumerDiscretionary"),
    ("Tesla", "TSLA", "ConsumerDiscretionary"),
    ("JPMorgan", "JPM", "Finance"),
    ("Goldman Sachs", "GS", "Finance"),
    ("BlackRock", "BLK", "Finance"),
    ("Pfizer", "PFE", "Healthcare"),
    ("Johnson & Johnson", "JNJ", "Healthcare")
]

for name, ticker, sector in companies:
    cur.execute("""
        INSERT OR IGNORE INTO companies (name, ticker, sector, last_updated)
        VALUES (?, ?, ?, ?)
    """, (name, ticker, sector, datetime.now()))

conn.commit()
conn.close()