# Trèfle Élite — Proposition V2

La V1 tourne (pronostics quotidiens postés sur le canal Telegram, basés sur les probabilités implicites des cotes bookmakers). Voici ce qu'on ajoute pour la V2.

## 1. Amélioration du taux de réussite (objectif 80%)

Aujourd'hui le bot poste un nombre fixe de matchs par jour, sans filtrer sur la fiabilité du pronostic. Pour viser 80% de réussite réelle :

- **Remonter le seuil de confiance minimum** : ne garder que les matchs où la probabilité de marché dépasse un seuil élevé (75-80%+), au lieu de toujours sortir un top 10 fixe.
- **Accepter un nombre de picks variable par jour** : certains jours 1-2 picks, d'autres jours 0 s'il n'y a pas de favori assez net. Moins de matchs, mais plus fiables — c'est le compromis demandé.
- **Filtrer les compétitions à risque** : exclure les matchs de coupe ou de divisions inférieures où les données/cotes sont moins fiables et les surprises plus fréquentes.
- **Suivi de performance en continu** : logger chaque pronostic + résultat réel pour ajuster le seuil au fil des semaines si le taux réel s'écarte de l'objectif.
- **Fixer l'heure d'envoi du message quotidien le matin** (actuellement envoyé le soir).

## 2. Extension à d'autres sports (plus de volume, plus de matchs à 80%+)

Plutôt que de se limiter au foot, on couvre plusieurs sports pour avoir plus de matchs candidats chaque jour et augmenter les chances de trouver des picks très fiables.

**À ajouter en priorité :**
- **Tennis (ATP/WTA)** — pas de match nul, écarts de niveau importants entre joueurs → beaucoup de probabilités de marché à 85-95%. Le sport le plus adapté à notre modèle.
- **Basketball (NBA, EuroLeague)** — pas de nul non plus, favoris souvent au-dessus de 75-80% de probabilité.

**À écarter pour l'instant :**
- **Baseball (MLB), Hockey (NHL)** — trop de variance, les favoris dépassent rarement 65-70% → ferait baisser notre taux de réussite global.
- **Golf, cricket, NASCAR** — format différent (pas un simple face-à-face vainqueur), nécessiterait de refaire le calcul de probabilité, pas juste ajouter une source de données.

**Faisabilité :** notre source de cotes actuelle (The Odds API) couvre déjà tennis, NBA, NHL, MLB, MMA nativement — c'est juste une ligne de config à ajouter, pas une nouvelle intégration technique. Seul point à vérifier : notre quota d'appels API avec plus de sports suivis.

## 3. Système de paiement (abonnement récurrent)

- Mise en place de **Stripe** pour gérer les abonnements (paiement récurrent, relances automatiques en cas d'échec, gestion des annulations).
- Facturation compatible micro-entreprise (SEPA, euros).
- Génération automatique d'un lien de paiement par client.

## 4. Ajout / expulsion automatique du canal Telegram

- Quand un paiement est validé → le bot génère un lien d'invitation Telegram à usage unique et l'envoie automatiquement au client.
- Quand un abonnement est annulé ou un paiement échoue → le bot exclut automatiquement le membre du canal.
- Tout ça piloté par les webhooks Stripe, sans intervention manuelle.

## 5. Site web de paiement

- Une page simple présentant l'offre (taux de réussite affiché, exemples de pronostics passés, prix de l'abonnement).
- Bouton "S'abonner" → redirige vers la page de paiement Stripe.
- Page de confirmation après paiement expliquant comment rejoindre le canal.

## Ordre de priorité proposé

1. Ajuster le seuil de confiance du bot + ajouter tennis et NBA (rapide, améliore le produit avant même de vendre).
2. Site web + page de présentation de l'offre.
3. Intégration Stripe + webhooks.
4. Automatisation ajout/expulsion Telegram.
