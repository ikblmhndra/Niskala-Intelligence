#!/usr/bin/env python3
"""Fase 0.5-0.7 — Rekam perilaku scraper lama sebagai fixture.

Ini yang bikin big-bang rewrite bisa diverifikasi. Buat tiap scraper lama
kita rekam dua hal:

  1. Byte HTTP mentah yang dia ambil   -> <id>/<tanggal>.input.<ext>
  2. Item (title, url) yang dia hasilkan -> <id>/expected_items.json

Nanti di Fase 4, plugin baru dikasih byte yang SAMA dan harus ngeluarin item
yang SAMA. Begitu script lama dihapus, baseline ini gak bisa dibikin lagi.

Cara kerjanya: scraper lama itu script yang jalan pas di-import (kode di level
modul). Jadi kita suntik pengganti palsu buat modules.jobQueue / offsetStore /
dbMongo / telegramAlert ke sys.modules DULUAN, baru jalanin script-nya. Yang
asli gak pernah ke-load, jadi gak butuh config.yml dan gak nyentuh Mongo.

Tiap scraper jalan di subprocess terpisah supaya satu yang crash atau hang
gak ngerusak keseluruhan run.

Pakai:
    ./record_fixtures.py --scrapers-dir ../../../ScraperNews \
                         --out ../../tests/fixtures
    ./record_fixtures.py --scrapers-dir ... --only gbHackerThreat --verbose
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

TIMEOUT_S = 90  # scraper light (RSS / requests)
TIMEOUT_BROWSER_S = 240  # Playwright: launch chromium + render + tunggu selector

# Script yang bukan feed scraper — jangan direkam.
SKIP = {
    "nlp_worker",
    "testing_nlp_worker",
    "iocSyncer",
    "test",
    "seleniumTemplate",
    "enrichmentTemplate",
    "xmlTemplate",
    "requestsTemplate",
    "playwrightTemplate",
    "undetectedChromeTemplate",
    "nameThreat",
    # Utilitas / service, bukan feed scraper -- gak punya baseline buat di-diff
    "addCveTrackerUi",
    "getCveTracker",
    "topCve",
    "pkgVulnScanner",
    "threatActorTrend",
    "cyborgHuntingIdea",
    "deepdarkCTI_sync",
    "export_db",
    "import_db",
}

# BAHAYA NYATA, bukan cuma "gak berguna direkam" -- file ini punya token
# Graylog DAN bot Telegram ASLI HARDCODED DI SOURCE (bukan dari config.yml,
# bukan lewat modules.telegramAlert yang di-stub), ngirim ke
# privy.graylog.cloud dan chat/thread Telegram BENERAN. Kena grep terpisah
# dari SKIP di atas biar gak ketimbun kalau SKIP direvisi nanti.
# JANGAN DIHAPUS dari sini sebelum token-nya dirotasi (lihat SECRETS_ROTATION.md).
#
# CATATAN: threatActorTrendGraylog.py (beda file, nama mirip) SUDAH DICEK dan
# AMAN -- dia lewat modules.graylogLogging yang di atas di-stub jadi no-op,
# gak hardcode kredensial sendiri. Jangan ikut ditambahin ke sini tanpa
# verifikasi ulang isi filenya.
DANGEROUS_LIVE_SIDE_EFFECTS = {"threatActorTrendTele"}
SKIP |= DANGEROUS_LIVE_SIDE_EFFECTS
SKIP_DIRS = {
    "backup_script",
    "stopped_script",
    "modules",
    "scripts",
    "supportFile",
    "offset",
    "chromedriver_mac64_arm64",
}


# ---------------------------------------------------------------- child mode
def _child(script_path: str) -> int:
    """Jalan di dalam subprocess: pasang perekam, eksekusi script, dump JSON."""
    import runpy
    import types

    # Context dari DB (techstack, monitored accounts, allowlist). Tanpa ini,
    # scraper yang nyocokin ke tech stack -- cisacatalogThreat, newCveThreat,
    # techstackNPM -- ngehasilkan NOL item dan fixture-nya jadi bohong.
    ctx_path = os.environ.get("CTI_FIXTURE_CONTEXT")
    ctx = json.loads(Path(ctx_path).read_text()) if ctx_path else {}
    used_context = bool(ctx)

    script = Path(script_path).resolve()
    recorded: dict[str, dict] = {}  # url -> {body: b64, content_type}
    items: list[dict] = []
    labels: set[str] = set()

    # --- pengganti palsu buat modul yang butuh config/Mongo ------------------
    def push_job(article_data, script_name):
        items.append(
            {
                "title": str(article_data.get("title", "")),
                "url": str(article_data.get("url", "")),
                "posted_on": str(article_data.get("posted_on", "")),
            }
        )
        labels.add(str(script_name))

    fake_queue = types.ModuleType("modules.jobQueue")
    fake_queue.push_job = push_job
    fake_queue.claim_job = lambda col: None

    fake_offset = types.ModuleType("modules.offsetStore")
    # Selalu True: kita mau LIHAT semua item yang diambil scraper, bukan cuma
    # yang belum pernah kelihatan. Ini yang bikin fixture deterministik.
    fake_offset.is_new_and_mark = lambda script_name, key: True

    fake_db = types.ModuleType("modules.dbMongo")
    for fn in (
        "upsert_article",
        "log_scraper_run",
        "update_cve_mention",
        "upsert_ioc_from_feed",
        "upsert_threat_feed",
        "upsert_ta_group_from_feed",
        "insert_logbook_entry",
        "upsert_tweet",
        "insert_database",
        "set_openai_cache",
    ):
        setattr(fake_db, fn, lambda *a, **k: None)
    fake_db.upsert_ransomware_victim = lambda d: (
        items.append(
            {"kind": "ransomware_victim", **{k: str(v) for k, v in d.items() if k != "saved_at"}}
        )
        or True
    )
    fake_db.get_existing_ransomware_keys = lambda: set()
    fake_db.get_ioc_allowlist = lambda: ctx.get(
        "ioc_allowlist", {"url_domains": [], "email_domains": [], "ips": []}
    )
    fake_db.get_c2_feed_set = lambda: set(ctx.get("c2_feed", []))
    fake_db.list_existing = lambda t: ctx.get("lists", {}).get(t, [])
    fake_db.list_monitored_accounts = lambda: ctx.get("monitored_accounts", [])
    fake_db.tweet_exists = lambda i: False
    fake_db.get_openai_cache = lambda u: None
    fake_db.get_cve_mentions = lambda ym: []

    fake_tele = types.ModuleType("modules.telegramAlert")
    for fn in (
        "send_alert",
        "send_alert_tech_stack",
        "send_alert_darkweb",
        "send_alert_report",
        "send_alert_databreach",
        "send_file",
        "send_alert_ransomware_act",
        "send_alert_poc",
        "send_alert_zeroday",
        "send_alert_tech_stack_unrelated",
        "send_alert_debug",
        "send_alert_news_of_the_day",
        "send_report_file",
        "send_alert_ot",
        "send_alert_sec_best_practice",
    ):
        setattr(fake_tele, fn, lambda *a, **k: None)

    fake_tech = types.ModuleType("modules.techstackStore")
    fake_tech.get_tech_list = lambda: ctx.get("techstack", [])
    fake_tech.get_tech_list_by_client = lambda: ctx.get("techstack_by_client", {})

    fake_graylog = types.ModuleType("modules.graylogLogging")
    fake_graylog.sendLogGraylog = lambda *a, **k: None

    fake_modules = types.ModuleType("modules")
    fake_modules.__path__ = []

    sys.modules.update(
        {
            "modules": fake_modules,
            "modules.jobQueue": fake_queue,
            "modules.offsetStore": fake_offset,
            "modules.dbMongo": fake_db,
            "modules.telegramAlert": fake_tele,
            "modules.techstackStore": fake_tech,
            "modules.graylogLogging": fake_graylog,
        }
    )

    # Stub eksplisit di atas cuma nutup 6 submodul. Scraper lain ngimport
    # modules.articleValidator / cveValidator / nlp / iocExtractor /
    # cveEmailAutomation / mitreValidator ... yang semuanya butuh config.yml,
    # Mongo, spaCy atau kunci OpenAI. Meta-path finder ini bikin stub permisif
    # otomatis buat modules.* apa pun yang belum disediakan, jadi fetch/parse
    # scraper tetap jalan tanpa satu pun dependensi berat.
    import importlib.abc
    import importlib.machinery

    class _AnyCallable:
        """Atribut apa pun bisa dipanggil, balikin None. Bisa dipakai sebagai
        context manager, iterator, dan boolean(False) juga."""

        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return None

        def __getattr__(self, n):
            return _AnyCallable()

        def __getitem__(self, n):
            return _AnyCallable()

        def __iter__(self):
            return iter(())

        def __bool__(self):
            return False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _StubLoader(importlib.abc.Loader):
        def create_module(self, spec):
            m = types.ModuleType(spec.name)
            m.__getattr__ = lambda n: _AnyCallable()  # PEP 562
            return m

        def exec_module(self, module):
            pass

    class _StubFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.startswith("modules.") and fullname not in sys.modules:
                return importlib.machinery.ModuleSpec(fullname, _StubLoader())
            return None

    sys.meta_path.insert(0, _StubFinder())

    # Bahaya nyata, bukan cuma masalah dependency: newCveThreat.py dan
    # githubPOCMonitor.py bikin MongoClient LANGSUNG dari config.yml,
    # ngelewatin modules.dbMongo yang di atas udah di-stub. Kalau config.yml
    # asli disuapin ke sini, dua script itu bisa BENERAN NULIS ke Mongo
    # produksi (newCveThreat malah manggil bulk_write). Tambal di sumbernya:
    # pymongo.MongoClient jadi inert apa pun config yang dikasih -- pertahanan
    # yang gak bergantung nemuin semua script yang bypass modules.dbMongo.
    try:
        import pymongo

        pymongo.MongoClient = _AnyCallable
    except ImportError:
        pass

    # Sama alasannya kayak pymongo di atas: threatActorTrendTele.py bikin
    # telegram.Bot(token='<hardcoded>') LANGSUNG, gak lewat modules.telegramAlert
    # yang di-stub. File itu udah masuk SKIP permanen, tapi ini pertahanan
    # kedua buat script lain yang belum ketemu dengan pola sama.
    try:
        import telegram

        telegram.Bot = _AnyCallable
    except ImportError:
        pass

    # --- rekam byte HTTP -----------------------------------------------------
    import base64

    def _store(url, content, ctype, status=200):
        if content and url not in recorded:
            recorded[url] = {
                "body_b64": base64.b64encode(content).decode(),
                "content_type": ctype or "",
                "status_code": status,
            }

    try:
        import requests

        _orig_send = requests.adapters.HTTPAdapter.send

        def send(self, request, **kw):
            resp = _orig_send(self, request, **kw)
            # Best-effort: nyimpen byte cuma buat fixture. Kalau gagal, jangan
            # sampai bikin request scraper aslinya ikut gagal.
            with contextlib.suppress(Exception):
                _store(
                    request.url,
                    resp.content,
                    resp.headers.get("Content-Type", ""),
                    resp.status_code,
                )
            return resp

        requests.adapters.HTTPAdapter.send = send
    except ImportError:
        pass

    # --- rekam DOM Playwright setelah render --------------------------------
    try:
        import playwright.sync_api as pw

        class _Page:
            """Proxy yang nyimpen HTML final tiap kali selesai goto()."""

            def __init__(self, inner):
                object.__setattr__(self, "_inner", inner)

            def goto(self, url, *a, **kw):
                r = self._inner.goto(url, *a, **kw)
                with contextlib.suppress(Exception):  # best-effort, sama alasannya
                    _store(
                        url,
                        self._inner.content().encode("utf-8"),
                        "text/html",
                        getattr(r, "status", 200) or 200,
                    )
                return r

            def __getattr__(self, n):
                return getattr(object.__getattribute__(self, "_inner"), n)

            def __setattr__(self, n, v):
                setattr(object.__getattribute__(self, "_inner"), n, v)

        _orig_new_page = pw.sync_api.Browser.new_page if hasattr(pw, "sync_api") else None
        from playwright.sync_api import Browser as _B

        _orig = _B.new_page

        def new_page(self, **kw):
            return _Page(_orig(self, **kw))

        _B.new_page = new_page
    except ImportError:
        pass

    # --- jalanin script lama -------------------------------------------------
    status, error = "ok", None
    os.chdir(script.parent)
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit:
        pass
    except BaseException as e:
        status = type(e).__name__
        error = f"{type(e).__name__}: {e}"

    print("<<<FIXTURE_JSON>>>")
    print(
        json.dumps(
            {
                "status": status,
                "error": error,
                "used_context": used_context,
                "items": items,
                "labels": sorted(labels),
                "http": recorded,
            }
        )
    )
    return 0


# --------------------------------------------------------------- parent mode
EXT = {"xml": ".xml", "rss": ".xml", "atom": ".xml", "json": ".json", "html": ".html"}


def _ext_for(ctype: str, url: str) -> str:
    c = (ctype or "").lower()
    for k, v in EXT.items():
        if k in c:
            return v
    for k, v in EXT.items():
        if url.lower().endswith("." + k):
            return v
    return ".txt"


def record_one(
    script: Path, out_root: Path, day: str, verbose: bool, context: Path | None = None
) -> dict:
    import base64

    sid = script.stem
    env = dict(os.environ)
    if context:
        env["CTI_FIXTURE_CONTEXT"] = str(context)
    src = script.read_text(errors="ignore")
    timeout = TIMEOUT_BROWSER_S if ("playwright" in src or "selenium" in src) else TIMEOUT_S
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--_child", str(script)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    marker = "<<<FIXTURE_JSON>>>"
    if marker not in proc.stdout:
        return {
            "scraper": sid,
            "status": "harness_error",
            "error": (proc.stderr or proc.stdout)[-400:],
            "items": 0,
        }

    data = json.loads(proc.stdout.split(marker, 1)[1].strip())
    d = out_root / sid
    d.mkdir(parents=True, exist_ok=True)

    for i, (url, blob) in enumerate(data["http"].items()):
        suffix = "" if i == 0 else f".{i}"
        p = d / f"{day}.input{suffix}{_ext_for(blob['content_type'], url)}"
        p.write_bytes(base64.b64decode(blob["body_b64"]))

    exp = d / "expected_items.json"
    existing = json.loads(exp.read_text()) if exp.exists() else {}
    existing[day] = data["items"]
    exp.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    http_status = {u: b.get("status_code", 0) for u, b in data["http"].items()}
    blocked = [u for u, c in http_status.items() if c in (401, 403, 429) or c >= 500]

    (d / "meta.json").write_text(
        json.dumps(
            {
                "scraper": sid,
                "legacy_script": sid,
                "legacy_labels": data["labels"],
                "source_urls": list(data["http"].keys()),
                "http_status": http_status,
                "blocked_urls": blocked,
                "used_db_context": data.get("used_context", False),
                "last_recorded": day,
                "last_status": data["status"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    if verbose and data["error"]:
        print(f"      {data['error'][:160]}", file=sys.stderr)

    return {
        "scraper": sid,
        "status": data["status"],
        "items": len(data["items"]),
        "http": len(data["http"]),
        "blocked": blocked,
        "error": data["error"],
    }


_DUMMY_CONFIG_YML = """\
# Dibuat otomatis oleh record_fixtures.py -- SEMUA NILAI PALSU.
# newCveThreat.py & githubPOCMonitor.py bikin MongoClient langsung dari sini,
# tapi pymongo.MongoClient sudah ditambal jadi inert di _child(), jadi
# kredensial mongodb/news_db di bawah TIDAK PERNAH dipakai buat koneksi
# beneran -- cuma biar dict-nya lengkap dan gak KeyError.
mongodb: {user: dummy, pass: dummy, ip: 127.0.0.1, cluster: dummy, collection: dummy}
news_db: {user: dummy, pass: dummy, ip: 127.0.0.1, db: dummy}
llm: {provider: openai, api_key: "", model: gpt-4o}
openai: {project_id: "", token_usage: 0}
telegram:
  bot_token: ""
  chat_id: "0"
  thread_id_apac: 0
  thread_id_apac_indo: 0
  thread_id_group: 0
  thread_id_breach: 0
  thread_id_report: 0
  thread_id_darkweb: 0
  thread_id_ransomware_activity: 0
  thread_id_github_exploit: 0
  thread_id_zero_day: 0
  thread_id_techstack_related: 0
  thread_id_techstack_unrelated: 0
  thread_id_ot: 0
  thread_id_sec_best: 0
  thread_id_debug: 0
  thread_id_group_debug: 0
  thread_id_notd: 0
twitter: {api_key: "", accounts_file: "", state_file: ""}
github: {token: ""}
nvd: {key: ""}
azure: {tenant_id: "", client_id: "", client_secret: ""}
graylog: {url: "http://127.0.0.1:1/gelf"}
otx: {}
abuseipdb: {}
myprovider: {api_key: ""}
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--_child", dest="child", help=argparse.SUPPRESS)
    ap.add_argument("--scrapers-dir", type=Path, help="root ScraperNews/")
    ap.add_argument("--out", type=Path, help="tujuan fixture")
    ap.add_argument("--only", action="append", help="rekam scraper tertentu saja")
    ap.add_argument(
        "--context",
        type=Path,
        help="JSON berisi data DB (techstack, monitored_accounts, "
        "ioc_allowlist). Tanpa ini, scraper yang bergantung DB "
        "ngehasilkan 0 item dan fixture-nya bohong.",
    )
    ap.add_argument(
        "--active-only",
        type=Path,
        metavar="RUNDECK_MAP",
        help="batasi ke scraper yang job Rundeck-nya aktif "
        "(docs/legacy/rundeck-jobs-map.json). 241 -> ~91.",
    )
    ap.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=1,
        help="jumlah scraper direkam paralel (default 1). "
        "8 masuk akal; tiap scraper jalan di subprocess sendiri.",
    )
    ap.add_argument(
        "--resume", action="store_true", help="lewati scraper yang hari ini udah berhasil direkam"
    )
    ap.add_argument("--day", default=dt.date.today().isoformat())
    ap.add_argument("--verbose", "-v", action="store_true")
    a = ap.parse_args()

    if a.child:
        return _child(a.child)

    # Run sebelumnya "berhasil" bikin 231 direktori fixture yang isinya nol item,
    # karena dijalanin pakai python sistem tanpa dependensi scraper lama.
    # Fixture kosong lebih bahaya daripada gagal: kelihatan kayak baseline.
    import importlib.util

    missing = [m for m in ("requests", "defusedxml", "lxml") if importlib.util.find_spec(m) is None]
    if missing:
        venv = Path(__file__).resolve().parents[2] / ".venv-legacy" / "bin" / "python"
        print(f"error: interpreter ini gak punya: {', '.join(missing)}\n", file=sys.stderr)
        print("Perekam harus jalan pakai venv legacy, bukan python sistem:\n", file=sys.stderr)
        print(f"  {venv} {' '.join(sys.argv)}\n", file=sys.stderr)
        print("Belum ada? bikin dulu: ./tools/salvage/setup_legacy_env.sh", file=sys.stderr)
        return 2
    if not a.scrapers_dir or not a.out:
        ap.error("--scrapers-dir dan --out wajib")

    root = a.scrapers_dir.resolve()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    scripts = sorted(
        p
        for p in root.glob("*.py")
        if p.stem not in SKIP
        and not any(part in SKIP_DIRS for part in p.parts)
        and (not a.only or p.stem in a.only)
    )
    # Sembilan scraper buka config/config.yml LANGSUNG (bukan lewat modules.*
    # yang di atas udah di-stub) buat baca token GitHub / kredensial Mongo.
    # File itu gak pernah ada di checkout ini (gitignored). Bikin versi dummy
    # kalau belum ada -- aman dipakai walau nilainya bukan yang asli, karena
    # pymongo.MongoClient dan telegram.Bot udah ditambal jadi inert di atas;
    # config ini cuma ngisi bentuk dict-nya biar gak KeyError, bukan nyambung
    # ke apa pun beneran.
    cfg_path = a.scrapers_dir / "config" / "config.yml"
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(_DUMMY_CONFIG_YML)
        print(f"Config dummy dibuat: {cfg_path} (nilai palsu, MongoClient sudah inert)\n")

    if a.active_only:
        jobs = json.loads(a.active_only.read_text())
        active = {Path(j["script"]).stem for j in jobs if j.get("enabled") and j.get("script")}
        before = len(scripts)
        scripts = [p for p in scripts if p.stem in active]
        print(f"Filter job aktif: {before} -> {len(scripts)} scraper")

    if a.resume:
        done = set()
        for f in out.glob("*/expected_items.json"):
            try:
                if f.parent.name and json.loads(f.read_text()).get(a.day):
                    done.add(f.parent.name)
            except Exception:
                pass
        before = len(scripts)
        scripts = [p for p in scripts if p.stem not in done]
        print(f"Resume: {before - len(scripts)} udah direkam hari ini, dilewati")

    print(f"Merekam {len(scripts)} scraper -> {out}  (hari: {a.day}, paralel: {a.jobs})\n")

    def run_one(script: Path) -> dict:
        try:
            return record_one(script, out, a.day, a.verbose, a.context)
        except subprocess.TimeoutExpired:
            return {
                "scraper": script.stem,
                "status": "timeout",
                "items": 0,
                "http": 0,
                "blocked": [],
                "error": "timeout",
            }
        except Exception as e:
            return {
                "scraper": script.stem,
                "status": "harness_error",
                "items": 0,
                "http": 0,
                "blocked": [],
                "error": str(e),
            }

    results = []
    lock = threading.Lock()
    done_n = 0

    def report(r):
        nonlocal done_n
        with lock:
            done_n += 1
            mark = (
                "BLOCKED"
                if r.get("blocked")
                else "ok "
                if r["status"] == "ok" and r["items"]
                else "EMPTY"
                if r["status"] == "ok"
                else r["status"][:12]
            )
            print(
                f"[{done_n:3}/{len(scripts)}] {r['scraper']:38} {r['items']:4} item  {mark}",
                flush=True,
            )

    if a.jobs > 1:
        # Tiap scraper jalan di subprocess sendiri, jadi thread di sini cuma
        # nunggu I/O -- GIL bukan masalah. Yang jadi batas: koneksi keluar dan
        # jumlah Chromium yang bisa hidup bareng.
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(run_one, s): s for s in scripts}
            for f in as_completed(futs):
                r = f.result()
                results.append(r)
                report(r)
    else:
        for s in scripts:
            r = run_one(s)
            results.append(r)
            report(r)

    report = out.parent / f"fixture_report.{a.day}.json"
    report.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    blocked = [r for r in results if r.get("blocked")]
    good = [r for r in results if r["status"] == "ok" and r["items"] and not r.get("blocked")]
    empty = [r for r in results if r["status"] == "ok" and not r["items"] and not r.get("blocked")]
    bad = [r for r in results if r["status"] != "ok"]

    print(f"\n{'=' * 64}")
    print(f"  ada item : {len(good):3}")
    print(f"  kosong   : {len(empty):3}   <- feed sepi, parser rusak, atau butuh --context?")
    print(f"  diblokir : {len(blocked):3}   <- 403/429/5xx: rekam dari IP prod")
    print(f"  error    : {len(bad):3}")
    print(f"  laporan  : {report}")
    if blocked:
        print("\nDiblokir sama situsnya (fixture-nya TIDAK valid):")
        for r in blocked[:15]:
            print(f"  {r['scraper']:34} {r['blocked'][0][:60]}")
    if bad:
        print("\nScraper yang error (ini kandidat script yang emang udah mati):")
        for r in bad[:20]:
            print(f"  {r['scraper']:34} {r['status']:14} {(r.get('error') or '')[:70]}")
    print(
        "\nGate Fase 4: hari-1 hijau. Hari ke-2 dan ke-3 numpuk belakangan,\n"
        "gak perlu ngulang -- expected_items.json digabung per tanggal."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
