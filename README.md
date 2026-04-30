# 🛂 VisaTrack — Plateforme SaaS de surveillance de créneaux Visa

Plateforme complète de surveillance et d'alerte pour les rendez-vous visa (BLS, TLScontact, VFS Global).

## 🚀 Installation rapide (5 minutes)

### Prérequis
- **Python 3.11+** → [python.org](https://python.org)
- **Git** → [git-scm.com](https://git-scm.com)

### Lancer l'installation

```bash
# 1. Cloner ou extraire le projet
cd visatrack

# 2. Lancer le script d'installation automatique
bash setup.sh

# 3. Démarrer le serveur
python manage.py runserver
```

Accès immédiat sur **http://localhost:8000**

---

## 📁 Structure du projet

```
visatrack/
├── manage.py                    # Point d'entrée Django
├── setup.sh                     # Installation automatique
├── requirements.txt             # Dépendances Python
├── .env.example                 # Template configuration
│
├── config/                      # Configuration Django
│   ├── settings.py              # Paramètres complets
│   ├── urls.py                  # Routes principales
│   ├── celery.py                # Tâches asynchrones
│   └── wsgi.py                  # Serveur WSGI
│
├── apps/
│   ├── users/                   # Auth & utilisateurs
│   ├── monitoring/              # Surveillance des créneaux
│   │   ├── models.py            # VisaCenter, Slot, Request
│   │   ├── tasks.py             # Moteur de scraping Celery
│   │   ├── parsers.py           # Parseurs BLS/TLS/VFS
│   │   ├── views.py             # API REST
│   │   └── serializers.py
│   ├── alerts/                  # Système d'alertes
│   │   ├── models.py            # Alert, NotifPreference
│   │   ├── tasks.py             # Dispatch alertes
│   │   └── channels/
│   │       ├── telegram.py      # Bot Telegram complet
│   │       └── email_whatsapp.py
│   ├── billing/                 # Abonnements & paiements
│   │   └── models.py            # Subscription, Invoice, Payment
│   └── bot/                     # Webhook Telegram
│
├── database/
│   └── schema.sql               # Schéma PostgreSQL complet
│
└── docker/
    └── docker-compose.yml       # Déploiement Docker
```

---

## ⚙️ Configuration

Éditez le fichier `.env` :

```bash
# Minimum pour commencer :
TELEGRAM_BOT_TOKEN=votre-token-botfather
EMAIL_HOST_USER=votre@gmail.com
EMAIL_HOST_PASSWORD=votre-mot-de-passe-app
```

---

## 🤖 Lancer le Bot Telegram

```bash
# Après avoir mis votre TOKEN dans .env
python manage.py setup_telegram
```

---

## ⚡ Lancer la surveillance automatique

```bash
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Worker Celery
celery -A config worker -l info -Q monitoring,alerts

# Terminal 3 — Scheduler (toutes les 60s)
celery -A config beat -l info
```

---

## 🐳 Déploiement Docker (production)

```bash
cp docker/docker-compose.yml docker-compose.yml
cp .env.example .env
# Remplir .env avec les vraies valeurs
docker compose up -d
```

---

## 🌐 URLs disponibles

| URL | Description |
|-----|-------------|
| `http://localhost:8000/admin` | Administration Django |
| `http://localhost:8000/api/docs` | Documentation API Swagger |
| `http://localhost:8000/api/auth/register/` | Inscription |
| `http://localhost:8000/api/auth/login/` | Connexion JWT |
| `http://localhost:8000/api/monitoring/centers/` | Centres visa |
| `http://localhost:8000/api/monitoring/slots/` | Créneaux disponibles |
| `http://localhost:8000/api/monitoring/requests/` | Dossiers clients |
| `http://localhost:8000/api/alerts/` | Alertes |
| `http://localhost:8000/api/billing/subscriptions/` | Abonnements |

---

## 📬 Compte admin par défaut

| Champ | Valeur |
|-------|--------|
| Email | `admin@visatrack.app` |
| Mot de passe | `Admin@1234` |

> ⚠️ **Changez ce mot de passe en production !**

---

## 📋 Plans tarifaires

| Plan | Prix | Alertes | Canaux |
|------|------|---------|--------|
| Free | Gratuit | Délai 10 min | Email seulement |
| Premium | 9 900 FCFA/mois | Instantanées | Telegram + Email |
| VIP | 24 900 FCFA/mois | Instantanées + Agent | Tous canaux |
