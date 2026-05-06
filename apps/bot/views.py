
import json
import logging
import os
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "changeme")


@csrf_exempt
@require_POST
def telegram_webhook(request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != WEBHOOK_SECRET:
        return HttpResponse(status=403)

    try:
        import httpx
        data = json.loads(request.body)

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")

            if text == "/start":
                message = "👋 Bienvenue sur *VisaTrack* !\n\nJe surveille les créneaux visa et vous alerte dès qu'une place se libère.\n\n📌 *Commandes :*\n/start – Menu principal\n/dossiers – Mes dossiers\n/alertes – Historique alertes\n/abonnement – Mon abonnement\n/help – Aide"
            elif text == "/help":
                message = "🆘 *Aide VisaTrack*\n\nCe bot surveille les créneaux visa automatiquement.\n\nSupport : @visatrack_support"
            elif text == "/dossiers":
                message = "📁 *Vos dossiers actifs*\n\nConnectez-vous sur votre espace VisaTrack pour voir vos dossiers."
            elif text == "/alertes":
                message = "🔔 *Vos alertes*\n\nAucune alerte récente."
            elif text == "/abonnement":
                message = "💳 *Votre abonnement*\n\nGérez votre abonnement sur visatrack-3ngv.onrender.com"
            else:
                message = "Commande non reconnue. Tapez /help pour l'aide."

            httpx.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )

    except Exception as exc:
        logger.exception(f"[webhook] Erreur: {exc}")
        return HttpResponse(status=500)

    return JsonResponse({"ok": True})