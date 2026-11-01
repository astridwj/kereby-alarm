"""Tjekker kereby.dk/bolig/ for nye ledige boliger og sender besked via ntfy."""
import json
import os
import re
import sys
import urllib.request

URL = "https://kereby.dk/bolig/"
STATE_FILE = "seen.json"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()


def notify(title, message, link=URL, priority="high"):
    if not TOPIC:
        print("Ingen NTFY_TOPIC sat - springer besked over:", title, message)
        return
    req = urllib.request.Request(
        "https://ntfy.sh/" + TOPIC,
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Click": link,
            "Priority": priority,
            "Tags": "house",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=20)


def fetch():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept-Language": "da-DK,da;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse(html):
    # Ledige boliger har et link til deres egen side: /bolig/<adresse>/
    slugs = set(re.findall(r'href=["\'](?:https?://(?:www\.)?kereby\.dk)?/bolig/([a-z0-9][a-z0-9\-]*)/?["\'#?]', html))
    # Alle boliger (ogsaa reserverede/udlejede) har billeder med et sags-id
    cases = set(re.findall(r"media\.jorato\.com/images/case/([0-9a-f\-]{36})/", html))
    return slugs, cases


def pretty(slug):
    words = slug.replace("-", " ")
    return words[:1].upper() + words[1:]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
