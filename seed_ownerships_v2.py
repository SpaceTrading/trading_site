import argparse
import csv
import os
import shutil
from datetime import datetime

from app import app, db, Company, Ownership


# =========================================================
# CONFIG
# =========================================================

CSV_FILE = "ownership_seed_v2.csv"
DB_FILE = os.path.join("instance", "app.db")


# =========================================================
# HELPERS
# =========================================================

def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_ticker(value):
    value = normalize_text(value)
    return value.upper() if value else None


def to_float(value):
    try:
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def backup_db():
    if not os.path.exists(DB_FILE):
        print(f"[WARN] DB non trovato: {DB_FILE}")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join("instance", f"app_backup_ownership_v2_{ts}.db")

    shutil.copy2(DB_FILE, backup_path)
    return backup_path


def get_or_create_company(name, ticker, sector, apply=False):
    name = normalize_text(name)
    ticker = normalize_ticker(ticker)
    sector = normalize_text(sector)

    if not name:
        return None, "missing_name"

    company = None

    if ticker:
        company = Company.query.filter_by(ticker=ticker).first()

    if not company:
        company = Company.query.filter_by(name=name).first()

    if company:
        changed = False

        if ticker and not company.ticker:
            company.ticker = ticker
            changed = True

        if sector and not company.sector:
            company.sector = sector
            changed = True

        if changed and apply:
            db.session.add(company)

        return company, "existing"

    if not apply:
        return None, "would_create"

    company = Company(
        name=name,
        ticker=ticker,
        sector=sector or None,
        market_cap=None,
        last_updated=None
    )

    db.session.add(company)
    db.session.flush()

    return company, "created"


def find_existing_ownership(source_id, target_id):
    return Ownership.query.filter_by(
        source_id=source_id,
        target_id=target_id
    ).first()


# =========================================================
# MAIN LOGIC
# =========================================================

def run(apply=False):
    print("\n========================================")
    print("OWNERSHIP SEED V2")
    print("MODE:", "APPLY" if apply else "DRY-RUN")
    print("========================================\n")

    if not os.path.exists(CSV_FILE):
        print(f"[ERROR] File CSV non trovato: {CSV_FILE}")
        print("\nCrea un file chiamato ownership_seed_v2.csv nella stessa cartella con colonne:")
        print("source_name,source_ticker,source_sector,target_name,target_ticker,target_sector,percentage")
        return

    backup_path = None

    if apply:
        backup_path = backup_db()
        if backup_path:
            print(f"[BACKUP] Creato backup DB: {backup_path}\n")

    stats = {
        "rows": 0,
        "invalid": 0,
        "companies_existing": 0,
        "companies_would_create": 0,
        "companies_created": 0,
        "ownership_would_create": 0,
        "ownership_created": 0,
        "ownership_would_update": 0,
        "ownership_updated": 0,
        "ownership_existing_same": 0,
        "self_links_skipped": 0,
    }

    with app.app_context():

        with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            required_cols = {
                "source_name",
                "source_ticker",
                "source_sector",
                "target_name",
                "target_ticker",
                "target_sector",
                "percentage",
            }

            missing = required_cols - set(reader.fieldnames or [])

            if missing:
                print("[ERROR] Colonne mancanti nel CSV:", sorted(missing))
                return

            for row in reader:
                stats["rows"] += 1

                source_name = normalize_text(row.get("source_name"))
                source_ticker = normalize_ticker(row.get("source_ticker"))
                source_sector = normalize_text(row.get("source_sector"))

                target_name = normalize_text(row.get("target_name"))
                target_ticker = normalize_ticker(row.get("target_ticker"))
                target_sector = normalize_text(row.get("target_sector"))

                percentage = to_float(row.get("percentage"))

                if not source_name or not target_name or percentage is None or percentage <= 0:
                    stats["invalid"] += 1
                    print(f"[INVALID] Riga {stats['rows']}: {row}")
                    continue

                source_company, source_status = get_or_create_company(
                    source_name,
                    source_ticker,
                    source_sector,
                    apply=apply
                )

                target_company, target_status = get_or_create_company(
                    target_name,
                    target_ticker,
                    target_sector,
                    apply=apply
                )

                for status in [source_status, target_status]:
                    if status == "existing":
                        stats["companies_existing"] += 1
                    elif status == "would_create":
                        stats["companies_would_create"] += 1
                    elif status == "created":
                        stats["companies_created"] += 1

                if not apply:
                    print(
                        f"[DRY] {source_name} ({source_ticker}) "
                        f"→ {target_name} ({target_ticker}) "
                        f"{percentage}%"
                    )

                    if source_status == "would_create":
                        print(f"      - creerebbe source node: {source_name}")

                    if target_status == "would_create":
                        print(f"      - creerebbe target node: {target_name}")

                    stats["ownership_would_create"] += 1
                    continue

                if not source_company or not target_company:
                    stats["invalid"] += 1
                    print(f"[SKIP] Impossibile creare/leggere nodi: {row}")
                    continue

                if source_company.id == target_company.id:
                    stats["self_links_skipped"] += 1
                    print(f"[SKIP] Self-link evitato: {source_company.name}")
                    continue

                existing = find_existing_ownership(source_company.id, target_company.id)

                if existing:
                    old_pct = float(existing.percentage)

                    if abs(old_pct - percentage) < 1e-9:
                        stats["ownership_existing_same"] += 1
                        print(
                            f"[SAME] {source_company.name} → {target_company.name} "
                            f"già presente {percentage}%"
                        )
                    else:
                        existing.percentage = percentage
                        db.session.add(existing)
                        stats["ownership_updated"] += 1
                        print(
                            f"[UPDATE] {source_company.name} → {target_company.name}: "
                            f"{old_pct}% → {percentage}%"
                        )

                else:
                    ownership = Ownership(
                        source_id=source_company.id,
                        target_id=target_company.id,
                        percentage=percentage
                    )

                    db.session.add(ownership)
                    stats["ownership_created"] += 1
                    print(
                        f"[CREATE] {source_company.name} → {target_company.name} "
                        f"{percentage}%"
                    )

        if apply:
            db.session.commit()
            print("\n[COMMIT] Modifiche salvate nel DB.")
        else:
            db.session.rollback()
            print("\n[DRY-RUN] Nessuna modifica scritta nel DB.")

    print("\n========================================")
    print("SUMMARY")
    print("========================================")

    for k, v in stats.items():
        print(f"{k}: {v}")

    if backup_path:
        print(f"\nBackup DB: {backup_path}")

    print("\nDONE\n")


# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Scrive davvero nel DB. Senza questo flag fa solo dry-run."
    )

    args = parser.parse_args()

    run(apply=args.apply)