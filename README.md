# ⚽ Pronostics foot quotidiens — Bot Telegram

Ce projet poste automatiquement, chaque jour, les matchs de football du jour
avec le plus fort taux de confiance selon le marché des cotes (Winamax,
Betclic, etc.), sur un channel ou groupe Telegram.

**Comment ça marche (V1) :** le script interroge [The Odds API](https://the-odds-api.com)
pour récupérer les cotes 1N2 des grands championnats européens. Pour chaque
match, il retire la marge de chaque bookmaker (le fameux "overround") pour
obtenir une probabilité "juste", moyenne ce calcul sur tous les bookmakers
disponibles, garde l'issue la plus probable, et sélectionne les 10 matchs du
jour où cette probabilité est la plus haute. Il poste ensuite le résumé sur
Telegram.

> ⚠️ Cette probabilité reflète ce que pensent les bookmakers, pas une
> prédiction garantie. Ce n'est pas un outil de "martingale" ni un conseil
> financier — voir la section Limites plus bas.

---

## 1. Créer le bot Telegram

1. Ouvre une conversation avec [@BotFather](https://t.me/BotFather) sur Telegram.
2. Envoie `/newbot`, choisis un nom et un identifiant (doit finir par `bot`).
3. BotFather te donne un **token** du type `123456789:AAG...` — garde-le, c'est `TELEGRAM_BOT_TOKEN`.
4. Crée un **channel** Telegram (ou utilise un groupe existant) où le bot postera.
5. Ajoute ton bot comme **administrateur** du channel/groupe (indispensable pour qu'il puisse poster).
6. Récupère l'**ID du channel/groupe** (`TELEGRAM_CHAT_ID`) :
   - Poste n'importe quel message dans le channel.
   - Va sur `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans ton navigateur.
   - Cherche `"chat":{"id":-1001234567890...}` dans la réponse JSON — c'est cet ID (négatif, commence souvent par `-100`).
   - Si la réponse est vide, essaie de transférer ("forward") un message du channel vers [@userinfobot](https://t.me/userinfobot) ou [@getidsbot](https://t.me/getidsbot).

## 2. Créer une clé The Odds API

1. Va sur [the-odds-api.com](https://the-odds-api.com) et crée un compte gratuit.
2. Récupère ta clé API (`ODDS_API_KEY`) depuis ton tableau de bord.
3. Vérifie le quota du plan gratuit actuel sur leur site (il évolue régulièrement) — chaque exécution du script consomme environ 1 requête par championnat suivi (7 par défaut), donc largement gérable pour un post quotidien.

## 3. Mettre le projet sur GitHub

1. Crée un nouveau dépôt (public ou privé) sur GitHub.
2. Mets-y tous les fichiers de ce dossier (`daily_picks.py`, `requirements.txt`, `.github/workflows/daily_picks.yml`, `.gitignore`, ce README). **Ne mets jamais de `.env` réel dans le dépôt.**

```bash
git init
git add .
git commit -m "Bot pronostics foot"
git branch -M main
git remote add origin https://github.com/<ton-compte>/<ton-repo>.git
git push -u origin main
```

## 4. Ajouter les secrets GitHub

Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**, ajoute trois secrets :

| Nom | Valeur |
|---|---|
| `ODDS_API_KEY` | ta clé The Odds API |
| `TELEGRAM_BOT_TOKEN` | le token de ton bot |
| `TELEGRAM_CHAT_ID` | l'ID du channel/groupe |

## 5. Tester

1. Va dans l'onglet **Actions** du dépôt, ouvre le workflow "Pronostics foot quotidiens".
2. Clique **Run workflow** pour le lancer manuellement (pas besoin d'attendre le cron).
3. Vérifie les logs, puis vérifie que le message est bien arrivé sur ton channel Telegram.

Une fois validé, le workflow tourne tout seul chaque jour à l'heure définie
dans `.github/workflows/daily_picks.yml` (par défaut ~8h heure de Paris) —
tant que le dépôt reste actif, c'est infini, aucun serveur à gérer.

## 6. Personnaliser

- **Championnats suivis** : modifie `DEFAULT_SPORTS` dans `daily_picks.py`, ou passe une variable d'environnement `SPORTS` (liste de "sport keys" séparées par des virgules — [liste complète ici](https://the-odds-api.com/sports-odds-data/sports-apis.html)).
- **Nombre de matchs postés** : variable `TOP_N` (10 par défaut).
- **Bookmakers interrogés** : variable `REGIONS` (`fr` = Betclic, NetBet, PMU, Unibet, Winamax ; `eu` élargit à d'autres bookmakers européens).
- **Horaire de publication** : modifie le `cron` dans le workflow GitHub Actions.

## Limites connues de la V1 (honnêtement)

- **La "probabilité" est celle du marché, pas une prédiction propriétaire.**
  C'est un calcul fiable et transparent (cotes → probabilité implicite,
  marge retirée), mais ça reste l'avis des bookmakers, pas une analyse
  statistique poussée (forme, blessures, historique, xG...).
- **Pas encore de "value bet"** (match où ton modèle diverge du marché en
  ta faveur) — pour ça il faut un vrai modèle prédictif entraîné sur des
  données historiques, ce sera une V2.
- **Pas d'analyse buteur** pour l'instant — nécessite une source de données
  différente (stats joueurs) et un marché de cotes spécifique ("anytime
  goalscorer"), possible en V2 mais plus coûteux en requêtes API.
- Le quota gratuit de The Odds API peut limiter le nombre de championnats
  suivis si le volume de matchs est élevé — à surveiller.
- Aucune garantie de gain : le pari sportif comporte un risque financier réel.

## Pistes pour une V2

- Modèle statistique maison (forme récente, face-à-face, Elo, xG via une
  source de données historiques comme football-data.org ou API-Football).
- Détection de "value bets" : comparer la probabilité de ton modèle à celle
  du marché et ne remonter que les écarts significatifs.
- Marché buteurs (anytime scorer) via API-Football.
- Historique des pronostics postés + suivi de performance (taux de réussite
  réel dans le temps) pour évaluer honnêtement la fiabilité du bot.
