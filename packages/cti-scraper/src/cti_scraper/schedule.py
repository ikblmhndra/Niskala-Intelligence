"""Jitter jadwal deterministik. Tanpa ini, 142 scraper RSS dengan interval
sama (mis. `*/15 * * * *`) nembak SEMUA di detik yang sama tiap 15 menit --
142 fetch keluar barengan plus 142 write Postgres barengan. `spread()`
nyebar mereka ke menit-menit di dalam window yang sama, stabil per scraper
lintas deploy (hash dari `id`, bukan random).

Bukan ide baru -- production Rundeck ternyata udah ngelakuin ini
(job aktif nembak di `:15`/`:30`/`:31`/`:46`, bukan cuma `:00`). Ini
formalisasi pola yang udah kebukti kerja, bukan penemuan.
"""

from __future__ import annotations

import hashlib
import re

_STEP_RE = re.compile(r"^\*/(\d+)$")


def spread(cron: str, key: str) -> str:
    """Ganti field MENIT `*/N` jadi `<offset>-59/N`, `offset` (0..N-1)
    dihitung dari hash `key` -- stabil per scraper, tersebar rata lintas
    scraper lain. Field jam/tanggal/bulan/hari gak disentuh.

    Field menit yang BUKAN pola `*/N` (mis. udah angka pasti "17",
    dipulihkan dari jadwal Rundeck asli) dibalikin APA ADANYA -- jangan
    maksa jitter ke jadwal yang memang udah spesifik.
    """
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"cron harus 5 field (menit jam tanggal bulan hari), dapet: '{cron}'")

    match = _STEP_RE.match(parts[0])
    if not match:
        return cron

    step = int(match.group(1))
    if not (0 < step <= 60):
        raise ValueError(f"step menit gak valid di '{cron}': {step}")

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:4], "big") % step

    parts[0] = f"{offset}-59/{step}"
    return " ".join(parts)
