import sqlite3

conn = sqlite3.connect("market.db")
cur = conn.cursor()

# Pulisce tabella (evita duplicati quando rilanci)
cur.execute("DELETE FROM ownerships")

ownerships_data = [

    ("BlackRock", "Apple", 8),
    ("BlackRock", "Microsoft", 7),
    ("BlackRock", "Google", 6),
    ("BlackRock", "Amazon", 6),

    ("Vanguard", "Apple", 7),
    ("Vanguard", "Microsoft", 8),
    ("Vanguard", "Google", 6),
    ("Vanguard", "Tesla", 5),

    ("JPMorgan", "Pfizer", 3),
    ("JPMorgan", "Johnson & Johnson", 2),

    ("Goldman Sachs", "Apple", 2),
    ("Goldman Sachs", "Microsoft", 3),

]

# Inserimento dati
cur.executemany("""
INSERT INTO ownerships (source, target, percentage)
VALUES (?, ?, ?)
""", ownerships_data)

conn.commit()
conn.close()

print("Ownerships seed completato ✅")