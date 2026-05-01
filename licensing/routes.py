from flask import Blueprint, jsonify, request

from licensing.service import check_license_payload


licensing_bp = Blueprint("licensing", __name__)


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
        payload = request.get_json(silent=True) or {}

        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

        result = check_license_payload(payload, ip_address=ip_address)

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