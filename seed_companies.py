from app import app, db
from app import Company
from datetime import datetime, UTC

companies = [

    # =========================
    # TECH (TOP)
    # =========================
    ("Apple", "AAPL", "Tech"),
    ("Microsoft", "MSFT", "Tech"),
    ("Google", "GOOGL", "Tech"),
    ("Amazon", "AMZN", "Tech"),
    ("NVIDIA", "NVDA", "Tech"),
    ("Meta", "META", "Tech"),
    ("Oracle", "ORCL", "Tech"),
    ("Intel", "INTC", "Tech"),
    ("AMD", "AMD", "Tech"),
    ("Salesforce", "CRM", "Tech"),
    ("Adobe", "ADBE", "Tech"),
    ("Cisco", "CSCO", "Tech"),
    ("IBM", "IBM", "Tech"),
    ("Qualcomm", "QCOM", "Tech"),
    ("Texas Instruments", "TXN", "Tech"),
    ("Broadcom", "AVGO", "Tech"),
    ("SAP", "SAP", "Tech"),
    ("ASML", "ASML", "Tech"),
    ("Sony", "SONY", "Tech"),
    ("Samsung", "SSNLF", "Tech"),

    # =========================
    # FINANCE
    # =========================
    ("JPMorgan", "JPM", "Finance"),
    ("Vanguard", "VANGUARD", "Finance"),
    ("Goldman Sachs", "GS", "Finance"),
    ("BlackRock", "BLK", "Finance"),
    ("Morgan Stanley", "MS", "Finance"),
    ("Bank of America", "BAC", "Finance"),
    ("Citigroup", "C", "Finance"),
    ("Wells Fargo", "WFC", "Finance"),

    # =========================
    # HEALTHCARE
    # =========================
    ("Pfizer", "PFE", "Healthcare"),
    ("Johnson & Johnson", "JNJ", "Healthcare"),
    ("Moderna", "MRNA", "Healthcare"),
    ("Merck", "MRK", "Healthcare"),

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