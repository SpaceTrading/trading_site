
# sicurezza/ip_tracker.py

import time

# memoria temporanea (in futuro puoi spostarla su DB/Redis)
ip_data = {}

def get_ip_info(ip):
    if ip not in ip_data:
        ip_data[ip] = {
            "failures": 0,
            "last_request": 0,
            "blocked_until": 0
        }
    return ip_data[ip]


def register_failure(ip):
    info = get_ip_info(ip)
    info["failures"] += 1
    info["last_request"] = time.time()


def register_success(ip):
    info = get_ip_info(ip)
    info["failures"] = 0


def is_blocked(ip):
    info = get_ip_info(ip)

    # Se il blocco è ancora attivo
    if time.time() < info["blocked_until"]:
        return True

    # Se il blocco era scaduto, resetta lo stato
    if info["blocked_until"] > 0:
        info["blocked_until"] = 0
        info["failures"] = 0

    return False


def block_ip(ip, seconds=600):
    info = get_ip_info(ip)
    info["blocked_until"] = time.time() + seconds