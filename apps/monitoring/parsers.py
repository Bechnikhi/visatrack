# apps/monitoring/parsers.py
"""
Parseurs HTML pour chaque plateforme visa.
Chaque parseur retourne une liste standardisée de créneaux :
[{"slot_date": date, "slot_time": time|None, "available_seats": int, "raw": dict}]

NOTE : Les sélecteurs CSS/XPath sont des approximations à adapter selon
       la structure HTML réelle de chaque site (qui peut changer).
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import date, time
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# INTERFACE DE BASE
# ──────────────────────────────────────────────

class BaseParser(ABC):
    """Parseur abstrait – chaque plateforme implémente parse()."""

    @abstractmethod
    def parse(self, html: str, center) -> list[dict]:
        ...

    def _safe_parse_date(self, raw: str) -> Optional[date]:
        """Tente plusieurs formats de date fréquents."""
        raw = raw.strip()
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%B %d, %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        logger.debug(f"[parser] Date non reconnue : {raw!r}")
        return None

    def _safe_parse_time(self, raw: str) -> Optional[time]:
        """Tente plusieurs formats d'heure."""
        raw = raw.strip()
        for fmt in ["%H:%M", "%H:%M:%S", "%I:%M %p"]:
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        return None


# ──────────────────────────────────────────────
# BLS INTERNATIONAL
# ──────────────────────────────────────────────

class BLSParser(BaseParser):
    """
    BLS affiche généralement un calendrier avec des cellules cliquables.
    Sélecteur typique : table.calendar td.available
    """

    def parse(self, html: str, center) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        slots = []

        # Recherche d'un calendrier type BLS
        available_cells = soup.select("td.available, td[data-available='true'], .slot-available")

        for cell in available_cells:
            raw_date = (
                cell.get("data-date")
                or cell.get("data-value")
                or cell.get_text(strip=True)
            )
            slot_date = self._safe_parse_date(raw_date) if raw_date else None
            if not slot_date:
                continue

            # Cherche les horaires dans la cellule ou ses enfants
            time_tags = cell.select(".slot-time, span.time, li.time")
            if time_tags:
                for t_tag in time_tags:
                    slot_time = self._safe_parse_time(t_tag.get_text(strip=True))
                    slots.append({
                        "slot_date": slot_date,
                        "slot_time": slot_time,
                        "available_seats": 1,
                        "raw": {"html": str(cell)[:500]},
                    })
            else:
                slots.append({
                    "slot_date": slot_date,
                    "slot_time": None,
                    "available_seats": int(cell.get("data-seats", 1) or 1),
                    "raw": {"html": str(cell)[:500]},
                })

        # Fallback : cherche des dates en texte brut si rien trouvé
        if not slots:
            slots = self._fallback_text_parse(soup)

        logger.debug(f"[BLS] {len(slots)} créneaux parsés")
        return slots

    def _fallback_text_parse(self, soup: BeautifulSoup) -> list[dict]:
        """Cherche des patterns de date dans le texte de la page."""
        text = soup.get_text()
        date_pattern = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\b")
        found = []
        for match in date_pattern.finditer(text):
            d = self._safe_parse_date(match.group(1))
            if d:
                found.append({"slot_date": d, "slot_time": None, "available_seats": 1, "raw": {}})
        return found[:20]  # limiter pour éviter les faux positifs


# ──────────────────────────────────────────────
# TLSCONTACT
# ──────────────────────────────────────────────

class TLSParser(BaseParser):
    """
    TLScontact utilise souvent une API JSON ou un formulaire React.
    L'URL /api/slots ou /api/availability retourne du JSON.
    On scrappe le HTML initial pour trouver les données embarquées.
    """

    def parse(self, html: str, center) -> list[dict]:
        # Cherche les données JSON embarquées dans le HTML (pattern React/Next.js)
        json_data = self._extract_json_data(html)
        if json_data:
            return self._parse_json(json_data)

        # Fallback HTML
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_html(soup)

    def _extract_json_data(self, html: str) -> Optional[list]:
        """Cherche __NEXT_DATA__ ou window.__STATE__ dans le HTML."""
        import json

        patterns = [
            r'window\.__STATE__\s*=\s*({.+?});\s*</script>',
            r'"slots"\s*:\s*(\[.+?\])',
            r'"availabilities"\s*:\s*(\[.+?\])',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None

    def _parse_json(self, data: list | dict) -> list[dict]:
        slots = []
        items = data if isinstance(data, list) else data.get("slots", data.get("items", []))
        for item in items:
            raw_date = item.get("date") or item.get("slotDate") or item.get("day")
            raw_time = item.get("time") or item.get("slotTime") or item.get("hour")
            seats    = item.get("available") or item.get("seats") or item.get("capacity") or 1

            slot_date = self._safe_parse_date(str(raw_date)) if raw_date else None
            if not slot_date:
                continue

            slots.append({
                "slot_date": slot_date,
                "slot_time": self._safe_parse_time(str(raw_time)) if raw_time else None,
                "available_seats": int(seats),
                "raw": item,
            })
        return slots

    def _parse_html(self, soup: BeautifulSoup) -> list[dict]:
        slots = []
        # TLS utilise des classes comme .appointment-slot ou .time-slot
        for slot_el in soup.select(".appointment-slot, .time-slot, [data-slot-date]"):
            raw_date = slot_el.get("data-slot-date") or slot_el.get("data-date")
            raw_time = slot_el.get("data-slot-time") or slot_el.get("data-time")
            slot_date = self._safe_parse_date(raw_date) if raw_date else None
            if slot_date:
                slots.append({
                    "slot_date": slot_date,
                    "slot_time": self._safe_parse_time(raw_time) if raw_time else None,
                    "available_seats": 1,
                    "raw": {"el": str(slot_el)[:300]},
                })
        return slots


# ──────────────────────────────────────────────
# VFS GLOBAL
# ──────────────────────────────────────────────

class VFSParser(BaseParser):
    """
    VFS utilise souvent un calendrier AngularJS ou une grille Bootstrap.
    """

    def parse(self, html: str, center) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        slots = []

        # VFS Angular : cherche ng-repeat ou data-ng-* attributes
        for el in soup.select("[ng-repeat], .vfs-slot, .available-date, td.day.available"):
            raw_date = (
                el.get("data-date")
                or el.get("ng-click", "").replace("selectDate('", "").replace("')", "")
                or el.get_text(strip=True)
            )
            slot_date = self._safe_parse_date(raw_date) if raw_date else None
            if not slot_date:
                continue

            # Cherche les plages horaires
            for time_el in el.select(".slot, .timeslot") or [el]:
                raw_time = time_el.get("data-time") or time_el.get_text(strip=True)
                slots.append({
                    "slot_date": slot_date,
                    "slot_time": self._safe_parse_time(raw_time),
                    "available_seats": int(el.get("data-capacity", 1) or 1),
                    "raw": {"html": str(el)[:400]},
                })

        logger.debug(f"[VFS] {len(slots)} créneaux parsés")
        return slots


# ──────────────────────────────────────────────
# FACTORY
# ──────────────────────────────────────────────

_PARSERS: dict[str, BaseParser] = {
    "BLS":       BLSParser(),
    "TLScontact": TLSParser(),
    "VFS":       VFSParser(),
}


def get_parser(platform: str) -> BaseParser:
    parser = _PARSERS.get(platform)
    if not parser:
        raise ValueError(f"Aucun parseur disponible pour la plateforme : {platform!r}")
    return parser
