"""XPath tahan-banting untuk daftar artikel yang berupa kumpulan `<a>` ke URL berpola.

Dipakai scraper `XPathScraper(indexed=False)` yang selector absolut `/html/body/div[2]/...` -nya
lapuk setiap situs di-redesign (census staging 2026-10-01: 18 dari 18 XPath gagal serentak). Yang
dipegang di sini cuma POLA HREF artikel (`/blog/<slug>`) dan panjang teks link -- bagian halaman
yang paling jarang berubah -- bukan posisi div ke-N.

Pasangan (judul, link) harus SEJAJAR (kontrak mode zipped `XPathScraper`), jadi dua XPath dibangun dari
filter anchor yang SAMA: judul = heading pertama di dalam anchor kalau ada (bersih dari label
kategori/tanggal/penulis yang ikut di `text_content()` anchor), kalau tidak ada heading = anchor itu
sendiri. Anchor dobel (gambar + judul menunjuk URL yang sama) menghasilkan item dobel; dedup per-URL
di framework yang membuangnya. Anchor di `nav`/`header`/`footer` dan teks <= `min_text` karakter
(menu, "Read more", paginasi) tidak diikutkan."""

from __future__ import annotations

_HEADING = "self::h1 or self::h2 or self::h3 or self::h4 or self::h5"


def link_card_xpaths(href_pred: str, *, min_text: int = 20) -> tuple[str, str]:
    """`(title_xpath, link_xpath)`. `href_pred` = isi predikat XPath atas `@href`, mis.
    `"starts-with(@href, '/blog/')"` atau `"contains(@href, '/advisory/')"`."""
    anchor = (
        f"//a[{href_pred}][string-length(normalize-space(.)) > {min_text}]"
        "[not(ancestor::nav or ancestor::header or ancestor::footer)]"
    )
    has_heading = f".//*[{_HEADING}]"
    first_heading = f"descendant::*[{_HEADING}][1]"
    title = f"{anchor}[{has_heading}]/{first_heading} | {anchor}[not({has_heading})]"
    link = f"{anchor}/@href"
    return title, link
