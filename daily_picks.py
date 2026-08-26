#!/usr/bin/env python3
"""
Bot de pronostics football quotidien.

Récupère les cotes du jour (Winamax, Betclic, etc. via The Odds API),
calcule une probabilité de marché pour chaque issue (marge bookmaker
retirée, moyennée sur les bookmakers disponibles), sélectionne les
matchs les plus "sûrs" du jour et poste le résumé sur un channel ou
groupe Telegram.

⚠️ Ces probabilités sont dérivées des cotes du marché : elles reflètent
ce que les bookmakers pensent, pas une prédiction garantie. Ce script
ne constitue pas un conseil de pari et ne garantit aucun gain.

Variables d'environnement requises :
- ODDS_API_KEY       clé API de https://the-odds-api.com
- TELEGRAM_BOT_TOKEN token du bot Telegram (@BotFather)
- TELEGRAM_CHAT_ID   id du channel/groupe Telegram cible (ex: -1001234567890)

Variables optionnelles :
- REGIONS  (def: "fr")  régions de bookmakers à interroger (fr, eu, uk...)
- TOP_N    (def: "10")  nombre de matchs à publier
- SPORTS   (def: grands championnats européens, voir DEFAULT_SPORTS)
           liste séparée par des virgules de "sport keys" The Odds API
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()  # no-op si aucun fichier .env n'est présent (cas GitHub Actions)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

REGIONS = os.environ.get("REGIONS", "fr")
TOP_N = int(os.environ.get("TOP_N", "10"))

# Championnats couverts par défaut. Liste des "sport keys" disponibles :
# https://the-odds-api.com/sports-odds-data/sports-apis.html
DEFAULT_SPORTS = [
    "soccer_france_ligue_one",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
]
SPORTS = [s.strip() for s in os.environ.get("SPORTS", ",".join(DEFAULT_SPORTS)).split(",") if s.strip()]

PARIS_TZ = ZoneInfo("Europe/Paris")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


def fetch_odds_for_sport(sport_key: str):
    """Récupère les cotes 1N2 (h2h) du jour pour un championnat donné."""
    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": "h2h",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
    except requests.RequestException as exc:
        print(f"[warn] {sport_key}: erreur réseau ({exc})", file=sys.stderr)
        return []

    if resp.status_code != 200:
        print(f"[warn] {sport_key}: HTTP {resp.status_code} — {resp.text[:200]}", file=sys.stderr)
        return []

    remaining = resp.headers.get("x-requests-remaining")
    if remaining is not None:
        print(f"[info] {sport_key}: {remaining} requêtes restantes ce mois-ci", file=sys.stderr)

    return resp.json()


def is_today_paris(iso_ts: str) -> bool:
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(PARIS_TZ)
    now = datetime.now(PARIS_TZ)
    return dt.date() == now.date()


def analyze_event(event: dict):
    """Calcule, pour un match, l'issue la plus probable selon le marché.

    Pour chaque bookmaker on retire la marge (overround) en normalisant
    les probabilités implicites (1/cote) pour qu'elles somment à 1, puis
    on moyenne ces probabilités "de-vig" sur tous les bookmakers
    disponibles pour ce match. On garde aussi la meilleure cote proposée
    pour l'issue retenue (et le bookmaker qui la propose).
    """
    outcome_probs: dict[str, list[float]] = {}
    outcome_best_odds: dict[str, tuple[float, str]] = {}

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = market.get("outcomes", [])
            if len(outcomes) < 2:
                continue

            inv_sum = sum(1 / o["price"] for o in outcomes)
            for o in outcomes:
                name, price = o["name"], o["price"]
                fair_prob = (1 / price) / inv_sum
                outcome_probs.setdefault(name, []).append(fair_prob)

                current_best = outcome_best_odds.get(name)
                if current_best is None or price > current_best[0]:
                    outcome_best_odds[name] = (price, bookmaker.get("title", "?"))

    if not outcome_probs:
        return None

    avg_probs = {name: sum(vals) / len(vals) for name, vals in outcome_probs.items()}
    pick_name = max(avg_probs, key=avg_probs.get)
    pick_prob = avg_probs[pick_name]
    pick_odds, pick_bookmaker = outcome_best_odds[pick_name]

    return {
        "home": event["home_team"],
        "away": event["away_team"],
        "commence_time": event["commence_time"],
        "pick": pick_name,
        "probability": pick_prob,
        "odds": pick_odds,
        "bookmaker": pick_bookmaker,
        "n_bookmakers": len({bk.get("title") for bk in event.get("bookmakers", [])}),
    }


def build_daily_picks():
    all_matches = []
    for sport in SPORTS:
        for event in fetch_odds_for_sport(sport):
            if not is_today_paris(event["commence_time"]):
                continue
            analysis = analyze_event(event)
            if analysis:
                all_matches.append(analysis)

    all_matches.sort(key=lambda m: m["probability"], reverse=True)
    return all_matches[:TOP_N]


def format_message(matches):
    today = datetime.now(PARIS_TZ).strftime("%d/%m/%Y")

    if not matches:
        return (
            f"⚽ *Pronostics du {today}*\n\n"
            "Aucun match avec des cotes disponibles aujourd'hui sur les "
            "championnats suivis."
        )

    lines = [f"⚽ *Pronostics du jour — {today}*\n"]
    for i, m in enumerate(matches, 1):
        kickoff = (
            datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            .astimezone(PARIS_TZ)
            .strftime("%Hh%M")
        )
        pct = round(m["probability"] * 100)
        lines.append(
            f"{i}. *{m['home']} vs {m['away']}* — {kickoff}\n"
            f"   🎯 Pronostic : *{m['pick']}*\n"
            f"   📊 Probabilité (marché, {m['n_bookmakers']} bookmakers) : {pct}%\n"
            f"   💰 Meilleure cote : {m['odds']:.2f} ({m['bookmaker']})\n"
        )

    lines.append(
        "\n_Probabilités calculées à partir des cotes des bookmakers "
        "(marge retirée), ce n'est pas une garantie de résultat. Le pari "
        "sportif comporte des risques financiers — jouez avec modération, "
        "18+, interdit aux mineurs. joueurs-info-service.fr_"
    )
    return "\n".join(lines)


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    missing = [
        name
        for name, val in [
            ("ODDS_API_KEY", ODDS_API_KEY),
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ]
        if not val
    ]
    if missing:
        print(f"Variables d'environnement manquantes : {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    picks = build_daily_picks()
    message = format_message(picks)
    print(message)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
