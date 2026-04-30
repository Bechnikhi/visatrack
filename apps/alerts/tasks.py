# apps/alerts/tasks.py
"""
Moteur d'envoi d'alertes multi-canal.
Quand un nouveau créneau est détecté, dispatch_alerts_for_slot() :
  1. Trouve tous les dossiers actifs correspondants
  2. Pour chaque utilisateur concerné, crée une Alert en base
  3. Envoie via le canal préféré (Telegram prioritaire pour VIP/Premium)
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.monitoring.models import AppointmentSlot, VisaRequest
from .models import Alert, NotificationPreference
from .channels.telegram import send_telegram_alert
from .channels.email import send_email_alert
from .channels.whatsapp import send_whatsapp_alert

logger = logging.getLogger(__name__)

PLAN_CHANNELS = {
    "vip":     ["telegram", "email", "whatsapp"],
    "premium": ["telegram", "email"],
    "free":    ["email"],
}


# ──────────────────────────────────────────────
# DISPATCH : 1 créneau → N alertes
# ──────────────────────────────────────────────

@shared_task(name="alerts.dispatch_for_slot", bind=True, max_retries=2)
def dispatch_alerts_for_slot(self, slot_id: int):
    """
    Pour un créneau donné, trouve les dossiers clients correspondants
    et envoie les alertes appropriées.
    """
    try:
        slot = AppointmentSlot.objects.select_related(
            "center", "center__country", "visa_type"
        ).get(id=slot_id)
    except AppointmentSlot.DoesNotExist:
        logger.error(f"[alerts] Créneau {slot_id} introuvable")
        return

    # Trouver les dossiers actifs qui correspondent à ce créneau
    matching_requests = VisaRequest.objects.filter(
        center=slot.center,
        status="active",
        desired_date_from__lte=slot.slot_date,
    ).filter(
        # Date fin optionnelle
        **{} if not slot.slot_date else {"desired_date_to__gte": slot.slot_date}
    ).select_related(
        "user", "user__notificationpreference"
    ).order_by(
        # VIP et premium d'abord
        "-user__plan",
        "created_at",  # les plus anciens dossiers en premier
    )

    alerts_created = 0
    for req in matching_requests:
        user = req.user
        channels = _get_channels_for_user(user)

        for channel in channels:
            # Éviter les doublons : pas plus d'1 alerte par créneau/user/canal dans les 30 min
            recent = Alert.objects.filter(
                user=user,
                slot=slot,
                channel=channel,
                created_at__gte=timezone.now() - timedelta(minutes=30),
            ).exists()

            if recent:
                continue

            message = _build_message(slot, user.plan)
            alert = Alert.objects.create(
                user=req.user,
                request=req,
                slot=slot,
                channel=channel,
                message=message,
            )
            # Envoyer immédiatement pour VIP/Premium, avec délai pour Free
            delay = 0 if user.plan in ("vip", "premium") else 600  # 10min pour free
            send_alert.apply_async(args=[alert.id], countdown=delay, queue="alerts")
            alerts_created += 1

    # Mettre à jour le statut du dossier si c'est le premier créneau trouvé
    if alerts_created > 0:
        VisaRequest.objects.filter(
            center=slot.center, status="active"
        ).update(status="slot_found", slot_found_at=timezone.now())

    logger.info(f"[alerts] Créneau {slot_id} → {alerts_created} alertes créées")
    return {"alerts_created": alerts_created}


# ──────────────────────────────────────────────
# ENVOI INDIVIDUEL D'ALERTE
# ──────────────────────────────────────────────

@shared_task(name="alerts.send_alert", bind=True, max_retries=3, default_retry_delay=60)
def send_alert(self, alert_id: str):
    """Envoie une alerte via son canal. Retry automatique en cas d'échec."""
    try:
        alert = Alert.objects.select_related("user", "slot__center__country").get(id=alert_id)
    except Alert.DoesNotExist:
        return

    if alert.status == "sent":
        return  # déjà envoyée

    try:
        if alert.channel == "telegram":
            send_telegram_alert(alert)
        elif alert.channel == "email":
            send_email_alert(alert)
        elif alert.channel == "whatsapp":
            send_whatsapp_alert(alert)
        else:
            raise ValueError(f"Canal inconnu: {alert.channel}")

        alert.status = "sent"
        alert.sent_at = timezone.now()
        alert.save(update_fields=["status", "sent_at"])
        logger.info(f"[alerts] ✓ Alert {alert_id} envoyée via {alert.channel}")

    except Exception as exc:
        alert.retry_count += 1
        alert.error_message = str(exc)[:500]
        alert.status = "failed"
        alert.save(update_fields=["retry_count", "error_message", "status"])
        logger.warning(f"[alerts] ✗ Échec {alert.channel} (essai {alert.retry_count}): {exc}")

        if alert.retry_count < alert.max_retries:
            raise self.retry(exc=exc, countdown=60 * alert.retry_count)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _get_channels_for_user(user) -> list[str]:
    """Retourne la liste des canaux actifs selon le plan et les préférences."""
    plan_channels = PLAN_CHANNELS.get(user.plan, ["email"])

    try:
        prefs = user.notificationpreference
        active = []
        if "telegram" in plan_channels and prefs.telegram_enabled and user.telegram_chat_id:
            active.append("telegram")
        if "email" in plan_channels and prefs.email_enabled and user.email:
            active.append("email")
        if "whatsapp" in plan_channels and prefs.whatsapp_enabled and user.whatsapp_number:
            active.append("whatsapp")
        return active or ["email"]
    except AttributeError:
        # Pas de préférences → fallback sur les canaux du plan
        return plan_channels


def _build_message(slot: AppointmentSlot, plan: str) -> str:
    """Construit le message d'alerte selon le créneau et le plan."""
    center    = slot.center
    country   = center.country
    slot_date = slot.slot_date.strftime("%d %B %Y")
    slot_time = slot.slot_time.strftime("%H:%M") if slot.slot_time else "Horaire à confirmer"

    base = (
        f"🚨 *CRÉNEAU DISPONIBLE* 🚨\n\n"
        f"🌍 *Destination* : {country.flag_emoji} {country.name_fr}\n"
        f"🏢 *Centre* : {center.platform} {center.city}\n"
        f"📅 *Date* : {slot_date}\n"
        f"🕐 *Heure* : {slot_time}\n"
        f"💺 *Places* : {slot.available_seats}\n\n"
        f"🔗 Réserver : {center.url_booking}"
    )

    if plan == "vip":
        base += "\n\n⭐ *Votre agent VIP vous contacte sous 5 minutes.*"
    elif plan == "premium":
        base += "\n\n⚡ Alerte Premium – Soyez rapide, les créneaux partent vite !"
    else:
        base += "\n\n💡 Passez Premium pour des alertes en temps réel !"

    return base
