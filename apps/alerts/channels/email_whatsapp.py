# apps/alerts/channels/email.py
"""Canal d'alerte Email — Django + SMTP."""

import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email_alert(alert) -> None:
    """Envoie une alerte par email avec template HTML."""
    user = alert.user
    slot = alert.slot

    if not user.email:
        raise ValueError(f"Pas d'email pour user {user.id}")

    subject = _build_subject(slot)
    context = {
        "user": user,
        "slot": slot,
        "alert": alert,
        "center": slot.center,
        "country": slot.center.country,
        "booking_url": slot.center.url_booking,
        "slot_date": slot.slot_date.strftime("%d %B %Y"),
        "slot_time": slot.slot_time.strftime("%H:%M") if slot.slot_time else "À confirmer",
        "unsubscribe_url": f"{settings.SITE_URL}/unsubscribe/{user.id}",
        "dashboard_url": f"{settings.SITE_URL}/dashboard",
    }

    html_body = render_to_string("alerts/email_alert.html", context)
    text_body = render_to_string("alerts/email_alert.txt", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        reply_to=["support@visatrack.app"],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    logger.info(f"[email] Alerte envoyée à {user.email} – {slot}")


def _build_subject(slot) -> str:
    flag   = slot.center.country.flag_emoji
    pays   = slot.center.country.name_fr
    ville  = slot.center.city
    date   = slot.slot_date.strftime("%d %b")
    return f"🚨 Créneau disponible {flag} {pays} – {ville} – {date}"


# ─────────────────────────────────────────────────────────
# Template HTML inline (pour éviter de dépendre des fichiers)
# En production, placer dans templates/alerts/email_alert.html
# ─────────────────────────────────────────────────────────

EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Créneau disponible</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f4f4f5; margin: 0; padding: 24px 0; }
  .container { max-width: 520px; margin: 0 auto; background: #fff;
               border-radius: 12px; overflow: hidden;
               box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  .header { background: #0A1628; padding: 28px 32px; text-align: center; }
  .header h1 { color: #fff; font-size: 22px; margin: 0; font-weight: 700; }
  .header p  { color: #7B8DB0; font-size: 13px; margin: 6px 0 0; }
  .badge { display: inline-block; background: #00C6A7;
           color: #fff; font-size: 11px; font-weight: 700;
           padding: 4px 10px; border-radius: 20px; margin-top: 12px; }
  .body { padding: 28px 32px; }
  .slot-card { background: #F0F9FF; border: 2px solid #1B4FD8;
               border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .slot-row { display: flex; align-items: center; gap: 10px;
              padding: 6px 0; font-size: 14px; color: #1a1a2e; }
  .slot-row .icon { font-size: 20px; width: 28px; }
  .slot-row strong { font-weight: 600; }
  .cta { display: block; background: #1B4FD8; color: #fff;
         text-align: center; padding: 14px 24px; border-radius: 8px;
         text-decoration: none; font-weight: 600; font-size: 15px;
         margin: 20px 0; }
  .cta:hover { background: #1544C0; }
  .warning { background: #FFF7ED; border-left: 3px solid #F5A623;
             padding: 12px 16px; border-radius: 4px;
             font-size: 13px; color: #92400e; margin-bottom: 16px; }
  .footer { padding: 20px 32px; border-top: 1px solid #f0f0f0;
            font-size: 12px; color: #888; text-align: center; }
  .footer a { color: #1B4FD8; text-decoration: none; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🚨 Créneau Disponible !</h1>
    <p>VisaTrack a détecté une place libre</p>
    <span class="badge">ALERTE IMMÉDIATE</span>
  </div>
  <div class="body">
    <p style="font-size:15px;color:#333;margin:0 0 16px">
      Bonjour <strong>{{ user.full_name }}</strong>,<br>
      Une place vient de se libérer pour votre dossier.
      Réservez <strong>maintenant</strong>, les créneaux partent très vite !
    </p>

    <div class="slot-card">
      <div class="slot-row"><span class="icon">{{ country.flag_emoji }}</span>
        <span><strong>Destination</strong> : {{ country.name_fr }}</span></div>
      <div class="slot-row"><span class="icon">🏢</span>
        <span><strong>Centre</strong> : {{ center.platform }} {{ center.city }}</span></div>
      <div class="slot-row"><span class="icon">📅</span>
        <span><strong>Date</strong> : {{ slot_date }}</span></div>
      <div class="slot-row"><span class="icon">🕐</span>
        <span><strong>Heure</strong> : {{ slot_time }}</span></div>
      <div class="slot-row"><span class="icon">💺</span>
        <span><strong>Places dispo</strong> : {{ slot.available_seats }}</span></div>
    </div>

    <div class="warning">
      ⚡ <strong>Attention :</strong> Ce créneau peut disparaître en quelques minutes.
      Réservez immédiatement !
    </div>

    <a href="{{ booking_url }}" class="cta">
      👉 Réserver ce créneau maintenant
    </a>

    <p style="font-size:13px;color:#666;text-align:center">
      Ou gérez votre dossier sur
      <a href="{{ dashboard_url }}" style="color:#1B4FD8">votre espace VisaTrack</a>
    </p>
  </div>
  <div class="footer">
    Vous recevez cet email car vous avez un dossier actif sur VisaTrack.<br>
    <a href="{{ unsubscribe_url }}">Se désabonner</a> · visatrack.app
  </div>
</div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────
# apps/alerts/channels/whatsapp.py
# ─────────────────────────────────────────────────────────

import httpx
import os


def send_whatsapp_alert(alert) -> None:
    """
    Envoie un message WhatsApp via l'API Meta WhatsApp Business.
    Nécessite un template de message approuvé dans Meta Business Manager.
    Template name : visa_slot_alert_v1
    """
    user = alert.user
    slot = alert.slot

    if not user.whatsapp_number:
        raise ValueError(f"Pas de numéro WhatsApp pour user {user.id}")

    phone = user.whatsapp_number.replace("+", "").replace(" ", "")

    ACCESS_TOKEN   = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    PHONE_ID       = os.environ.get("WHATSAPP_PHONE_ID", "")
    TEMPLATE_NAME  = "visa_slot_alert_v1"
    TEMPLATE_LANG  = "fr"

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANG},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": slot.center.country.name_fr},
                        {"type": "text", "text": f"{slot.center.platform} {slot.center.city}"},
                        {"type": "text", "text": slot.slot_date.strftime("%d/%m/%Y")},
                        {"type": "text", "text": slot.slot_time.strftime("%H:%M") if slot.slot_time else "–"},
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": slot.center.url_booking}],
                },
            ],
        },
    }

    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"WhatsApp API error: {data['error']}")
