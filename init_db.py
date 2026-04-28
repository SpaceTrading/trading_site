import sqlite3

conn = sqlite3.connect("market.db")
cur = conn.cursor()

# TABELLA COMPANIES
cur.execute("""
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    ticker TEXT,
    sector TEXT,
    market_cap REAL,
    last_updated DATETIME
)
""")

# =========================
# OWNERSHIPS TABLE
# =========================
cur.execute("""
CREATE TABLE IF NOT EXISTS ownerships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    target TEXT,
    percentage REAL
)
""")

# TABELLA STORICO
cur.execute("""
CREATE TABLE IF NOT EXISTS market_cap_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    market_cap REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(company_id) REFERENCES companies(id)
)
""")

conn.commit()
conn.close()

print("Database creato")