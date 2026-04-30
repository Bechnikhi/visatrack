# apps/bot/__init__.py
# apps/bot/models.py  (app sans modèles propres)

# apps/bot/views.py
import json, logging, os
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Reçoit les updates Telegram et les traite."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != os.environ.get("TELEGRAM_WEBHOOK_SECRET", "changeme"):
        return HttpResponse(status=403)

    try:
        from telegram import Update
        from apps.alerts.channels.telegram import get_bot_app
        data   = json.loads(request.body)
        update = Update.de_json(data, get_bot_app().bot)
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(get_bot_app().process_update(update))
        loop.close()
    except Exception as exc:
        logger.exception(f"[webhook] Erreur: {exc}")
        return HttpResponse(status=500)

    return JsonResponse({"ok": True})
