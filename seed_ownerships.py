from app import app, db
from app import Company, Ownership
from datetime import datetime

# =========================
# DATA (NAME-BASED INPUT)
# =========================
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

# =========================
# HELPERS
# =========================
def normalize(name):
    return name.strip()

# =========================
# SEED
# =========================
with app.app_context():

    # Carica tutte le aziende
    companies = Company.query.all()

    # Lookup veloce (O(1))
    name_map = {normalize(c.name): c for c in companies}

    created = 0
    updated = 0
    skipped = 0

    for source_name, target_name, percentage in ownerships_data:

        source_name = normalize(source_name)
        target_name = normalize(target_name)

        source = name_map.get(source_name)
        target = name_map.get(target_name)

        # Se azienda non esiste → skip
        if not source or not target:
            print(f"SKIP: {source_name} → {target_name} (azienda mancante)")
            skipped += 1
            continue

        # Verifica se già esiste relazione
        existing = Ownership.query.filter_by(
            source_id=source.id,
            target_id=target.id
        ).first()

        if existing:
            existing.percentage = percentage
            updated += 1
        else:
            db.session.add(
                Ownership(
                    source_id=source.id,
                    target_id=target.id,
                    percentage=percentage
                )
            )
            created += 1

    db.session.commit()

    print("Ownership seed completato")
    print(f"creati: {created}")
    print(f"aggiornati: {updated}")
    print(f"skipped: {skipped}")