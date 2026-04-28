import sqlite3
import requests
from datetime import datetime

API_KEY = "INSERISCI_LA_TUA_API_KEY_QUI"

conn = sqlite3.connect("market.db")
cur = conn.cursor()

cur.execute("SELECT id, ticker FROM companies")
companies = cur.fetchall()

for company_id, ticker in companies:

    url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={API_KEY}"

    try:
        res = requests.get(url).json()

        if not res:
            print(f"{ticker} → nessun dato")
            continue

        market_cap = res[0]["mktCap"] / 1_000_000_000  # in BILLIONS

        # UPDATE companies
        cur.execute("""
            UPDATE companies
            SET market_cap = ?, last_updated = ?
            WHERE id = ?
        """, (market_cap, datetime.now(), company_id))

        # INSERT storico
        cur.execute("""
            INSERT INTO market_cap_history (company_id, market_cap)
            VALUES (?, ?)
        """, (company_id, market_cap))

        print(f"{ticker} aggiornato → {round(market_cap,2)}B")

    except Exception as e:
        print(f"Errore {ticker}: {e}")

conn.commit()
conn.close()