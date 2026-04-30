# apps/bot/management/commands/setup_telegram.py
import os
import httpx
from django.core.management.base import BaseCommand

TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
SECRET      = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


class Command(BaseCommand):
    help = "Configure le webhook Telegram et les commandes du bot"

    def handle(self, *args, **kwargs):
        if not TOKEN:
            self.stdout.write(self.style.ERROR("✗ TELEGRAM_BOT_TOKEN non configuré dans .env"))
            return

        # 1. Enregistrer le webhook
        resp = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            json={
                "url":              WEBHOOK_URL,
                "secret_token":     SECRET,
                "allowed_updates":  ["message", "callback_query"],
                "drop_pending_updates": True,
            },
        )
        data = resp.json()
        if data.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"✓ Webhook enregistré : {WEBHOOK_URL}"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Webhook error: {data}"))

        # 2. Définir les commandes dans le menu
        commands = [
            {"command": "start",       "description": "Menu principal"},
            {"command": "dossiers",    "description": "Mes dossiers actifs"},
            {"command": "alertes",     "description": "Historique des alertes"},
            {"command": "abonnement",  "description": "Gérer mon abonnement"},
            {"command": "lier",        "description": "Lier mon compte VisaTrack"},
            {"command": "help",        "description": "Aide"},
        ]
        resp2 = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/setMyCommands",
            json={"commands": commands},
        )
        if resp2.json().get("ok"):
            self.stdout.write(self.style.SUCCESS("✓ Commandes du bot enregistrées"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Commands error: {resp2.json()}"))

        # 3. Info du bot
        me = httpx.get(f"https://api.telegram.org/bot{TOKEN}/getMe").json()
        if me.get("ok"):
            bot = me["result"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Bot prêt : @{bot['username']} (ID: {bot['id']})"
                )
            )
