from datetime import datetime
import sys
import hashlib
import re

def get_app_models():
    """
    Recupera db e modelli dal modulo Flask già caricato.
    Serve a evitare circular import e doppio import app/__main__.
    """
    app_module = sys.modules.get("app") or sys.modules.get("__main__")

    if not app_module:
        raise RuntimeError("App module not loaded")

    return (
        app_module.db,
        app_module.Product,
        app_module.License,
        app_module.LicenseCheckLog,
    )

def _now():
    return datetime.utcnow()

def _license_key_for_audit(license_key):
    """
    Non salviamo mai la license_key in chiaro nei log.
    Salviamo hash SHA-256 + ultimi 6 caratteri per audit/debug.
    """
    key = (license_key or "").strip()

    if not key:
        return ""

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    tail = key[-6:] if len(key) >= 6 else key

    return f"sha256:{digest}|tail:{tail}"


def _valid_license_key_format(license_key):
    """
    Formato prudenziale:
    - 8-255 caratteri
    - lettere, numeri, underscore, trattino, punto
    Non blocca formati normali tipo ABC-123_x.y
    """
    key = (license_key or "").strip()

    if len(key) < 8 or len(key) > 255:
        return False

    return re.fullmatch(r"[A-Za-z0-9_.-]+", key) is not None


def _valid_product_slug(product_slug):
    """
    Slug prodotto sicuro: strategy_pegasus, ea_v1, ecc.
    """
    slug = (product_slug or "").strip()

    if len(slug) < 2 or len(slug) > 120:
        return False

    return re.fullmatch(r"[A-Za-z0-9_-]+", slug) is not None


def _valid_mt5_account(mt5_account):
    """
    Account MT5: di norma numerico.
    Manteniamo range ampio per broker diversi.
    """
    account = str(mt5_account or "").strip()

    if len(account) < 3 or len(account) > 40:
        return False

    return re.fullmatch(r"[0-9]+", account) is not None


def _valid_mt5_server(mt5_server):
    """
    Server broker opzionale, ma se presente deve essere ragionevole.
    """
    server = (mt5_server or "").strip()

    if not server:
        return True

    if len(server) > 180:
        return False

    return re.fullmatch(r"[A-Za-z0-9_.\- ]+", server) is not None

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
    
    db, Product, License, LicenseCheckLog = get_app_models()
    
    try:
        row = LicenseCheckLog(
            license_id=license_obj.id if license_obj else None,
            product_slug=product_slug,
            license_key=_license_key_for_audit(license_key),
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
    
    db, Product, License, LicenseCheckLog = get_app_models()

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
    
    if not _valid_license_key_format(license_key):
        reason = "INVALID_LICENSE_KEY_FORMAT"
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
            "message": "Formato license key non valido."
        }

    if not _valid_product_slug(product_slug):
        reason = "INVALID_PRODUCT_FORMAT"
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
            "message": "Formato prodotto non valido."
        }

    if not mt5_account:
        reason = "MISSING_MT5_ACCOUNT"
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
            "message": "Account MT5 mancante."
        }

    if not _valid_mt5_account(mt5_account):
        reason = "INVALID_MT5_ACCOUNT_FORMAT"
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
            "message": "Formato account MT5 non valido."
        }

    if not _valid_mt5_server(mt5_server):
        reason = "INVALID_MT5_SERVER_FORMAT"
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
            "message": "Formato server MT5 non valido."
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
    # Se è vuota, la prima richiesta valida la lega al conto MT5.
    if license_obj.mt5_account:
        if str(license_obj.mt5_account) != str(mt5_account):
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
        # Auto-bind controllato: prima esecuzione valida lega la licenza al conto.
        license_obj.mt5_account = mt5_account
    
    
    # =========================
    # MT5 SERVER CHECK
    # =========================
    # Il server è opzionale finché non viene valorizzato.
    # Se la licenza ha già un server associato, deve combaciare.
    if license_obj.mt5_server:
        if not mt5_server:
            reason = "MISSING_MT5_SERVER"
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
                "message": "Server broker mancante."
            }
    
        if license_obj.mt5_server != mt5_server:
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