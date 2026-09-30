"""GithubCommitWatcher -- pantau commit sebuah repo GitHub, kabari Telegram
(Fase 10.E). Gantiin empat skrip lama yang salinannya nyaris sama:
`githubTTPs`, `githubSophoslab`, `githubAptTTPSimulation`, `mitreGithub`.

Bedanya cuma: repo mana, berapa commit yang dilihat, commit mana yang
dilewati, dan bentuk pesan -- semuanya jadi hook di subclass. Yang SAMA dan
dulu ditulis ulang tiap skrip (dan tiap skrip punya bug-nya sendiri):

  - Auth token: `meta.credential="github"` (skrip lama: `commit_detail`
    Sophoslab dipanggil TANPA header auth -> kena rate limit anonim 60/jam).
  - Dedup: `NoticeItem.key` (biasanya `"<sha>:<file>"`), bukan file offset
    lokal (`offset/githubsha.txt`, yang hilang tiap container di-restart).
  - Kegagalan API (rate limit 403, repo pindah 404): `ParseError`, bukan
    `KeyError`/`response[0]` yang meledak di tengah loop.

Subclass cukup ngisi `owner`/`repo` dan `notices()`.
"""

from __future__ import annotations

import contextlib
import datetime
from abc import abstractmethod
from collections.abc import Iterator
from typing import Any, ClassVar

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.errors import ParseError
from cti_scraper.items import NoticeItem

_API = "https://api.github.com/repos"


class GithubCommitWatcher(BaseScraper):
    __abstract__ = True

    owner: ClassVar[str]
    repo: ClassVar[str]
    max_commits: ClassVar[int] = 5
    """Cuma N commit TERBARU yang dilihat tiap run."""
    max_age_days: ClassVar[int | None] = None
    """Commit yang lebih tua dari ini dilewati (`None` = tanpa batas umur)."""

    @classmethod
    def commits_url(cls) -> str:
        return f"{_API}/{cls.owner}/{cls.repo}/commits"

    def fetch(self, ctx: ScrapeContext) -> Iterator[NoticeItem]:
        url = self.commits_url()
        commits = self._get_json(ctx, url)
        if not isinstance(commits, list):
            raise ParseError(f"{url}: diharap list commit, dapat {type(commits).__name__}")

        found = 0
        for summary in commits[: self.max_commits]:
            if self.skip_commit(ctx, summary):
                continue
            detail = self._get_json(ctx, f"{url}/{summary['sha']}")
            if not isinstance(detail, dict):
                raise ParseError(f"{url}/{summary['sha']}: detail commit bukan objek JSON")
            for notice in self.notices(ctx, summary, detail):
                if found >= self.meta.max_items:
                    return
                found += 1
                yield notice

    @staticmethod
    def _get_json(ctx: ScrapeContext, url: str) -> Any:
        resp = ctx.http.get(url)
        if resp.status_code != 200:
            message = ""
            with contextlib.suppress(ValueError, AttributeError):
                message = str(resp.json().get("message", ""))[:200]
            raise ParseError(f"{url}: HTTP {resp.status_code} {message}".strip())
        try:
            return resp.json()
        except ValueError as e:
            raise ParseError(f"{url}: respons bukan JSON valid -- {e}") from e

    def skip_commit(self, ctx: ScrapeContext, summary: dict[str, Any]) -> bool:
        """Default: cuma batas umur. Override buat filter lain (pesan commit, dst)."""
        if self.max_age_days is None:
            return False
        committed = commit_date(summary)
        return (ctx.now - committed).days >= self.max_age_days

    @abstractmethod
    def notices(
        self, ctx: ScrapeContext, summary: dict[str, Any], detail: dict[str, Any]
    ) -> Iterator[NoticeItem]:
        """Nol atau lebih notice dari SATU commit. `summary` = elemen daftar
        commit, `detail` = respons `/commits/<sha>` (ada `files`)."""


def commit_date(summary: dict[str, Any]) -> datetime.datetime:
    """Tanggal committer commit, naif UTC (sama dengan `ScrapeContext.now`)."""
    raw = summary["commit"]["committer"]["date"]
    return datetime.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
