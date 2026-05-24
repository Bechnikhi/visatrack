# apps/monitoring/tasks.py
import logging
import time
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import AppointmentSlot, MonitoringLog, VisaCenter
from .parsers import get_parser

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# TÂCHE PRINCIPALE : orchestration
# ──────────────────────────────────────────────

@shared_task(name="monitoring.check_all_centers", bind=True, max_retries=1)
def check_all_centers(self):
    now = timezone.now()
    centers = VisaCenter.objects.filter(is_active=True).select_related("country")

    launched = 0
    for center in centers:
        if _should_check(center, now):
            check_center.apply_async(
                args=[center.id],
                queue="monitoring",
                priority=9 if center.check_interval <= 2 else 5,
            )
            launched += 1

    logger.info(f"[monitoring] {launched} tâches lancées sur {centers.count()} centres")
    return {"launched": launched}


def _should_check(center: VisaCenter, now: datetime) -> bool:
    if not center.last_checked_at:
        return True
    elapsed = (now - center.last_checked_at).total_seconds() / 60
    return elapsed >= center.check_interval


# ──────────────────────────────────────────────
# TÂCHE INDIVIDUELLE : 1 centre
# ──────────────────────────────────────────────

@shared_task(
    name="monitoring.check_center",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=90,
)
def check_center(self, center_id: int):
    try:
        center = VisaCenter.objects.select_related("country").get(id=center_id)
    except VisaCenter.DoesNotExist:
        logger.error(f"[monitoring] Centre {center_id} introuvable")
        return

    log_data = {"center": center, "success": False}
    t_start = time.monotonic()

    try:
        slots_raw = _fetch_slots(center)
        duration_ms = int((time.monotonic() - t_start) * 1000)

        new_slots = _persist_slots(center, slots_raw)

        log_data.update({
            "success": True,
            "duration_ms": duration_ms,
            "slots_found": len(slots_raw),
            "slots_new": len(new_slots),
        })

        VisaCenter.objects.filter(id=center_id).update(last_checked_at=timezone.now())

        for slot in new_slots:
            from apps.alerts.tasks import dispatch_alerts_for_slot
            dispatch_alerts_for_slot.apply_async(
                args=[slot.id],
                queue="alerts",
                priority=9,
            )

        logger.info(
            f"[{center.platform}] {center.city} – "
            f"{len(slots_raw)} créneaux, {len(new_slots)} nouveaux ({duration_ms}ms)"
        )

    except httpx.TimeoutException as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        log_data.update({"duration_ms": duration_ms, "error_message": f"Timeout: {exc}"})
        logger.warning(f"[monitoring] Timeout sur {center} – retry {self.request.retries}")
        raise self.retry(exc=exc)

    except httpx.HTTPStatusError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        log_data.update({
            "duration_ms": duration_ms,
            "http_status": exc.response.status_code,
            "error_message": str(exc),
        })
        logger.error(f"[monitoring] HTTP {exc.response.status_code} sur {center}")

    except Exception as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        log_data.update({"duration_ms": duration_ms, "error_message": str(exc)})
        logger.exception(f"[monitoring] Erreur inattendue sur {center}")
        raise self.retry(exc=exc)

    finally:
        MonitoringLog.objects.create(**log_data)


# ──────────────────────────────────────────────
# SCRAPING HTTP
# ──────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _fetch_slots(center: VisaCenter) -> list[dict]:
    parser = get_parser(center.platform)

    with httpx.Client(
        headers=HEADERS,
        timeout=httpx.Timeout(connect=10, read=20, write=10, pool=5),
        follow_redirects=True,
        http2=False,
    ) as client:
        url = center.url_check or center.url_booking
        response = client.get(url)
        response.raise_for_status()

    return parser.parse(response.text, center)


# ──────────────────────────────────────────────
# PERSISTANCE DES CRÉNEAUX
# ──────────────────────────────────────────────

def _persist_slots(center: VisaCenter, slots_raw: list[dict]) -> list[AppointmentSlot]:
    new_slots = []
    today = date.today()

    with transaction.atomic():
        for slot_data in slots_raw:
            slot_date = slot_data.get("slot_date")
            slot_time = slot_data.get("slot_time")

            if slot_date and slot_date < today:
                continue

            slot, created = AppointmentSlot.objects.get_or_create(
                center=center,
                slot_date=slot_date,
                slot_time=slot_time,
                defaults={
                    "available_seats": slot_data.get("available_seats", 1),
                    "status": "available",
                    "raw_data": slot_data.get("raw", {}),
                },
            )

            if created:
                new_slots.append(slot)
            else:
                if slot.status == "taken":
                    slot.status = "available"
                    slot.taken_at = None
                    slot.save(update_fields=["status", "taken_at", "last_seen_at"])
                    new_slots.append(slot)
                else:
                    slot.save(update_fields=["last_seen_at"])

        current_keys = {
            (s.get("slot_date"), s.get("slot_time")) for s in slots_raw
        }
        center.slots.filter(status="available").exclude(
            slot_date__in=[k[0] for k in current_keys]
        ).update(status="taken", taken_at=timezone.now())

    return new_slots


# ──────────────────────────────────────────────
# TÂCHE DE NETTOYAGE
# ──────────────────────────────────────────────

@shared_task(name="monitoring.cleanup_old_slots")
def cleanup_old_slots():
    cutoff = timezone.now() - timezone.timedelta(days=30)
    deleted_slots, _ = AppointmentSlot.objects.filter(slot_date__lt=date.today() - timezone.timedelta(days=1)).delete()
    deleted_logs, _ = MonitoringLog.objects.filter(checked_at__lt=cutoff).delete()
    logger.info(f"[cleanup] {deleted_slots} créneaux, {deleted_logs} logs supprimés")
    return {"slots": deleted_slots, "logs": deleted_logs}


@shared_task(name="monitoring.mark_slot_taken")
def mark_slot_taken(slot_id: int):
    AppointmentSlot.objects.filter(id=slot_id).update(
        status="taken", taken_at=timezone.now()
    )
