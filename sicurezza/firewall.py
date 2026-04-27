
# sicurezza/firewall.py

import time
from sicurezza.ip_tracker import get_ip_info, register_failure, register_success, is_blocked, block_ip


def check_request(ip):
    info = get_ip_info(ip)

    # IP già bloccato
    if is_blocked(ip):
        return "blocked"

    # molto sospetto
    if info["failures"] >= 5:
        block_ip(ip, seconds=600)  # 10 minuti
        return "blocked"

    # sospetto
    if info["failures"] >= 2:
        return "suspicious"

    # normale
    return "ok"