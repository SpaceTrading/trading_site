import requests
import os

#  SECRET KEY
TURNSTILE_SECRET_KEY = os.environ.get("0x4AAAAAADEMHrMbbdwbbE4vI1xQ4vqvtUk", "")


def verify_turnstile(token, ip=None):
    """
    Verifica token Cloudflare Turnstile
    """

    if not token:
        return False

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    data = {
        "secret": TURNSTILE_SECRET_KEY,
        "response": token
    }

    # opzionale ma PRO: aggiunge IP
    if ip:
        data["remoteip"] = ip

    try:
        response = requests.post(url, data=data, timeout=5)
        result = response.json()

        # DEBUG (puoi toglierlo dopo)
        print("TURNSTILE RESPONSE:", result)

        return result.get("success", False)

    except Exception as e:
        print("TURNSTILE ERROR:", e)
        return False