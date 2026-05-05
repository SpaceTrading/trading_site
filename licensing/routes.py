import os
import sys
from datetime import datetime
from sicurezza.firewall import check_request
from sicurezza.ip_tracker import register_failure, register_success

from flask import (
    Blueprint,
    jsonify,
    request,
    render_template,
    send_from_directory,
    abort,
    current_app,
)
from flask_login import login_required, current_user

from licensing.service import check_license_payload


licensing_bp = Blueprint("licensing", __name__)


def get_app_models():
    """
    Recupera i modelli dal modulo app già caricato.
    Evita circular import app <-> licensing.
    """
    app_module = sys.modules.get("app") or sys.modules.get("__main__")

    if not app_module:
        raise RuntimeError("App module not loaded")

    return (
        app_module.db,
        app_module.Product,
        app_module.ProductVersion,
        app_module.License,
    )


def license_is_active(license_obj):
    """
    Licenza valida se:
    - status active
    - non scaduta
    """
    if not license_obj:
        return False

    if license_obj.status != "active":
        return False

    if license_obj.expires_at and license_obj.expires_at < datetime.utcnow():
        return False

    return True


@licensing_bp.route("/api/license/check", methods=["POST"])
def api_license_check():
    """
    Endpoint usato dall'EA MQL5 per verificare la licenza.

    Richiesta JSON:
    {
        "license_key": "...",
        "product": "strategy_pegasus",
        "mt5_account": "123456",
        "mt5_server": "Broker-Demo",
        "ea_version": "1.0"
    }
    """

    try:
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

        status = check_request(ip_address)
        if status == "blocked":
            return jsonify({
                "ok": False,
                "status": "blocked",
                "reason": "RATE_LIMIT_BLOCK",
                "message": "Troppi tentativi. Riprova più tardi."
            }), 429
        
        payload = request.get_json(silent=True) or {}

        result = check_license_payload(payload, ip_address=ip_address)
        
        if result.get("ok"):
            register_success(ip_address)
        else:
            register_failure(ip_address)        

        status_code = 200 if result.get("ok") else 403

        return jsonify(result), status_code

    except Exception as e:
        print("LICENSE CHECK ERROR:", e)

        return jsonify({
            "ok": False,
            "status": "error",
            "reason": "SERVER_ERROR",
            "message": "Errore server durante controllo licenza."
        }), 500


@licensing_bp.route("/my-products")
@login_required
def my_products():
    """
    Pagina utente: mostra i prodotti acquistati/affittati.
    """

    db, Product, ProductVersion, License = get_app_models()

    licenses = (
        License.query
        .filter_by(user_id=current_user.id)
        .order_by(License.created_at.desc())
        .all()
    )

    rows = []

    for lic in licenses:
        product = lic.product
        
        if not product:
            continue        

        latest_version = (
            ProductVersion.query
            .filter_by(product_id=product.id, is_latest=True, is_active=True)
            .first()
        )

        rows.append({
            "license": lic,
            "product": product,
            "version": latest_version,
            "is_active": license_is_active(lic),
            "expires_at": lic.expires_at,
            "files": {
                "ea": os.path.basename(latest_version.file_path) if latest_version and latest_version.file_path else None,
                "set": os.path.basename(latest_version.set_file_path) if latest_version and latest_version.set_file_path else None,
                "manual": os.path.basename(latest_version.manual_path) if latest_version and latest_version.manual_path else None,
                "changelog": os.path.basename(latest_version.changelog_path) if latest_version and latest_version.changelog_path else None,
            }
        })

    return render_template("my_products.html", rows=rows)


@licensing_bp.route("/download/product/<slug>/<version>/<filename>")
@login_required
def download_product_file(slug, version, filename):
    """
    Download protetto dei file prodotto.
    I file NON stanno in static.
    Stanno in:
    instance/private_products/<product>/<version>/<file>
    """

    db, Product, ProductVersion, License = get_app_models()

    product = Product.query.filter_by(slug=slug, is_active=True).first()

    if not product:
        abort(404)

    license_obj = (
        License.query
        .filter_by(user_id=current_user.id, product_id=product.id)
        .first()
    )

    if not license_is_active(license_obj):
        abort(403)

    product_version = (
        ProductVersion.query
        .filter_by(
            product_id=product.id,
            version=version,
            is_active=True
        )
        .first()
    )

    if not product_version:
        abort(404)

    allowed_paths = [
        product_version.file_path,
        product_version.set_file_path,
        product_version.manual_path,
        product_version.changelog_path,
    ]

    allowed_paths = [p for p in allowed_paths if p]

    selected_path = None

    for path in allowed_paths:
        if os.path.basename(path) == filename:
            selected_path = path
            break

    if not selected_path:
        abort(403)

    private_root = os.path.join(current_app.instance_path, "private_products")
    absolute_path = os.path.abspath(os.path.join(private_root, selected_path))

    # sicurezza anti path traversal
    private_root_abs = os.path.abspath(private_root)

    if os.path.commonpath([private_root_abs, absolute_path]) != private_root_abs:
        abort(403)

    if not os.path.exists(absolute_path):
        abort(404)

    directory = os.path.dirname(absolute_path)
    safe_filename = os.path.basename(absolute_path)

    return send_from_directory(
        directory,
        safe_filename,
        as_attachment=True
    )