"""Konversi jadwal Rundeck (docs/legacy/rundeck-jobs-map.json) ke cron
standar 5-field buat `ScraperMeta.schedule`.

Temuan penting waktu nulis ini: Rundeck TERNYATA nyimpen menit TETAP per
job (mis. bitdefender = menit 17 tiap jam), BUKAN pola `*/N` -- staggering
antar ~48 job RSS datang dari tiap job punya menit beda, bukan dari step
interval. `spread()` (Fase 3) tetap aman dipanggil di atas hasil ini: dia
cuma ngubah pola `*/N`, cron menit-tetap dibalikin apa adanya (lihat
schedule.py) -- jadi jadwal produksi asli gak keubah.
"""

from __future__ import annotations

import json
from pathlib import Path


def build_schedule_map(rundeck_map_path: Path) -> dict[str, str]:
    """legacy_script (stem, mis. "bitdefenderThreat") -> cron 5-field."""
    jobs = json.loads(rundeck_map_path.read_text())
    out: dict[str, str] = {}
    for job in jobs:
        script = job.get("script")
        if not script:
            continue
        stem = Path(script).stem
        out[stem] = _to_cron(job["schedule"])
    return out


def _to_cron(schedule: dict[str, object]) -> str:
    time = schedule.get("time", {})
    minute = str(time.get("minute", "*"))
    hour = str(time.get("hour", "*"))
    month = str(schedule.get("month", "*"))
    weekday = schedule.get("weekday", {})
    day_of_week = str(weekday.get("day", "*")) if isinstance(weekday, dict) else "*"
    return f"{minute} {hour} * {month} {day_of_week}"


def build_enabled_map(rundeck_map_path: Path) -> dict[str, bool]:
    jobs = json.loads(rundeck_map_path.read_text())
    out: dict[str, bool] = {}
    for job in jobs:
        script = job.get("script")
        if not script:
            continue
        out[Path(script).stem] = bool(job.get("enabled"))
    return out
