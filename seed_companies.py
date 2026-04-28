from app import app, db
from app import Company
from datetime import datetime, UTC

companies = [
    ("Apple", "AAPL", "Tech"),
    ("Microsoft", "MSFT", "Tech"),
    ("Google", "GOOGL", "Tech"),
    ("Amazon", "AMZN", "ConsumerDiscretionary"),
    ("Tesla", "TSLA", "ConsumerDiscretionary"),
    ("JPMorgan", "JPM", "Finance"),
    ("Vanguard", "VANGUARD", "Finance"),
    ("Goldman Sachs", "GS", "Finance"),
    ("BlackRock", "BLK", "Finance"),
    ("Pfizer", "PFE", "Healthcare"),
    ("Johnson & Johnson", "JNJ", "Healthcare"),
]

with app.app_context():
    for name, ticker, sector in companies:
        name = name.strip()
        ticker = ticker.upper().strip()
        sector = sector.strip()

        company = Company.query.filter_by(ticker=ticker).first()

        if company:
            company.name = name
            company.sector = sector
            company.last_updated = datetime.now(UTC)
        else:
            db.session.add(
                Company(
                    name=name,
                    ticker=ticker,
                    sector=sector,
                    market_cap=1,
                    last_updated=datetime.now(UTC),
                )
            )

    db.session.commit()

print("Seed companies aggiornato")