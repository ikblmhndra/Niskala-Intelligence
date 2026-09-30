"""`cti_worker.beat_lock.BeatLock` + fail-stop di `beat_main._renew_loop`
(Fase 10.1d, checklist cutover "Beat terverifikasi singleton").

Redis BENERAN lewat testcontainers, bukan fake -- yang diuji itu semantik
`SET NX PX` + dua script Lua (perpanjang/lepas cuma kalau masih punya kita),
dan fake in-memory gak bisa ngejalanin Lua tanpa ngimplementasi ulang
semantiknya sendiri (jadi ngetes tiruannya, bukan lock-nya).
"""

from __future__ import annotations

import threading
import time

import pytest
import redis
from cti_worker import beat_main
from cti_worker.beat_lock import LOCK_KEY, BeatLock


@pytest.fixture(autouse=True)
def _clean(redis_client: redis.Redis) -> None:
    redis_client.flushall()


def test_only_one_process_can_acquire(redis_client: redis.Redis) -> None:
    a = BeatLock(redis_client, ttl_ms=5000)
    b = BeatLock(redis_client, ttl_ms=5000)

    assert a.acquire() is True
    assert b.acquire() is False  # standby
    assert redis_client.get(LOCK_KEY) == a.token.encode()


def test_holder_can_renew_and_it_extends_the_ttl(redis_client: redis.Redis) -> None:
    a = BeatLock(redis_client, ttl_ms=10_000)
    a.acquire()
    redis_client.pexpire(LOCK_KEY, 500)  # simulasi TTL nyaris abis

    assert a.renew() is True

    assert redis_client.pttl(LOCK_KEY) > 5000


def test_non_holder_cannot_renew_or_release_someone_elses_lock(
    redis_client: redis.Redis,
) -> None:
    a = BeatLock(redis_client, ttl_ms=5000)
    b = BeatLock(redis_client, ttl_ms=5000)
    a.acquire()

    assert b.renew() is False
    assert b.release() is False
    assert redis_client.get(LOCK_KEY) == a.token.encode()  # lock A utuh


def test_release_lets_standby_take_over_immediately(redis_client: redis.Redis) -> None:
    a = BeatLock(redis_client, ttl_ms=60_000)  # TTL panjang: bukan TTL yang nolong
    b = BeatLock(redis_client, ttl_ms=60_000)
    a.acquire()

    assert a.release() is True
    assert b.acquire() is True

    assert a.release() is False  # A udah bukan pemilik, gak boleh ngehapus lock B
    assert redis_client.get(LOCK_KEY) == b.token.encode()


def test_crashed_leader_lock_expires_and_standby_takes_over(
    redis_client: redis.Redis,
) -> None:
    a = BeatLock(redis_client, ttl_ms=200)
    b = BeatLock(redis_client, ttl_ms=200)
    a.acquire()  # A "crash": gak pernah renew/release

    time.sleep(0.35)

    assert b.acquire() is True
    assert a.renew() is False  # A yang hidup lagi sadar dia udah bukan leader


# --- fail-stop --------------------------------------------------------------


class _Exited(Exception):
    pass


@pytest.fixture
def exits(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """`os._exit` di-patch: catat kode, lalu lempar biar loop yang lagi
    diuji berhenti (aslinya proses langsung mati)."""
    codes: list[int] = []

    def fake_exit(code: int) -> None:
        codes.append(code)
        raise _Exited

    monkeypatch.setattr(beat_main.os, "_exit", fake_exit)
    return codes


def test_renew_loop_exits_when_lock_was_taken_over(
    redis_client: redis.Redis, exits: list[int]
) -> None:
    a = BeatLock(redis_client, ttl_ms=300)
    b = BeatLock(redis_client, ttl_ms=5000)
    a.acquire()
    time.sleep(0.4)  # lock A kadaluarsa
    assert b.acquire()  # B ambil alih

    with pytest.raises(_Exited):
        beat_main._renew_loop(a, ttl_s=0.3, stop=threading.Event())

    assert exits == [1]


def test_renew_loop_keeps_renewing_while_we_hold_the_lock(
    redis_client: redis.Redis, exits: list[int]
) -> None:
    a = BeatLock(redis_client, ttl_ms=600)
    a.acquire()
    stop = threading.Event()
    t = threading.Thread(
        target=beat_main._renew_loop, kwargs={"lock": a, "ttl_s": 0.6, "stop": stop}
    )
    t.start()

    time.sleep(1.5)  # > 2x TTL: tanpa perpanjangan lock udah hilang
    still_ours = redis_client.get(LOCK_KEY) == a.token.encode()
    stop.set()
    t.join(timeout=2)

    assert still_ours
    assert exits == []


class _FlakyLock:
    """Redis putus: `renew()` selalu raise."""

    def renew(self) -> bool:
        raise redis.ConnectionError("redis mati")


def test_renew_loop_tolerates_redis_blip_but_exits_after_ttl(exits: list[int]) -> None:
    with pytest.raises(_Exited):
        beat_main._renew_loop(_FlakyLock(), ttl_s=0.45, stop=threading.Event())  # type: ignore[arg-type]

    assert exits == [1]
