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
    ("Amazon", "AMZN", "ConsumerDiscretionary"),
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
    
    # =========================
    # ENERGY
    # =========================
    ("Exxon Mobil", "XOM", "Energy"),
    ("Chevron", "CVX", "Energy"),
    ("Shell", "SHEL", "Energy"),
    ("BP", "BP", "Energy"),
    ("TotalEnergies", "TTE", "Energy"),
    
    # =========================
    # INDUSTRIALS
    # =========================
    ("Boeing", "BA", "Industrials"),
    ("Lockheed Martin", "LMT", "Industrials"),
    ("Raytheon", "RTX", "Industrials"),
    ("Caterpillar", "CAT", "Industrials"),
    ("General Electric", "GE", "Industrials"),
    
    # =========================
    # CONSUMER STAPLES
    # =========================
    ("Coca-Cola", "KO", "ConsumerStaples"),
    ("PepsiCo", "PEP", "ConsumerStaples"),
    ("Procter & Gamble", "PG", "ConsumerStaples"),
    ("Walmart", "WMT", "ConsumerStaples"),
    ("Costco", "COST", "ConsumerStaples"),
    
    # =========================
    # COMMUNICATION
    # =========================
    ("Netflix", "NFLX", "Communication"),
    ("Disney", "DIS", "Communication"),
    ("Comcast", "CMCSA", "Communication"),
    ("AT&T", "T", "Communication"),
    ("Verizon", "VZ", "Communication"),
    
    # =========================
    # MATERIALS
    # =========================
    ("Dow", "DOW", "Materials"),
    ("DuPont", "DD", "Materials"),
    ("Rio Tinto", "RIO", "Materials"),
    ("BHP", "BHP", "Materials"),
    
    # =========================
    # UTILITIES
    # =========================
    ("NextEra Energy", "NEE", "Utilities"),
    ("Duke Energy", "DUK", "Utilities"),
    ("Southern Company", "SO", "Utilities"),    

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