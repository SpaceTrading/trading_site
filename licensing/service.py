from datetime import datetime

from app import db, Product, License, LicenseCheckLog


def _now():
    return datetime.utcnow()


def log_license_check(
    license_obj=None,
    product_slug=None,
    license_key=None,
    mt5_account=None,
    mt5_server=None,
    ip_address=None,
    result="BLOCK",
    reason="UNKNOWN",
):
    """
    Log audit del controllo licenza.
    Non deve mai bloccare la risposta principale.
    """
    try:
        row = LicenseCheckLog(
            license_id=license_obj.id if license_obj else None,
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result=result,
            reason=reason,
        )
        db.session.add(row)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("LICENSE LOG ERROR:", e)


def check_license_payload(payload, ip_address=None):
    """
    Controlla una licenza EA.

    Input atteso:
    {
        "license_key": "...",
        "product": "strategy_pegasus",
        "mt5_account": "123456",
        "mt5_server": "Broker-Demo",
        "ea_version": "1.0"
    }

    Output:
    dict JSON-ready.
    """

    license_key = (payload.get("license_key") or "").strip()
    product_slug = (payload.get("product") or "").strip()
    mt5_account = str(payload.get("mt5_account") or "").strip()
    mt5_server = (payload.get("mt5_server") or "").strip()
    ea_version = (payload.get("ea_version") or "").strip()

    # =========================
    # BASIC VALIDATION
    # =========================
    if not license_key:
        reason = "MISSING_LICENSE_KEY"
        log_license_check(
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": "blocked",
            "reason": reason,
            "message": "License key mancante."
        }

    if not product_slug:
        reason = "MISSING_PRODUCT"
        log_license_check(
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": "blocked",
            "reason": reason,
            "message": "Product mancante."
        }

    # =========================
    # PRODUCT CHECK
    # =========================
    product = Product.query.filter_by(slug=product_slug).first()

    if not product or not product.is_active:
        reason = "PRODUCT_NOT_FOUND_OR_INACTIVE"
        log_license_check(
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": "blocked",
            "reason": reason,
            "message": "Prodotto non valido o non attivo."
        }

    # =========================
    # LICENSE CHECK
    # =========================
    license_obj = License.query.filter_by(
        license_key=license_key,
        product_id=product.id
    ).first()

    if not license_obj:
        reason = "LICENSE_NOT_FOUND"
        log_license_check(
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": "blocked",
            "reason": reason,
            "message": "Licenza non trovata."
        }

    # =========================
    # STATUS CHECK
    # =========================
    if license_obj.status != "active":
        reason = f"LICENSE_{license_obj.status.upper()}"
        log_license_check(
            license_obj=license_obj,
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": license_obj.status,
            "reason": reason,
            "message": "Licenza non attiva."
        }

    # =========================
    # EXPIRY CHECK
    # =========================
    now = _now()

    if license_obj.expires_at and license_obj.expires_at < now:
        license_obj.status = "expired"
        db.session.add(license_obj)
        db.session.commit()

        reason = "LICENSE_EXPIRED"
        log_license_check(
            license_obj=license_obj,
            product_slug=product_slug,
            license_key=license_key,
            mt5_account=mt5_account,
            mt5_server=mt5_server,
            ip_address=ip_address,
            result="BLOCK",
            reason=reason,
        )
        return {
            "ok": False,
            "status": "expired",
            "reason": reason,
            "message": "Licenza scaduta."
        }

    # =========================
    # MT5 ACCOUNT CHECK
    # =========================
    # Se la licenza ha già un account associato, deve combaciare.
    # Se invece è vuota, per ora la associamo al primo account che la usa.
    if license_obj.mt5_account:
        if mt5_account and str(license_obj.mt5_account) != str(mt5_account):
            reason = "ACCOUNT_MISMATCH"
            log_license_check(
                license_obj=license_obj,
                product_slug=product_slug,
                license_key=license_key,
                mt5_account=mt5_account,
                mt5_server=mt5_server,
                ip_address=ip_address,
                result="BLOCK",
                reason=reason,
            )
            return {
                "ok": False,
                "status": "blocked",
                "reason": reason,
                "message": "Account MT5 non autorizzato."
            }
    else:
        # Auto-bind controllato: prima esecuzione lega la licenza al conto.
        if mt5_account:
            license_obj.mt5_account = mt5_account

    # Broker/server opzionale: se già settato, controlla match.
    if license_obj.mt5_server:
        if mt5_server and license_obj.mt5_server != mt5_server:
            reason = "SERVER_MISMATCH"
            log_license_check(
                license_obj=license_obj,
                product_slug=product_slug,
                license_key=license_key,
                mt5_account=mt5_account,
                mt5_server=mt5_server,
                ip_address=ip_address,
                result="BLOCK",
                reason=reason,
            )
            return {
                "ok": False,
                "status": "blocked",
                "reason": reason,
                "message": "Server broker non autorizzato."
            }
    else:
        if mt5_server:
            license_obj.mt5_server = mt5_server

    # =========================
    # SUCCESS
    # =========================
    license_obj.last_check_at = now
    db.session.add(license_obj)
    db.session.commit()

    reason = "LICENSE_OK"

    log_license_check(
        license_obj=license_obj,
        product_slug=product_slug,
        license_key=license_key,
        mt5_account=mt5_account,
        mt5_server=mt5_server,
        ip_address=ip_address,
        result="OK",
        reason=reason,
    )

    return {
        "ok": True,
        "status": "active",
        "reason": reason,
        "message": "Licenza valida.",
        "product": product.slug,
        "product_name": product.name,
        "ea_version": ea_version,
        "expires_at": license_obj.expires_at.isoformat() if license_obj.expires_at else None,
        "mt5_account": license_obj.mt5_account,
        "mt5_server": license_obj.mt5_server,
    }