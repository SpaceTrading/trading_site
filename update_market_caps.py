from app import app, db
from app import Company, MarketCapHistory
from datetime import datetime
import yfinance as yf
import pandas as pd

# =========================
# CONFIG
# =========================
BATCH_SIZE = 20

# =========================
# UPDATE
# =========================
with app.app_context():

    companies = Company.query.filter(Company.ticker.isnot(None)).all()
    company_map = {c.ticker: c for c in companies}

    tickers = [c.ticker for c in companies if c.ticker]

    print(f"Totale ticker: {len(tickers)}")

    updated = 0
    skipped = 0

    # batch download
    for i in range(0, len(tickers), BATCH_SIZE):

        batch = tickers[i:i+BATCH_SIZE]

        try:
            data = yf.download(
                batch,
                period="1d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True
            )

        except Exception as e:
            print(f" Batch error: {e}")
            continue

        for ticker in batch:

            try:
                company_map = {c.ticker: c for c in companies}
                company = company_map.get(ticker)
                if not company:
                    continue

                # fallback struttura dati
                if len(batch) == 1:
                    close = data["Close"].iloc[-1]
                else:
                    close = data[ticker]["Close"].iloc[-1]

                if pd.isna(close):
                    print(f"{ticker} → no price")
                    skipped += 1
                    continue

                # fallback market cap proxy (price * shares outstanding)
                stock = yf.Ticker(ticker)
                shares = stock.fast_info.get("shares")

                if not shares:
                    print(f"{ticker} → no shares")
                    skipped += 1
                    continue

                market_cap = (close * shares) / 1_000_000_000  # billions

                # update DB
                company.market_cap = float(market_cap)
                company.last_updated = datetime.utcnow()
                
                db.session.add(
                    MarketCapHistory(
                        company_id=company.id,
                        market_cap=company.market_cap,
                        timestamp=datetime.utcnow()
                    )
                )                

                updated += 1

                print(f"{ticker} → {round(market_cap,2)}B")

            except Exception as e:
                print(f"Errore {ticker}: {e}")
                skipped += 1

    db.session.commit()

    print("\n UPDATE COMPLETATO")
    print(f" aggiornati: {updated}")
    print(f" skipped: {skipped}")