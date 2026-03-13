from __future__ import annotations
from datetime import datetime, date

TURKISH_MONTHS = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

TURKISH_DAYS = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
]


def today_str() -> str:
    return date.today().isoformat()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_turkish_date(d: date | None = None) -> str:
    if d is None:
        d = date.today()
    day_name = TURKISH_DAYS[d.weekday()]
    return f"{d.day} {TURKISH_MONTHS[d.month]} {d.year}, {day_name}"


def format_timestamp() -> str:
    return datetime.now().isoformat()
