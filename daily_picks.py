#!/usr/bin/env python3
"""
Bot de pronostics multi-sport quotidien.

Récupère les cotes du jour (Winamax, Betclic, etc. via The Odds API),
calcule une probabilité de marché pour chaque issue (marge bookmaker
retirée, moyennée sur les bookmakers disponibles), ne garde que les
matchs jugés suffisamment sûrs (seuil de confiance) et poste le résumé
sur un channel ou groupe Telegram.

⚠️ Ces probabilités sont dérivées des cotes du marché : elles reflètent
ce que les bookmakers pensent, pas une prédiction garantie. Ce script
ne constitue pas un conseil de pari et ne garantit aucun gain.

Variables d'environnement requises :
- ODDS_API_KEY       clé API de https://the-odds-api.com
- TELEGRAM_BOT_TOKEN token du bot Telegram (@BotFather)
- TELEGRAM_CHAT_ID   id du channel/groupe Telegram cible (ex: -1001234567890)

Variables optionnelles :
- REGIONS         (def: "fr")   régions de bookmakers à interroger (fr, eu, uk...)
- MIN_PROBABILITY (def: "0.65") seuil de confiance minimum (0 à 1) pour publier un pick
- MIN_ODDS        (def: "1.20") cote minimum (meilleure cote dispo) pour publier un
                                 pick — évite les picks ultra-favoris mais sans
                                 intérêt (ex: cote à 1.03)
- MAX_PICKS       (def: "10")   nombre maximum de picks publiés, même s'il y en a
                                 plus au-dessus du seuil (garde-fou contre un jour
                                 avec beaucoup de très gros favoris)
- SPORTS          (def: grands championnats + tennis + NBA, voir DEFAULT_SPORTS)
                   liste séparée par des virgules de "sport keys" The Odds API
- PICKS_LOG_PATH  (def: "data/picks_log.jsonl") fichier où chaque pick envoyé
                   est enregistré (un JSON par ligne), pour calculer le taux
                   de réussite réel a posteriori.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()  # no-op si aucun fichier .env n'est présent (cas GitHub Actions)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

REGIONS = os.environ.get("REGIONS", "fr")
MIN_PROBABILITY = float(os.environ.get("MIN_PROBABILITY", "0.65"))
MIN_ODDS = float(os.environ.get("MIN_ODDS", "1.20"))
MAX_PICKS = int(os.environ.get("MAX_PICKS", "10"))
PICKS_LOG_PATH = os.environ.get("PICKS_LOG_PATH", "data/picks_log.jsonl")

# Championnats/sports couverts par défaut. Liste des "sport keys" disponibles :
# https://the-odds-api.com/sports-odds-data/sports-apis.html
#
# Foot : pas de nul possible dans notre modèle actuel (h2h à 2 issues) donc
# on ne garde que les compétitions où la probabilité d'un des deux camps
# peut vraiment dépasser le seuil. Tennis et NBA n'ont pas de match nul,
# ce qui les rend structurellement plus fiables pour ce type de pronostic.
DEFAULT_SPORTS = [
    "soccer_france_ligue_one",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "tennis_atp",
    "tennis_wta",
    "basketball_nba",
]
SPORTS = [s.strip() for s in os.environ.get("SPORTS", ",".join(DEFAULT_SPORTS)).split(",") if s.strip()]

PARIS_TZ = ZoneInfo("Europe/Paris")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


def fetch_odds_for_sport(sport_key: str):
    """Récupère les cotes h2h du jour pour un sport/championnat donné."""
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


def analyze_event(event: dict, sport_key: str):
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
        "sport": sport_key,
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
            analysis = analyze_event(event, sport)
            if analysis:
                all_matches.append(analysis)

    # On ne garde que les picks au-dessus du seuil de confiance ET dont la
    # cote reste au moins à MIN_ODDS (sinon le pick est "sûr" mais sans
    # intérêt : une cote à 1.03 ne rapporte quasi rien). Les meilleurs
    # picks (probabilité la plus haute) sont affichés en premier. Un jour
    # sans favori assez net peut tout à fait donner une liste vide, et
    # c'est voulu : mieux vaut publier zéro pick fiable qu'un pick incertain.
    confident_matches = [
        m for m in all_matches
        if m["probability"] >= MIN_PROBABILITY and m["odds"] >= MIN_ODDS
    ]
    confident_matches.sort(key=lambda m: m["probability"], reverse=True)
    return confident_matches[:MAX_PICKS]


def format_message(matches):
    today = datetime.now(PARIS_TZ).strftime("%d/%m/%Y")

    if not matches:
        return (
            f"🎯 *Pronostics du {today}*\n\n"
            f"Aucun match n'atteint aujourd'hui le seuil de confiance "
            f"({round(MIN_PROBABILITY * 100)}%) sur les sports suivis. "
            f"On ne publie que les picks les plus fiables."
        )

    lines = [f"🎯 *Pronostics du jour — {today}*\n"]
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


def log_picks(matches):
    """Enregistre chaque pick envoyé pour pouvoir calculer le taux de
    réussite réel plus tard (comparaison avec le résultat final).

    ⚠️ Sur GitHub Actions, le système de fichiers est éphémère : ce fichier
    doit être commité/poussé dans le repo à la fin du workflow pour être
    conservé d'une exécution à l'autre (voir le .yml du workflow).
    """
    if not matches:
        return

    path = Path(PICKS_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(PARIS_TZ).isoformat()
    with path.open("a", encoding="utf-8") as f:
        for m in matches:
            entry = {**m, "sent_at": now_iso, "result": None}  # 'result' à remplir plus tard
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
    log_picks(picks)


if __name__ == "__main__":
    main()
