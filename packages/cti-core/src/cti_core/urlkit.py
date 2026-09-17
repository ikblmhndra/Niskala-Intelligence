"""Normalisasi URL -- fondasi dedup artikel.

Menggantikan `is_new_and_mark(script, str(title)+str(url))` di
`ScraperNews/modules/offsetStore.py`, yang punya tiga cacat (lihat plan §2 /
§3): key mentah tanpa normalisasi (titik koma di judul = repost), namespace
per-script (dua scraper yang liput situs sama dedup dua kali), dan
di-mark SEBELUM diproses (kegagalan downstream = artikel hilang permanen).

Modul ini cuma ngurusin bagian normalisasi identitas URL. Reservasi
dua-fase (mark-setelah-sukses) itu tanggung jawab `cti_scraper.dedup`
(Fase 3) -- di sana urusannya nge-lease per scraper_id, di sini urusannya
"dua URL ini merujuk dokumen yang sama atau bukan".

Basis tracking-param list diambil dari satu-satunya implementasi yang ada
di kedua repo lama: `ScraperNewsWeb/insert_to_mongo.py:14-24`.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = frozenset(
    [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "utm_reader",
        "fbclid",
        "gclid",
        "gbraid",
        "wbraid",
        "msclkid",
        "dclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "referrer",
        "source",
        "_hsenc",
        "_hsmi",
        "vero_id",
        "yclid",
        "ck_subscriber_id",
    ]
)

# Port yang gak perlu ditulis eksplisit -- http dan https diperlakukan sebagai
# skema yang SAMA buat keperluan identitas (lihat canonicalize_url), jadi
# default port dua-duanya didrop.
_DEFAULT_PORTS = frozenset({80, 443})


def canonicalize_url(url: str) -> str:
    """Normalisasi URL jadi string identitas yang stabil.

    Aturan (lihat test_urlkit.py buat tabel lengkap ~60 kasus):
      - scheme  -> selalu "https" (http/https dianggap dokumen yang sama)
      - host    -> lowercase, strip satu "www." di depan, strip titik di akhir
      - port    -> didrop kalau 80/443 atau gak ada; port lain dipertahankan
      - path    -> di-decode lalu di-encode ulang secara konsisten; SATU
                   trailing slash dibuang (tapi root "/" tetap "/"); path
                   kosong dianggap "/"
      - query   -> tracking param (TRACKING_PARAMS) dibuang, sisanya
                   diurutkan berdasarkan key lalu value; query yang isinya
                   cuma tracking param jadi hilang total
      - fragment -> dibuang, KECUALI pola hashbang ("#!...", dipakai
                   beberapa SPA lama buat routing) yang dipertahankan

    Sengaja TIDAK dilakukan: follow redirect (butuh network call per item)
    atau strip "index.html" (sebagian situs nyajiin konten beda).
    """
    parts = urlsplit(url.strip())

    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in _DEFAULT_PORTS:
        host = f"{host}:{parts.port}"

    path = _canonical_path(parts.path)

    query = _canonical_query(parts.query)

    fragment = parts.fragment if parts.fragment.startswith("!") else ""

    return urlunsplit(("https", host, path, query, fragment))


def _canonical_path(raw_path: str) -> str:
    if not raw_path or raw_path == "/":
        return "/"
    # Split di '/' MENTAH dulu (sebelum decode apa pun) -- '/' literal di
    # string URL selalu pemisah segment sungguhan; kalau '/' itu bagian dari
    # DATA (bukan pemisah), sumbernya wajib nulis %2F. Decode-lalu-encode
    # ulang seluruh path sekaligus (bukan per segmen) bikin "%2F" ke-decode
    # jadi "/" lalu ketimbun "aman" oleh quote(safe="/") -- artinya segmen
    # "a%2Fb" (satu segmen, isinya karakter slash) dan "a/b" (dua segmen)
    # ke-canonicalize jadi string yang SAMA, padahal itu dua resource beda.
    # Ketauan dari test, bukan asumsi -- proses tiap segmen sendiri-sendiri.
    segments = raw_path.split("/")
    encoded = "/".join(quote(unquote(seg), safe="") for seg in segments)
    if len(encoded) > 1 and encoded.endswith("/"):
        encoded = encoded[:-1]
    return encoded


def _canonical_query(raw_query: str) -> str:
    if not raw_query:
        return ""
    pairs = [
        (k, v)
        for k, v in parse_qsl(raw_query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    return urlencode(pairs)


def url_hash(url: str) -> str:
    """SHA-256 hex digest dari `canonicalize_url(url)`.

    Fixed-width (64 hex char), aman dipakai sebagai unique key/index --
    beda dari key lama `str(title)+str(url)` yang panjangnya gak dibatasi
    dan bisa nabrak batas 1024-byte index key Mongo (itu salah satu cacat
    yang dicatat di plan §3.1).
    """
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()
