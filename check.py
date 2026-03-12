import os
import json
import time
from pathlib import Path

import requests

DOMAINS = [
    "handelsfachwirt.de",
    "meiermichael.de",
    "michaelmeier.de",
    "michael-meier.de",
    "dihk.de",
    "akademie-handel.de",
    "wbs-training.de",
    "wbstraining.de",
    "michaelmeier.net",
    "michael-meier.net",
]

STATE_FILE = Path("domain_state.json")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Optional, aber empfohlen:
GODADDY_KEY = os.environ.get("GODADDY_KEY")
GODADDY_SECRET = os.environ.get("GODADDY_SECRET")


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message[:4000]}, timeout=30)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_godaddy(domain: str):
    """Liefert True/False/None zurück:
    True = frei, False = registriert, None = unbekannt/Fehler
    """
    if not GODADDY_KEY or not GODADDY_SECRET:
        return None, "no_api_keys"

    url = "https://api.godaddy.com/v1/domains/available"
    headers = {
        "Authorization": f"sso-key {GODADDY_KEY}:{GODADDY_SECRET}"
    }
    params = {"domain": domain}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        data = r.json()
        return bool(data.get("available", False)), "ok"
    except Exception as e:
        return None, f"error:{e}"


def check_rdap(domain: str):
    """RDAP-Heuristik:
    False = registriert (Eintrag gefunden)
    True = wahrscheinlich frei (404/not found)
    None = unbekannt/Fehler
    """
    # Für viele gTLDs funktioniert rdap.org als Bootstrap gut.
    # Für .de testen wir direkt DENIC RDAP.
    if domain.endswith(".de"):
        url = f"https://rdap.denic.de/domain/{domain}"
    else:
        url = f"https://rdap.org/domain/{domain}"

    try:
        r = requests.get(
            url,
            headers={"Accept": "application/rdap+json, application/json"},
            timeout=30,
        )

        if r.status_code == 404:
            return True, "not_found"

        if r.status_code == 200:
            return False, "found"

        return None, f"http_{r.status_code}"
    except Exception as e:
        return None, f"error:{e}"


def decide_status(domain: str):
    gd_status, gd_info = check_godaddy(domain)
    rdap_status, rdap_info = check_rdap(domain)

    # Beste Aussage: beide Quellen stimmen überein
    if gd_status is True and rdap_status is True:
        return "available_confirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    if gd_status is False and rdap_status is False:
        return "registered_confirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    # Fallbacks
    if gd_status is True and rdap_status is None:
        return "available_unconfirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    if gd_status is False and rdap_status is None:
        return "registered_unconfirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    if gd_status is None and rdap_status is True:
        return "available_unconfirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    if gd_status is None and rdap_status is False:
        return "registered_unconfirmed", {
            "godaddy": gd_info,
            "rdap": rdap_info,
        }

    # Widerspruch zwischen Quellen
    return "conflict", {
        "godaddy": gd_info,
        "rdap": rdap_info,
    }


def main():
    state = load_state()
    new_state = {}

    for domain in DOMAINS:
        status, details = decide_status(domain)

        previous = state.get(domain, {})
        prev_status = previous.get("status")
        streak = previous.get("streak", 0)

        # streak nur erhöhen, wenn Status gleich bleibt
        if status == prev_status:
            streak += 1
        else:
            streak = 1

        new_state[domain] = {
            "status": status,
            "streak": streak,
            "details": details,
            "checked_at": int(time.time()),
        }

        # Nur alarmieren, wenn 2 Läufe hintereinander bestätigt frei
        if status == "available_confirmed" and streak == 2:
            send_telegram(f"🔥 DOMAIN BESTÄTIGT FREI: {domain}")

        # Optional: Konflikte melden
        if status == "conflict" and prev_status != "conflict":
            send_telegram(
                f"⚠️ Konflikt bei {domain}\n"
                f"GoDaddy: {details.get('godaddy')}\n"
                f"RDAP: {details.get('rdap')}"
            )

    save_state(new_state)


if __name__ == "__main__":
    main()
