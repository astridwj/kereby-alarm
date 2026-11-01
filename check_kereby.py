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
                return None


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def main():
    state = load_state()
    try:
        html = fetch()
        slugs, cases = parse(html)
    except Exception as e:  # netvaerksfejl e.l.
        print("Kunne ikke hente siden:", e)
        slugs, cases = set(), set()

    if not slugs and not cases:
        # Siden kunne ikke hentes eller har skiftet design. Advar én gang.
        print("Fandt ingen boliger paa siden.")
        if state is not None and not state.get("broken_alerted"):
            notify("Kereby-overvågning virker ikke",
                   "Scriptet kunne ikke læse boligerne. Tjek siden selv, og få scriptet rettet.",
                   priority="default")
            state["broken_alerted"] = True
            save_state(state)
        return

    if state is None:
        save_state({"slugs": sorted(slugs), "cases": sorted(cases), "broken_alerted": False})
        notify("Kereby-overvågning er sat op ✅",
               f"Jeg holder øje med {len(cases)} boliger, heraf {len(slugs)} ledige. "
               "Du får besked, når der kommer nye.",
               priority="default")
        print("Foerste koersel - state gemt.")
        return

    new_slugs = sorted(slugs - set(state.get("slugs", [])))
    new_cases = cases - set(state.get("cases", []))

    for slug in new_slugs:
        notify("Ny ledig bolig hos Kereby!", pretty(slug), link=f"https://kereby.dk/bolig/{slug}/", priority="urgent")
        print("Ny ledig:", slug)

    if new_cases and not new_slugs:
        notify("Ny bolig på Kerebys liste",
               f"{len(new_cases)} ny(e) bolig(er) på listen – måske allerede reserveret. Tryk for at se.",
               priority="default")
        print("Nye sager uden link:", new_cases)

    # Husk alt vi nogensinde har set, saa en bolig der forsvinder og kommer igen ikke giver dobbelt-besked
    state["slugs"] = sorted(set(state.get("slugs", [])) | slugs)
    state["cases"] = sorted(set(state.get("cases", [])) | cases)
    state["broken_alerted"] = False
    save_state(state)


if __name__ == "__main__":
    sys.exit(main())

