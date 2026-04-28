import sqlite3
import yfinance as yf
from datetime import datetime

conn = sqlite3.connect("market.db")
cur = conn.cursor()

cur.execute("SELECT id, ticker FROM companies")
companies = cur.fetchall()

for company_id, ticker in companies:

    try:
        stock = yf.Ticker(ticker)
        market_cap = stock.info.get("marketCap")

        if not market_cap:
            print(f"{ticker} → no data")
            continue

        market_cap = market_cap / 1_000_000_000  # billions

        cur.execute("""
            UPDATE companies
            SET market_cap = ?, last_updated = ?
            WHERE id = ?
        """, (market_cap, datetime.now(), company_id))

        cur.execute("""
            INSERT INTO market_cap_history (company_id, market_cap)
            VALUES (?, ?)
        """, (company_id, market_cap))

        print(f"{ticker} aggiornato → {round(market_cap,2)}B")

    except Exception as e:
        print(f"Errore {ticker}: {e}")

conn.commit()
conn.close()