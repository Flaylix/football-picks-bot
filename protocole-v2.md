# Trèfle Élite V2 — Protocole de lancement

Ordre d'exécution recommandé : on ne vend rien tant que le bot n'est pas fiabilisé et validé. Chaque phase dépend de la précédente.

## Phase 1 — Fiabiliser le bot (avant tout le reste)

- [ ] Remonter le seuil de confiance minimum dans le script (probabilité de marché ≥ 75-80%).
- [ ] Ajouter les sports tennis (ATP/WTA) et basket (NBA) dans la config de l'API de cotes.
- [ ] Fixer l'heure d'envoi automatique du message le matin (cron job à une heure fixe, ex: 8h00).
- [ ] Mettre en place un log automatique pronostic → résultat réel (fichier ou base de données), pour calculer le taux de réussite réel jour après jour.
- [ ] **Période de validation : 2 à 3 semaines de test réel avant de vendre**, pour vérifier que le taux de réussite avec le nouveau seuil s'approche bien de 80%. C'est l'étape la plus importante : vendre un produit "80% de réussite" sans l'avoir vérifié sur des données réelles est risqué commercialement et vis-à-vis des clients.

## Phase 2 — Site web

- [ ] Réserver un nom de domaine.
- [ ] Page de présentation : l'offre, le taux de réussite réel mesuré en Phase 1, exemples de pronostics passés, prix de l'abonnement.
- [ ] Bouton "S'abonner" → redirige vers le paiement Stripe.
- [ ] Page de confirmation post-paiement expliquant comment rejoindre le canal Telegram.
- [ ] Mentions légales de base (paris sportifs = jeu d'argent, avertissement 18+, lien joueurs-info-service.fr comme déjà utilisé dans les messages du bot).

## Phase 3 — Paiement (Stripe)

- [ ] Créer le compte Stripe (si pas déjà fait) et vérifier l'activation (KYC, IBAN de la micro-entreprise).
- [ ] Créer le produit + le prix d'abonnement récurrent dans Stripe.
- [ ] Configurer les webhooks : `checkout.session.completed`, `invoice.payment_failed`, `customer.subscription.deleted`.
- [ ] Déployer un petit serveur (Flask/FastAPI) qui reçoit ces webhooks.

## Phase 4 — Automatisation Telegram

- [ ] Webhook `checkout.session.completed` → le bot génère un lien d'invitation Telegram à usage unique (`createChatInviteLink`, limite 1 membre) et l'envoie au client (email ou Telegram).
- [ ] Webhook `invoice.payment_failed` ou `customer.subscription.deleted` → le bot exclut le membre (`banChatMember` puis `unbanChatMember` pour permettre un retour si réabonnement).
- [ ] Test : un paiement test doit déclencher l'ajout, une annulation test doit déclencher l'exclusion.

## Phase 5 — Test end-to-end avant ouverture publique

- [ ] Simuler un parcours client complet (paiement → accès canal → annulation → exclusion) avec une carte de test Stripe.
- [ ] Vérifier que les messages du bot continuent d'arriver normalement au canal pendant tout le processus.

## Phase 6 — Lancement

- [ ] Ouvrir les inscriptions.
- [ ] Annoncer le taux de réussite réel mesuré (pas un chiffre théorique).
