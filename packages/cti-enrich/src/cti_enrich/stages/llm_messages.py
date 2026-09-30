"""Bentuk pesan LLM buat stage yang WAJIB dijawab JSON (classify, extract_ttps).

Kenapa ada dua bentuk: gateway dev (9router -> `claude-haiku-4.5` lewat
backend Kiro) sesekali njawab pakai persona -- "I'm Kiro, a development
environment assistant, not a threat intelligence analyst" atau "I'm ready to
classify, please provide a title" -- BUKAN JSON. Bergantung ke isi judul dan
gak deterministik (ketemu di e2e staging Fase 10). Dengan `temperature=0`
percobaan ulang persis sama cenderung mengulang jawaban yang sama, jadi
retry yang identik hampir gak berguna.

Diukur langsung di gateway (6 percobaan/varian, dua judul yang gagal):

    baseline (system + judul polos)               judul-1 0/6   judul-2 1/6
    + pengingat sebagai pesan user terpisah       judul-1 1/6   judul-2 6/6
    system + <tag>judul</tag> + pengingat         judul-1 6/6   judul-2 6/6   <- dipakai
    SATU pesan user (prompt+judul+pengingat)      judul-1 6/6   judul-2 6/6

Percobaan PERTAMA tetap verbatim (prompt bisnis asli, perilaku yang sudah
teruji Fase 5 gak berubah). Cuma percobaan ULANG (yang berarti percobaan
pertama sudah gagal JSON) pakai bentuk yang dikuatkan -- jadi bentuk ini
hanya bisa MENYELAMATKAN kasus gagal, gak bisa merusak yang sudah benar.
"""

from __future__ import annotations

JSON_ONLY_REMINDER = (
    "Respond ONLY with the JSON object in the required format. "
    "No prose, no questions, no introduction."
)


def build_messages(system: str, user: str, *, attempt: int, tag: str) -> list[dict[str, str]]:
    """`attempt` 0 = bentuk asli (verbatim). >= 1 = dikuatkan: input dibungkus
    tag yang jelas + pengingat "JSON saja" di pesan user yang SAMA (pengingat
    di pesan terpisah terbukti kurang ampuh)."""
    if attempt == 0:
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
    wrapped = f"<{tag}>{user}</{tag}>\n\n{JSON_ONLY_REMINDER}"
    return [{"role": "system", "content": system}, {"role": "user", "content": wrapped}]
