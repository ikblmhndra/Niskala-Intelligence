"""Queue non-scraper (`enrich`/`notify`/`maintenance`) -- 3 queue scrape
(`scrape.rss`/`scrape.api`/`scrape.browser`, `queue_for()`) pindah ke
`cti_scraper.queues` (Fase 9, H2), murni fungsi `ScraperMeta` yang juga
dibutuhin `apps/api` (control plane trigger), bukan worker-spesifik."""

from __future__ import annotations

QUEUE_ENRICH = "enrich"
QUEUE_NOTIFY = "notify"
QUEUE_MAINTENANCE = "maintenance"
