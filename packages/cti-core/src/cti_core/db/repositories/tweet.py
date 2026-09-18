"""TweetRepo -- satu-satunya jalur tulis `tweets`. Gantiin `dbMongo.
upsert_tweet`/`tweet_exists` (`$setOnInsert`-only, gak pernah update tweet
yang udah ada -- dipertahankan di sini: sekali masuk, field mesin TIDAK
di-refresh, beda dari `ArticleRepo.upsert` yang emang didesain buat re-scrape.
Alasannya sama kayak lama: tweet gak berubah isinya setelah diposting,
beda dari artikel yang bisa di-edit penulisnya)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cti_core.db.models.tweet import Tweet


class TweetRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists(self, tweet_id: str) -> bool:
        return (
            self.session.execute(select(Tweet.id).where(Tweet.tweet_id == tweet_id)).first()
            is not None
        )

    def insert(self, *, tweet_id: str, url: str, text: str, **fields: Any) -> Tweet | None:
        """`None` kalau `tweet_id` udah ada -- caller cek `exists()` duluan
        kalau perlu tau alasannya, di sini insert aja/no-op diam-diam,
        setara return value `upsert_tweet()` lama (`True` kalau baru)."""
        existing = self.session.execute(select(Tweet.id).where(Tweet.tweet_id == tweet_id)).first()
        if existing is not None:
            return None

        row = Tweet(tweet_id=tweet_id, url=url, text=text, **fields)
        self.session.add(row)
        self.session.flush()
        return row

    def get_last_seen_id(self, author_username: str) -> str | None:
        """Ganti `state.json` (`monitorX.py::load_state/save_state`) --
        tweet ID terbesar yang udah tersimpan buat akun ini, dipakai
        sebagai `since_id` query berikutnya. MAX numerik, bukan MAX string
        (ID Twitter numerik tapi disimpen sebagai string)."""
        rows = (
            self.session.execute(
                select(Tweet.tweet_id).where(Tweet.author_username == author_username)
            )
            .scalars()
            .all()
        )
        if not rows:
            return None
        return max(rows, key=int)
