# 🤖 RSV Trading Bot

Bot Telegram de signaux trading — Stratégie SMC/ICT sur XAU/USD

## 🚀 Fonctionnalités

- ✅ Menu ON/OFF simple et fluide
- 📡 Réception signaux TradingView via webhook
- 💰 Money Management automatique (0.25% / 0.5% / 0.75%)
- 🔁 Suivi live TP / SL / Break Even
- 🚨 Arrêt automatique après 2 pertes
- 👥 Multi-utilisateurs avec niveaux d'accès
- 📊 Rapports quotidiens et hebdomadaires
- ⭐ Score de confiance 1 à 5

## ⚙️ Variables d'environnement (Railway)

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Token du bot Telegram (BotFather) |
| `ADMIN_ID` | Ton user_id Telegram |
| `PORT` | Port du serveur (Railway gère automatiquement) |

## 📋 Commandes

| Commande | Description | Accès |
|---|---|---|
| `/start` | Menu principal | Tous |
| `/status` | Statut rapide | Tous |
| `/capital [montant]` | Définir son capital | Tous |
| `/report` | Rapport du jour | Tous |
| `/weekly` | Rapport hebdomadaire | Tous |
| `/adduser [id] [nom]` | Ajouter un abonné | Admin |
| `/removeuser [id]` | Supprimer un abonné | Admin |
| `/listusers` | Liste des abonnés | Admin |

## 🔗 Webhook TradingView

URL : `https://[ton-projet].up.railway.app/webhook`

Format JSON de l'alerte :
```json
{
  "pair": "XAUUSD",
  "direction": "BUY",
  "entry": 2345.50,
  "tp": 2380.00,
  "sl": 2330.00,
  "timeframe": "M5",
  "score": 4
}
```

## 🛡️ Sécurité

- Filtrage strict par user_id Telegram
- Token stocké en variable d'environnement (jamais dans le code)
- Repo GitHub en mode Privé
