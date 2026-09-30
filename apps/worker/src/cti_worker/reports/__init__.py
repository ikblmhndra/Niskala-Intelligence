"""Laporan periodik Fase 10.E -- gantiin job Rundeck lama yang bukan scraper:
`sendCounter`, `trendingNewsToday`, `logbook`, `topCve`, dan `trendingCve`.

Logika di sini PURE-ish (masuk: session/HTTP/waktu yang disuntik; keluar: data
atau teks), pengiriman Telegram dan pembungkus Celery ada di `tasks/reports.py`.
"""
