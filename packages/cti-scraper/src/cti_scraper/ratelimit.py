"""Token bucket Redis, per-DOMAIN (bukan per-scraper). Dua scraper yang
mukul host yang sama harus berbagi budget yang sama -- itu yang situsnya
sungguh pedulikan, bukan siapa yang mukul. Lihat plan §4.4.

Kenapa Redis dan bukan in-process: begitu Fase 6 jalan, beberapa worker
Celery jalan sebagai proses terpisah. Budget yang cuma hidup di memori satu
proses gak ngelindungin apa-apa kalau proses lain juga mukul domain yang
sama. Redis udah jadi dependency cti-scraper dari awal justru buat ini.
"""

from __future__ import annotations

import re
import time

import redis

_RATE_RE = re.compile(r"^(\d+)\s*/\s*(second|minute|hour)$")
_WINDOW_S = {"second": 1, "minute": 60, "hour": 3600}

_LUA_ACQUIRE = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local window_s = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local count = redis.call('GET', key)
if not count then
    redis.call('SET', key, 1, 'EX', window_s)
    return 1
end
count = tonumber(count)
if count < capacity then
    redis.call('INCR', key)
    return 1
end
return 0
"""


def parse_rate(rate: str) -> tuple[int, int]:
    """ "20/minute" -> (20, 60). Raise ValueError kalau formatnya gak
    dikenal -- gagal keras di config time, bukan diam-diam gak ngerate-limit."""
    m = _RATE_RE.match(rate.strip())
    if not m:
        raise ValueError(f"format rate limit gak dikenal: '{rate}' (contoh: '20/minute')")
    count, unit = m.groups()
    return int(count), _WINDOW_S[unit]


class TokenBucket:
    """Fixed-window counter per domain, bukan sliding-window/leaky-bucket
    beneran -- lebih murah (satu key, satu Lua script), dan buat throttle
    scraping "gak lebih dari N per menit" ini akurasinya cukup. Kalau
    nanti butuh smoothing yang lebih halus, ganti implementasi tanpa
    ubah signature `acquire()`.
    """

    def __init__(self, redis_client: redis.Redis, *, key_prefix: str = "cti:ratelimit") -> None:
        self._redis = redis_client
        self._prefix = key_prefix
        self._script = self._redis.register_script(_LUA_ACQUIRE)

    def acquire(self, domain: str, rate: str) -> bool:
        """True kalau boleh jalan sekarang. False kalau budget domain ini
        abis -- caller (biasanya ScraperHttpClient) yang raise RateLimited."""
        capacity, window_s = parse_rate(rate)
        key = f"{self._prefix}:{domain}"
        result = self._script(keys=[key], args=[capacity, window_s, time.time()])
        return bool(result)
