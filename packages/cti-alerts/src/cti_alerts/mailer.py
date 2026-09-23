"""SATU mailer Microsoft Graph -- gantiin `_send_newsletter_email()` di
`ScraperNewsWeb/app/routers/newsletter.py:62-119` (dua cabang SMTP/Graph
digabung satu fungsi, dipicu `EMAIL_METHOD` env var), DAN
`_create_graph_draft()` di `cve_email_service.py` lama (logic-nya sama
persis, cuma disalin). Dua-duanya kepake sekarang (`newsletter`+`cve`
router, Fase 7.4 Grup C) -- nama fungsi digeneralisasi dari
`send_newsletter_email` biar gak nyesatin, bukan lagi spesifik newsletter.

**Cuma jalur Microsoft Graph yang diport, SMTP TIDAK** -- keputusan
sadar, bukan kelalaian: `GraphSettings` (Fase 2) udah dibikin duluan
khusus buat ini ("pengiriman email CVE notification"), sementara skema
config baru SAMA SEKALI gak punya `SmtpSettings` -- dan `.env` produksi
yang udah ada isinya cuma kredensial Graph (`GRAPH__*`), gak ada satu
pun `SMTP_*`. Nambah SMTP sekarang berarti bikin config path yang gak
ada bukti kepake, ngelanggar prinsip "SATU cara" yang sama dipakai
`telegram.py` (SATU `send_alert()`, bukan 14 fungsi). Kalau nanti
ternyata SMTP beneran dibutuhkan, itu keputusan terpisah yang butuh
`SmtpSettings` baru di `cti_core.config`, bukan tambal di sini.

Dipakai `cti_api` (router `newsletter`, Fase 7.3 Bagian 4) -- BUKAN
`cti_scraper`/`cti_enrich`, jadi gak kena exit criteria "gak ada import
cti_scraper/cti_enrich dari API" (docs/PROGRESS.md Fase 7). `apps/api`
nambah `cti-alerts` sebagai dependency baru, sama kayak `apps/worker`
udah duluan.

Sinkron (bukan `async def`) -- port apa adanya, kode lama juga manggil
`_send_newsletter_email` via `run_in_executor`/thread pool dari endpoint
FastAPI async, bukan native async HTTP. `httpx.Client` sync dipakai di
sini, bukan `AsyncClient`, konsisten sama itu."""

from __future__ import annotations

import httpx
import msal
from cti_core.config import GraphSettings, get_settings


class GraphAuthError(Exception):
    """Gagal dapetin access token dari Azure AD."""


class GraphSendError(Exception):
    """Graph API nolak permintaan kirim/draft email."""


def create_graph_draft(
    html_content: str, subject: str, *, settings: GraphSettings | None = None
) -> str:
    """Bikin DRAFT message di mailbox `settings.sender` lewat Graph API
    (`POST /users/{sender}/messages`) -- port apa adanya, kode lama juga
    "draft" bukan "send" beneran (gak ada `/sendMail` call), analis yang
    review+kirim manual dari Outlook. Return Graph message id."""
    settings = settings or get_settings().graph

    authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
    app = msal.ConfidentialClientApplication(
        settings.client_id, authority=authority, client_credential=settings.client_secret
    )
    resp = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    token = resp.get("access_token")
    if not token:
        raise GraphAuthError(
            f"Gagal dapetin Azure access token: {resp.get('error_description', resp)}"
        )

    cc_list = [
        {"emailAddress": {"address": addr.strip()}}
        for addr in settings.cc.split(",")
        if addr.strip()
    ]
    payload = {
        "subject": subject,
        "body": {"contentType": "html", "content": html_content},
        "ccRecipients": cc_list,
    }
    resp2 = httpx.post(
        f"https://graph.microsoft.com/v1.0/users/{settings.sender}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    if resp2.status_code != 201:
        raise GraphSendError(f"Graph API error {resp2.status_code}: {resp2.text[:200]}")
    result: dict[str, object] = resp2.json()
    return str(result["id"])
