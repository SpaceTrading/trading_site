import sqlite3

conn = sqlite3.connect("market.db")
cur = conn.cursor()

# Pulisce tabella (evita duplicati quando rilanci)
cur.execute("DELETE FROM ownerships")

ownerships_data = [

    # BIG ASSET MANAGERS → TECH
    ("BlackRock", "Apple", 8),
    ("BlackRock", "Microsoft", 7),
    ("BlackRock", "Google", 6),
    ("BlackRock", "Amazon", 6),

    ("Vanguard", "Apple", 7),
    ("Vanguard", "Microsoft", 8),
    ("Vanguard", "Google", 6),
    ("Vanguard", "Tesla", 5),

    # FINANCE → HEALTHCARE
    ("JPMorgan", "Pfizer", 3),
    ("JPMorgan", "Johnson & Johnson", 2),

    ("Goldman Sachs", "Moderna", 2),
    ("Goldman Sachs", "Meta", 3),

    # TECH → TECH / AI
    ("Microsoft", "OpenAI", 49),
    ("Google", "Stripe", 4),

    # ENERGY CONNECTIONS
    ("BlackRock", "ExxonMobil", 5),
    ("Vanguard", "Chevron", 4),

    # CONSUMER
    ("BlackRock", "Coca-Cola", 5),
    ("Vanguard", "Nestle", 4),

    # DEFENSE / INDUSTRIAL
    ("JPMorgan", "Boeing", 3),
    ("BlackRock", "Lockheed Martin", 6),

    # AI / FUTURE
    ("Microsoft", "Nvidia", 6),

]

# Inserimento dati
cur.executemany("""
INSERT INTO ownerships (source, target, percentage)
VALUES (?, ?, ?)
""", ownerships_data)

conn.commit()
conn.close()

print("Ownerships seed completato ✅")