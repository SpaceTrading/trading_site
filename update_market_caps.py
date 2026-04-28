from app import app, db
from app import Company, MarketCapHistory
from datetime import datetime, UTC
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
            print(f"Batch error: {e}")
            continue

        for ticker in batch:

            try:
                company = company_map.get(ticker)
                if not company:
                    continue

                # =========================
                # GET PRICE
                # =========================
                if len(batch) == 1:
                    close = data["Close"].iloc[-1]
                else:
                    close = data[ticker]["Close"].iloc[-1]

                if pd.isna(close):
                    print(f"{ticker} → no price")
                    skipped += 1
                    continue

                # =========================
                # GET SHARES (fallback)
                # =========================
                try:
                    stock = yf.Ticker(ticker)
                    shares = stock.fast_info.get("shares")
                except Exception:
                    shares = None

                if not shares:
                    print(f"{ticker} → no shares")
                    skipped += 1
                    continue

                # =========================
                # CALC MARKET CAP
                # =========================
                market_cap = (close * shares) / 1_000_000_000

                # =========================
                # UPDATE DB
                # =========================
                now = datetime.now(UTC)

                company.market_cap = float(market_cap)
                company.last_updated = now

                db.session.add(
                    MarketCapHistory(
                        company_id=company.id,
                        market_cap=company.market_cap,
                        timestamp=now
                    )
                )

                updated += 1

                print(f"{ticker} → {round(market_cap,2)}B")

            except Exception as e:
                print(f"Errore {ticker}: {e}")
                skipped += 1

    db.session.commit()

    print("\nUPDATE COMPLETATO")
    print(f"aggiornati: {updated}")
    print(f"skipped: {skipped}")