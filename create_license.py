from datetime import datetime, timedelta
import secrets

from app import app, db, User, Product, ProductVersion, License


# =========================================================
# CONFIG LICENZA TEST
# =========================================================

USER_EMAIL = "admin@local"

PRODUCT_NAME = "Strategy Pegasus"
PRODUCT_SLUG = "strategy_pegasus"
PRODUCT_PLATFORM = "mql5"

VERSION = "1.0"

# Percorsi relativi dentro instance/private_products/
EA_FILE_PATH = "strategy_pegasus/v1.0/StrategyPegasus.ex5"
SET_FILE_PATH = "strategy_pegasus/v1.0/StrategyPegasus.set"
MANUAL_PATH = "strategy_pegasus/v1.0/manuale_strategy_pegasus.pdf"

# Durata affitto test
DAYS_VALID = 30

# Se vuoi già bloccarla a un conto MT5 specifico, metti numero qui.
# Se lasci None, la licenza si aggancia al primo account MT5 che la usa.
MT5_ACCOUNT = None
MT5_SERVER = None


def make_license_key():
    token = secrets.token_hex(8).upper()
    return f"ST-{token}"


with app.app_context():

    # =========================================================
    # USER
    # =========================================================
    user = User.query.filter_by(email=USER_EMAIL).first()

    if not user:
        print(f"[ERROR] Utente non trovato: {USER_EMAIL}")
        print("Cambia USER_EMAIL oppure crea prima l'utente.")
        raise SystemExit(1)

    # =========================================================
    # PRODUCT
    # =========================================================
    product = Product.query.filter_by(slug=PRODUCT_SLUG).first()

    if not product:
        product = Product(
            name=PRODUCT_NAME,
            slug=PRODUCT_SLUG,
            platform=PRODUCT_PLATFORM,
            description="Expert Advisor MQL5 in affitto.",
            is_active=True,
        )
        db.session.add(product)
        db.session.flush()
        print("[CREATE] Product:", PRODUCT_NAME)
    else:
        product.name = PRODUCT_NAME
        product.platform = PRODUCT_PLATFORM
        product.is_active = True
        db.session.add(product)
        print("[OK] Product già esistente:", PRODUCT_NAME)

    # =========================================================
    # PRODUCT VERSION
    # =========================================================
    # Spegne eventuali versioni latest precedenti
    ProductVersion.query.filter_by(product_id=product.id).update({
        "is_latest": False
    })

    version = ProductVersion.query.filter_by(
        product_id=product.id,
        version=VERSION
    ).first()

    if not version:
        version = ProductVersion(
            product_id=product.id,
            version=VERSION,
            file_path=EA_FILE_PATH,
            set_file_path=SET_FILE_PATH,
            manual_path=MANUAL_PATH,
            changelog_path=None,
            is_latest=True,
            is_active=True,
        )
        db.session.add(version)
        print("[CREATE] ProductVersion:", VERSION)
    else:
        version.file_path = EA_FILE_PATH
        version.set_file_path = SET_FILE_PATH
        version.manual_path = MANUAL_PATH
        version.is_latest = True
        version.is_active = True
        db.session.add(version)
        print("[OK] ProductVersion già esistente:", VERSION)

    # =========================================================
    # LICENSE
    # =========================================================
    license_key = make_license_key()

    license_obj = License(
        user_id=user.id,
        product_id=product.id,
        license_key=license_key,
        mt5_account=MT5_ACCOUNT,
        mt5_server=MT5_SERVER,
        status="active",
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=DAYS_VALID),
    )

    db.session.add(license_obj)

    db.session.commit()

    print("\n========================================")
    print("LICENZA CREATA")
    print("========================================")
    print("Product:", PRODUCT_NAME)
    print("Slug:", PRODUCT_SLUG)
    print("Version:", VERSION)
    print("User:", USER_EMAIL)
    print("License Key:", license_key)
    print("Validità giorni:", DAYS_VALID)
    print("Expires at:", license_obj.expires_at)
    print("MT5 account:", MT5_ACCOUNT or "auto-bind al primo uso")
    print("MT5 server:", MT5_SERVER or "auto-bind al primo uso")
    print("========================================\n")