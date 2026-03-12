import requests
import os

DOMAINS = [
    "handelsfachwirt.de",
    "meiermichael.de"
    "michaelmeier.de"
    "michael-meier.de"
    "dihk.de"
    "akademie-handel.de"
    "wbs-training.de"
    "wbstraining.de"

]

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def check(domain):
    url = "https://api.domainsdb.info/v1/domains/search"
    r = requests.get(url, params={"domain": domain.split(".")[0]})
    data = r.json()

    if "domains" not in data:
        send(f"🔥 DOMAIN FREI: {domain}")


for d in DOMAINS:
    check(d)
