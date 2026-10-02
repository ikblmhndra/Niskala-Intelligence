"""Alert Telegram `github_poc` (2026-10-02).

Legacy `githubPOCMonitor.py` mengirim `send_alert_poc` ke thread `github_exploit` untuk repo PoC
dari pencarian broad. Di platform baru alert itu hilang sama sekali (scraper hanya menulis
`cve_tracker.pocs`). Sekarang `fetch()` menyertakan `NoticeItem` topik `github_poc` untuk repo
baru dari pencarian broad; pencarian targeted tetap hanya menyimpan (sama seperti legacy)."""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any

import httpx
import pytest
from cti_scraper.items import CvePocItem, NoticeItem
from cti_scrapers.feeds.github_poc_monitor import GithubPocMonitor

from tests.unit.scraper_helpers import make_ctx

NOW = datetime.datetime(2026, 10, 2, 12, 0, 0)
MITRE = {"containers": {"cna": {"affected": [{"vendor": "Fortinet", "product": "FortiOS"}]}}}


def _repo(**over: Any) -> dict[str, Any]:
    repo: dict[str, Any] = {
        "id": 1,
        "name": "cve-2026-12345-poc",
        "html_url": "https://github.com/acme/cve-2026-12345-poc",
        "description": "Fortinet FortiOS RCE exploit",
        "language": "Python",
        "fork": False,
        "owner": {"login": "acme"},
        "created_at": "2026-10-01T10:00:00Z",
    }
    repo.update(over)
    return repo


class _Http:
    """Search `cve-2026-*` halaman 1 -> `repos`; halaman/tahun lain kosong. MITRE -> Fortinet."""

    def __init__(self, repos: list[dict[str, Any]], mitre: dict[str, Any] | None = None) -> None:
        self.repos = repos
        self.mitre = mitre or MITRE

    def get(self, url: str, **_: Any) -> httpx.Response:
        if "cveawg.mitre.org" in url:
            return httpx.Response(200, json=self.mitre)
        if "q=cve-2026-*" in url and "page=1" in url:
            return httpx.Response(200, json={"items": self.repos})
        return httpx.Response(200, json={"items": []})


def _run(
    repos: list[dict[str, Any]],
    *,
    max_items: int | None = None,
    mitre: dict[str, Any] | None = None,
) -> list[Any]:
    scraper = GithubPocMonitor()
    if max_items is not None:
        scraper.meta = dataclasses.replace(scraper.meta, max_items=max_items)  # type: ignore[misc]
    ctx = make_ctx(
        GithubPocMonitor,
        lambda r: httpx.Response(200),
        now=NOW,
        reference={"techstack": ["fortinet"], "true_positive_cves": []},
    )
    ctx.http = _Http(repos, mitre)  # type: ignore[assignment]
    return list(scraper.fetch(ctx))


def test_repo_baru_menghasilkan_cvepocitem_lalu_notice_github_poc() -> None:
    items = _run([_repo()])

    assert [type(i) for i in items] == [CvePocItem, NoticeItem]
    stored, notice = items
    assert stored.cve_id == "cve-2026-12345"
    assert notice.topic == "github_poc"
    assert notice.url == "https://github.com/acme/cve-2026-12345-poc"
    assert notice.posted_on == datetime.date(2026, 10, 1)
    for fragment in (
        "NEW CVE POC ON GITHUB",
        "CVE-2026-12345",
        "cve-2026-12345-poc POC for Fortinet",
        "<b>Owner</b>: acme",
        "<b>Language</b>: Python",
        "FortiOS",
        '<a href="https://github.com/acme/cve-2026-12345-poc">Link</a>',
        "17:00:00 01-10-2026",  # 10:00 UTC dalam WIB (+7), format legacy
    ):
        assert fragment in notice.text, fragment


def test_key_notice_tidak_bentrok_dengan_dedup_cvepocitem() -> None:
    """Dua item itu hidup di namespace dedup scraper_id yang sama -- key identik = satu dibuang."""
    stored, notice = _run([_repo()])

    assert stored.dedup_key() != notice.dedup_key()
    assert notice.dedup_key().startswith("alert:")


def test_repo_lebih_tua_dari_tiga_hari_hanya_disimpan_tanpa_alert() -> None:
    items = _run([_repo(created_at="2026-09-28T10:00:00Z")])

    assert [type(i) for i in items] == [CvePocItem]


def test_batas_umur_tepat_tiga_hari_masih_di_alert_lewat_sedikit_tidak() -> None:
    edge_in = _repo(created_at="2026-09-29T12:00:00Z")  # tepat 3 hari
    edge_out = _repo(created_at="2026-09-29T11:59:59Z")  # lewat 1 detik

    assert [type(i) for i in _run([edge_in])] == [CvePocItem, NoticeItem]
    assert [type(i) for i in _run([edge_out])] == [CvePocItem]


@pytest.mark.parametrize("created_at", [None, "", "kemarin"])
def test_created_at_tidak_terbaca_tidak_di_alert(created_at: str | None) -> None:
    repo = _repo()
    if created_at is None:
        del repo["created_at"]
    else:
        repo["created_at"] = created_at

    assert [type(i) for i in _run([repo])] == [CvePocItem]


def test_teks_dari_luar_di_escape() -> None:
    repo = _repo(description="Fortinet <script>alert(1)</script> & co", language="C<>")
    notice = _run([repo])[1]

    assert "<script>" not in notice.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co" in notice.text
    assert "<b>Language</b>: C&lt;&gt;" in notice.text


def test_field_panjang_dipotong_sehingga_pesan_di_bawah_batas_telegram() -> None:
    repo = _repo(description="fortinet " + "x" * 5000)
    notice = _run([repo])[1]

    assert len(notice.text) < 4096
    assert "…" in notice.text


def test_vendor_dan_produk_dari_mitre_di_escape_dan_dipotong() -> None:
    affected = [{"vendor": "Acme & Sons <x>", "product": f"Product{n}"} for n in range(300)]
    mitre = {"containers": {"cna": {"affected": affected}}}

    notice = _run([_repo(description="fortinet appliance")], mitre=mitre)[1]

    assert "POC for Acme &amp; Sons &lt;x&gt;" in notice.text
    assert "Product0" in notice.text
    assert "Product299" not in notice.text  # ~3000 karakter produk dipotong di 800
    assert len(notice.text) < 4096


def test_language_kosong_tampil_strip_bukan_none() -> None:
    notice = _run([_repo(language=None)])[1]

    assert "<b>Language</b>: -" in notice.text
    assert "None" not in notice.text


def test_max_items_menghitung_repo_bukan_pasangan_notice() -> None:
    repos = [
        _repo(
            id=n,
            name=f"cve-2026-{n:05d}-poc",
            html_url=f"https://github.com/acme/cve-2026-{n:05d}-poc",
        )
        for n in range(1, 6)
    ]

    items = _run(repos, max_items=2)

    assert [type(i) for i in items] == [CvePocItem, NoticeItem, CvePocItem, NoticeItem]


def test_pencarian_targeted_hanya_menyimpan_tanpa_alert() -> None:
    """Legacy fase 2 (CVE yang sudah ter-track) menulis DB saja -- tidak mengirim Telegram."""
    ctx = make_ctx(
        GithubPocMonitor,
        lambda r: httpx.Response(200),
        now=NOW,
        reference={
            "techstack": [],
            "true_positive_cves": [{"cve_id": "CVE-2026-12345", "poc_urls": set()}],
        },
    )

    class _Targeted:
        def get(self, url: str, **_: Any) -> httpx.Response:
            return httpx.Response(200, json={"items": [_repo(name="CVE-2026-12345-poc")]})

    ctx.http = _Targeted()  # type: ignore[assignment]

    items = list(GithubPocMonitor().fetch(ctx))

    assert [type(i) for i in items] == [CvePocItem]


def test_notice_dikirim_ke_topik_github_poc_lewat_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    import cti_alerts.telegram as telegram
    from cti_scraper import sinks

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(telegram, "send_alert", lambda topic, msg: sent.append((topic, msg)))
    notice = _run([_repo()])[1]

    sinks._notice_sink(notice, GithubPocMonitor.meta, None)  # type: ignore[arg-type]

    assert sent == [("github_poc", notice.text)]


def test_topik_github_poc_terdaftar_di_template_env() -> None:
    """`UnknownAlertTopic` kalau lupa: scraper memakai literal `github_poc`."""
    import json
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    for name in (".env.example", ".env.prod.template"):
        line = next(
            ln for ln in (root / name).read_text().splitlines() if ln.startswith("TELEGRAM__THREAD")
        )
        assert "github_poc" in json.loads(line.split("=", 1)[1]), name
