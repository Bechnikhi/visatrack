# apps/alerts/channels/telegram.py  +  apps/bot/telegram_bot.py
# ============================================================
#  VisaTrack — Bot Telegram complet
#  Bibliothèque : python-telegram-bot v20+ (async)
# ============================================================

"""
Ce fichier contient :
  1. send_telegram_alert()     — envoi d'alertes depuis Celery
  2. VisaTrackBot              — bot interactif (commandes utilisateur)
  3. Webhook handler Django    — réception des updates Telegram
"""

import logging
import os
from functools import wraps

import httpx
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")


# ──────────────────────────────────────────────
# 1. ENVOI D'ALERTES (appelé par Celery)
# ──────────────────────────────────────────────

def send_telegram_alert(alert) -> None:
    """
    Envoie un message Telegram pour une alerte.
    Appelé de manière synchrone depuis la tâche Celery send_alert().
    """
    if not alert.user.telegram_chat_id:
        raise ValueError(f"Pas de telegram_chat_id pour user {alert.user.id}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Réserver maintenant", url=alert.slot.center.url_booking)],
        [
            InlineKeyboardButton("✅ Créneau pris", callback_data=f"booked_{alert.slot.id}"),
            InlineKeyboardButton("🔕 Désactiver alerte", callback_data=f"stop_{alert.request.id}"),
        ],
    ])

    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": alert.user.telegram_chat_id,
                "text": alert.message,
                "parse_mode": "Markdown",
                "reply_markup": keyboard.to_dict(),
                "disable_web_page_preview": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data.get('description')}")


# ──────────────────────────────────────────────
# 2. BOT INTERACTIF
# ──────────────────────────────────────────────

# États de la conversation /nouveau_dossier
(
    ASK_COUNTRY,
    ASK_CENTER,
    ASK_DATE_FROM,
    ASK_DATE_TO,
    ASK_PLAN,
    CONFIRM,
) = range(6)


def require_linked_account(func):
    """Décorateur : refuse si le compte n'est pas lié à VisaTrack."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        chat_id = update.effective_user.id
        user = User.objects.filter(telegram_chat_id=chat_id, is_active=True).first()
        if not user:
            await update.message.reply_text(
                "❌ Votre compte n'est pas lié.\n"
                "Connectez-vous sur *visatrack.app* et liez votre Telegram dans Paramètres.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        context.user_data["db_user"] = user
        return await func(update, context)
    return wrapper


# ── /start ───────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📁 Mes dossiers"), KeyboardButton("🔔 Mes alertes")],
            [KeyboardButton("💳 Mon abonnement"), KeyboardButton("ℹ️ Aide")],
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        f"👋 Bienvenue sur *VisaTrack*, {user.first_name} !\n\n"
        "Je surveille les créneaux visa et vous alerte dès qu'une place se libère.\n\n"
        "📌 *Commandes disponibles :*\n"
        "/start – Menu principal\n"
        "/dossiers – Voir vos dossiers actifs\n"
        "/alertes – Historique des alertes\n"
        "/nouveau – Créer un dossier de surveillance\n"
        "/abonnement – Gérer votre plan\n"
        "/lier – Lier votre compte VisaTrack\n"
        "/help – Aide",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ── /lier ────────────────────────────────────

async def cmd_lier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """L'utilisateur envoie son token de liaison depuis le site."""
    await update.message.reply_text(
        "🔗 Pour lier votre compte VisaTrack :\n\n"
        "1. Connectez-vous sur *visatrack.app*\n"
        "2. Allez dans ⚙️ *Paramètres → Telegram*\n"
        "3. Copiez votre code de liaison\n"
        "4. Envoyez-le ici avec la commande : `/lier VOTRE_CODE`",
        parse_mode=ParseMode.MARKDOWN,
    )

    if context.args:
        token = context.args[0].strip()
        await _process_link_token(update, token)


async def _process_link_token(update: Update, token: str):
    """Vérifie le token et lie le compte."""
    import hashlib
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    User = get_user_model()
    cache_key = f"telegram_link_token:{token}"
    user_id = cache.get(cache_key)

    if not user_id:
        await update.message.reply_text(
            "❌ Code invalide ou expiré.\n"
            "Générez un nouveau code depuis votre espace VisaTrack.",
        )
        return

    user = User.objects.filter(id=user_id).first()
    if not user:
        await update.message.reply_text("❌ Compte introuvable.")
        return

    user.telegram_chat_id = update.effective_user.id
    user.save(update_fields=["telegram_chat_id"])
    cache.delete(cache_key)

    await update.message.reply_text(
        f"✅ Compte *{user.email}* lié avec succès !\n\n"
        f"Plan actuel : *{user.plan.upper()}*\n"
        "Vous recevrez désormais les alertes ici. 🎉",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /dossiers ────────────────────────────────

@require_linked_account
async def cmd_dossiers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.monitoring.models import VisaRequest
    user = context.user_data["db_user"]

    requests = VisaRequest.objects.filter(
        user=user, status__in=["active", "slot_found", "booked"]
    ).select_related("center__country")[:10]

    if not requests:
        await update.message.reply_text(
            "📭 Vous n'avez aucun dossier actif.\n"
            "Créez-en un avec /nouveau"
        )
        return

    STATUS_EMOJI = {
        "active": "🔵", "slot_found": "🟡", "booked": "🟢",
        "completed": "✅", "cancelled": "❌",
    }

    lines = ["📁 *Vos dossiers actifs* :\n"]
    buttons = []

    for req in requests:
        emoji = STATUS_EMOJI.get(req.status, "⚪")
        lines.append(
            f"{emoji} {req.center.country.flag_emoji} {req.center.country.name_fr} "
            f"– {req.center.city}\n"
            f"   📅 À partir du {req.desired_date_from:%d/%m/%Y}\n"
        )
        buttons.append([
            InlineKeyboardButton(
                f"Voir dossier {req.center.country.code}",
                callback_data=f"req_{req.id}",
            )
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── /alertes ─────────────────────────────────

@require_linked_account
async def cmd_alertes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.alerts.models import Alert
    user = context.user_data["db_user"]

    alerts = Alert.objects.filter(
        user=user, status="sent"
    ).select_related("slot__center__country").order_by("-sent_at")[:5]

    if not alerts:
        await update.message.reply_text("🔕 Aucune alerte envoyée récemment.")
        return

    lines = ["🔔 *Vos dernières alertes* :\n"]
    for a in alerts:
        slot = a.slot
        if slot:
            lines.append(
                f"• {slot.center.country.flag_emoji} {slot.center.country.name_fr} "
                f"– {slot.slot_date:%d/%m/%Y} "
                f"à {slot.slot_time:%H:%M if slot.slot_time else '–'} "
                f"({a.sent_at:%d/%m %H:%M})\n"
            )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── /abonnement ──────────────────────────────

@require_linked_account
async def cmd_abonnement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data["db_user"]

    PLAN_LABELS = {"free": "Gratuit", "premium": "⚡ Premium", "vip": "⭐ VIP"}
    plan_label = PLAN_LABELS.get(user.plan, user.plan)

    expires = user.plan_expires_at
    exp_str = f"\n📆 Expire le : *{expires:%d/%m/%Y}*" if expires else ""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Gérer sur visatrack.app", url="https://visatrack.app/billing")],
    ])

    await update.message.reply_text(
        f"💳 *Votre abonnement*\n\n"
        f"Plan : *{plan_label}*{exp_str}\n\n"
        "🔗 Gérez votre abonnement depuis le site.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ── Callback queries (boutons inline) ────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("booked_"):
        slot_id = int(data.split("_", 1)[1])
        await query.edit_message_text(
            "✅ Parfait ! Dossier marqué comme réservé. Félicitations ! 🎉",
        )
        # Mettre à jour le dossier en base (via tâche Celery)
        from apps.monitoring.tasks import mark_slot_taken
        mark_slot_taken.delay(slot_id)

    elif data.startswith("stop_"):
        req_id = data.split("_", 1)[1]
        await query.edit_message_text("🔕 Surveillance désactivée pour ce dossier.")
        from apps.monitoring.models import VisaRequest
        VisaRequest.objects.filter(id=req_id).update(status="cancelled")

    elif data.startswith("req_"):
        req_id = data.split("_", 1)[1]
        from apps.monitoring.models import VisaRequest
        try:
            req = VisaRequest.objects.select_related("center__country").get(id=req_id)
            await query.edit_message_text(
                f"📁 *Dossier* {req.center.country.flag_emoji} {req.center.country.name_fr}\n"
                f"Centre : {req.center.platform} {req.center.city}\n"
                f"Statut : {req.status}\n"
                f"Priorité : {req.priority}\n"
                f"Date souhaitée : {req.desired_date_from:%d/%m/%Y}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except VisaRequest.DoesNotExist:
            await query.edit_message_text("❌ Dossier introuvable.")


# ── Message texte libre ───────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📁 Mes dossiers":
        await cmd_dossiers(update, context)
    elif text == "🔔 Mes alertes":
        await cmd_alertes(update, context)
    elif text == "💳 Mon abonnement":
        await cmd_abonnement(update, context)
    elif text == "ℹ️ Aide":
        await cmd_start(update, context)
    else:
        await update.message.reply_text(
            "Je n'ai pas compris. Utilisez les boutons du menu ou tapez /help"
        )


# ── /help ────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Aide VisaTrack Bot*\n\n"
        "Ce bot surveille les créneaux visa en temps réel et vous alerte dès qu'une place est disponible.\n\n"
        "*Commandes :*\n"
        "/start – Accueil\n"
        "/lier CODE – Lier votre compte\n"
        "/dossiers – Voir vos dossiers\n"
        "/alertes – Historique alertes\n"
        "/abonnement – Votre plan\n\n"
        "📞 Support : @visatrack_support",
        parse_mode=ParseMode.MARKDOWN,
    )


# ──────────────────────────────────────────────
# 3. CRÉATION DE L'APPLICATION BOT
# ──────────────────────────────────────────────

def create_bot_app() -> Application:
    """Crée et configure l'Application python-telegram-bot."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("lier",         cmd_lier))
    app.add_handler(CommandHandler("dossiers",     cmd_dossiers))
    app.add_handler(CommandHandler("alertes",      cmd_alertes))
    app.add_handler(CommandHandler("abonnement",   cmd_abonnement))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


# ──────────────────────────────────────────────
# 4. DJANGO VIEW : WEBHOOK HANDLER
# ──────────────────────────────────────────────

# apps/bot/views.py  (à placer dans le bon fichier Django)

import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from telegram import Update

_bot_app = None

def get_bot_app():
    global _bot_app
    if _bot_app is None:
        _bot_app = create_bot_app()
    return _bot_app


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """
    Endpoint Django qui reçoit les updates Telegram.
    URL : /api/bot/telegram/webhook/
    Enregistrer avec : bot.set_webhook(url=WEBHOOK_URL)
    """
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""):
        return HttpResponse(status=403)

    try:
        data = json.loads(request.body)
        update = Update.de_json(data, get_bot_app().bot)

        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(get_bot_app().process_update(update))
        loop.close()

    except Exception as exc:
        logger.exception(f"[telegram_webhook] Erreur: {exc}")
        return HttpResponse(status=500)

    return JsonResponse({"ok": True})


# ──────────────────────────────────────────────
# 5. MANAGEMENT COMMAND : enregistrer le webhook
# ──────────────────────────────────────────────

# apps/bot/management/commands/setup_telegram.py

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Configure le webhook Telegram et les commandes du bot"

    def handle(self, *args, **kwargs):
        import httpx

        # Enregistrer le webhook
        resp = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            json={
                "url": WEBHOOK_URL,
                "secret_token": os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True,
            },
        )
        data = resp.json()
        if data.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"✓ Webhook enregistré : {WEBHOOK_URL}"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Erreur: {data}"))

        # Définir les commandes dans le menu Telegram
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
            self.stdout.write(self.style.SUCCESS("✓ Commandes enregistrées"))
