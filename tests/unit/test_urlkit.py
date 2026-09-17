"""canonicalize_url() / url_hash() -- exit criteria Fase 2: lolos tabel
~60 kasus. Dijalanin dan diverifikasi tiap kasus lewat interpreter dulu
sebelum ditulis di sini (bukan ditebak) -- lihat commit message."""

import hashlib

import pytest
from cti_core.urlkit import canonicalize_url, url_hash

# fmt: off
CASES: list[tuple[str, str, str]] = [
    # --- skema ---
    ("http -> https", "http://example.com/a", "https://example.com/a"),
    ("https tetap https", "https://example.com/a", "https://example.com/a"),

    # --- host ---
    ("host di-lowercase", "https://EXAMPLE.com/a", "https://example.com/a"),
    ("www. dibuang", "https://www.example.com/a", "https://example.com/a"),
    ("cuma satu www. dibuang", "https://www.www.example.com/a", "https://www.example.com/a"),
    ("subdomain non-www dipertahankan", "https://blog.example.com/a", "https://blog.example.com/a"),
    ("titik akhir host dibuang", "https://example.com./a", "https://example.com/a"),
    ("host+titik akhir+www digabung", "https://WWW.Example.COM./a", "https://example.com/a"),

    # --- port ---
    ("port 443 eksplisit dibuang", "https://example.com:443/a", "https://example.com/a"),
    ("port 80 eksplisit dibuang (skema jadi https)", "http://example.com:80/a", "https://example.com/a"),
    ("port custom dipertahankan", "https://example.com:8443/a", "https://example.com:8443/a"),
    ("port 8080 di http custom dipertahankan", "http://example.com:8080/a", "https://example.com:8080/a"),

    # --- path ---
    ("path kosong jadi root", "https://example.com", "https://example.com/"),
    ("root tetap root", "https://example.com/", "https://example.com/"),
    ("trailing slash non-root dibuang", "https://example.com/a/", "https://example.com/a"),
    ("path bersih gak berubah", "https://example.com/a/b", "https://example.com/a/b"),
    ("trailing slash cuma dibuang sekali", "https://example.com/a//", "https://example.com/a/"),
    ("spasi di-encode", "https://example.com/a b", "https://example.com/a%20b"),
    ("encoding spasi lama dinormalisasi", "https://example.com/a%20b", "https://example.com/a%20b"),
    ("encoding lowercase hex dinormalisasi ke uppercase", "https://example.com/a%2fb", "https://example.com/a%2Fb"),
    ("unicode di-encode UTF-8 uppercase hex", "https://example.com/café", "https://example.com/caf%C3%A9"),
    ("path numerik gak berubah", "https://example.com/2026/09/17", "https://example.com/2026/09/17"),
    ("path dgn titik dipertahankan (bukan dot-segment resolve)", "https://example.com/a/./b", "https://example.com/a/./b"),

    # --- query: tracking param dibuang ---
    ("utm_source dibuang", "https://example.com/a?utm_source=rss", "https://example.com/a"),
    ("utm_medium dibuang", "https://example.com/a?utm_medium=feed", "https://example.com/a"),
    ("utm_campaign dibuang", "https://example.com/a?utm_campaign=x", "https://example.com/a"),
    ("utm_term dibuang", "https://example.com/a?utm_term=x", "https://example.com/a"),
    ("utm_content dibuang", "https://example.com/a?utm_content=x", "https://example.com/a"),
    ("utm_id dibuang", "https://example.com/a?utm_id=1", "https://example.com/a"),
    ("utm_reader dibuang", "https://example.com/a?utm_reader=feedly", "https://example.com/a"),
    ("fbclid dibuang", "https://example.com/a?fbclid=abc", "https://example.com/a"),
    ("gclid dibuang", "https://example.com/a?gclid=abc", "https://example.com/a"),
    ("gbraid dibuang", "https://example.com/a?gbraid=abc", "https://example.com/a"),
    ("wbraid dibuang", "https://example.com/a?wbraid=abc", "https://example.com/a"),
    ("msclkid dibuang", "https://example.com/a?msclkid=abc", "https://example.com/a"),
    ("dclid dibuang", "https://example.com/a?dclid=abc", "https://example.com/a"),
    ("igshid dibuang", "https://example.com/a?igshid=abc", "https://example.com/a"),
    ("mc_cid dibuang", "https://example.com/a?mc_cid=abc", "https://example.com/a"),
    ("mc_eid dibuang", "https://example.com/a?mc_eid=abc", "https://example.com/a"),
    ("ref dibuang", "https://example.com/a?ref=twitter", "https://example.com/a"),
    ("ref_src dibuang", "https://example.com/a?ref_src=tw", "https://example.com/a"),
    ("referrer dibuang", "https://example.com/a?referrer=x", "https://example.com/a"),
    ("source dibuang", "https://example.com/a?source=rss", "https://example.com/a"),
    ("_hsenc dibuang", "https://example.com/a?_hsenc=x", "https://example.com/a"),
    ("_hsmi dibuang", "https://example.com/a?_hsmi=x", "https://example.com/a"),
    ("vero_id dibuang", "https://example.com/a?vero_id=x", "https://example.com/a"),
    ("yclid dibuang", "https://example.com/a?yclid=x", "https://example.com/a"),
    ("ck_subscriber_id dibuang", "https://example.com/a?ck_subscriber_id=x", "https://example.com/a"),
    ("tracking param case-insensitive", "https://example.com/a?UTM_SOURCE=rss", "https://example.com/a"),
    (
        "semua tracking sekaligus jadi query kosong total",
        "https://example.com/a?utm_source=x&fbclid=y&ref=z",
        "https://example.com/a",
    ),

    # --- query: non-tracking dipertahankan + diurutkan ---
    ("query non-tracking dipertahankan", "https://example.com/a?id=42", "https://example.com/a?id=42"),
    ("dua query diurutkan alfabetis", "https://example.com/a?z=1&a=2", "https://example.com/a?a=2&z=1"),
    ("tracking dibuang, sisanya diurutkan", "https://example.com/a?utm_source=x&id=1&page=2", "https://example.com/a?id=1&page=2"),
    ("key sama value beda diurutkan by value", "https://example.com/a?b=2&b=1", "https://example.com/a?b=1&b=2"),
    ("query blank value dipertahankan", "https://example.com/a?flag=", "https://example.com/a?flag="),
    ("query tanpa value dipertahankan sbg blank", "https://example.com/a?flag", "https://example.com/a?flag="),

    # --- fragment ---
    ("fragment biasa dibuang", "https://example.com/a#section2", "https://example.com/a"),
    ("fragment kosong gak nyisa tanda pagar", "https://example.com/a#", "https://example.com/a"),
    ("hashbang dipertahankan (pola SPA lama)", "https://example.com/a#!/page/2", "https://example.com/a#!/page/2"),

    # --- gabungan ---
    (
        "semua transformasi sekaligus",
        "HTTP://WWW.Example.COM:80/a/b/?utm_source=rss&z=1&a=2#section",
        "https://example.com/a/b?a=2&z=1",
    ),
]
# fmt: on


@pytest.mark.parametrize("desc,url,expected", CASES, ids=[c[0] for c in CASES])
def test_canonicalize_url_table(desc: str, url: str, expected: str) -> None:
    assert canonicalize_url(url) == expected, desc


def test_case_count_meets_exit_criteria() -> None:
    """Fase 2 exit criteria: canonicalize_url lolos tabel ~60 kasus."""
    assert len(CASES) >= 60


# --- pasangan yang HARUS collide (dua tampilan beda, satu identitas) ---
EQUIVALENT_PAIRS: list[tuple[str, str]] = [
    ("http://example.com/a", "https://example.com/a"),
    ("https://example.com/a", "https://www.example.com/a"),
    ("https://example.com/a", "https://EXAMPLE.com/a/"),
    ("https://example.com/a", "https://example.com:443/a"),
    ("https://example.com/a", "https://example.com/a?utm_source=rss"),
    ("https://example.com/a?z=1&a=2", "https://example.com/a?a=2&z=1"),
    ("https://example.com/a#section", "https://example.com/a"),
]


@pytest.mark.parametrize("url_a,url_b", EQUIVALENT_PAIRS)
def test_equivalent_urls_collide(url_a: str, url_b: str) -> None:
    assert canonicalize_url(url_a) == canonicalize_url(url_b)
    assert url_hash(url_a) == url_hash(url_b)


# --- pasangan yang TIDAK boleh collide ---
DISTINCT_PAIRS: list[tuple[str, str]] = [
    ("https://example.com/a", "https://example.com/b"),
    ("https://example.com/a", "https://other.com/a"),
    ("https://example.com/a?id=1", "https://example.com/a?id=2"),
    ("https://example.com:8443/a", "https://example.com/a"),
    ("https://example.com/a#!/x", "https://example.com/a#!/y"),
]


@pytest.mark.parametrize("url_a,url_b", DISTINCT_PAIRS)
def test_distinct_urls_do_not_collide(url_a: str, url_b: str) -> None:
    assert canonicalize_url(url_a) != canonicalize_url(url_b)
    assert url_hash(url_a) != url_hash(url_b)


def test_url_hash_is_sha256_of_canonical_form() -> None:
    url = "http://WWW.Example.com/a?utm_source=x"
    expected = hashlib.sha256(canonicalize_url(url).encode()).hexdigest()
    assert url_hash(url) == expected
    assert len(url_hash(url)) == 64  # hex digest, fixed width


def test_url_hash_is_deterministic() -> None:
    url = "https://example.com/threat-report-2026"
    assert url_hash(url) == url_hash(url)
