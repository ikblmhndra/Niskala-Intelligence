"""Helper tokenizer + penamaan cluster, dipakai BARENG dua pipeline
clustering (`cti_api.services.cluster`'s `get_clusters()` DAN
`cti_api.services.campaign`'s `get_recent_campaigns()`) -- port bagian
atas `cluster_service.py` (baris 1-214, sebelum `_persist_and_tag`).
Fase 7.4 Grup A (2026-09-23). Dipisah file sendiri (bukan digabung ke
salah satu pipeline) karena dipakai DUA-DUANYA, bukan spesifik satu."""

from __future__ import annotations

import hashlib
import re
from collections import Counter

_STOP_WORDS = frozenset(
    {
        "the", "a", "an", "is", "in", "on", "at", "to", "for", "of", "and", "or", "with",
        "by", "from", "as", "its", "it", "was", "are", "were", "has", "have", "had",
        "be", "been", "being", "their", "they", "this", "that", "these", "those",
        "after", "about", "over", "into", "out", "up", "down", "via", "more", "how",
        "what", "when", "where", "who", "why", "which", "says", "say", "said", "using",
        "used", "use", "can", "will", "now", "also", "just", "but", "not", "all", "our",
        "your", "than", "amid", "inside", "across", "against", "between", "per", "vs",
        "new", "top", "get", "got", "one", "two", "three", "first", "last", "next",
    }
)  # fmt: skip

_LOWERCASE_INNER = frozenset(
    {"and", "or", "of", "the", "in", "on", "at", "by", "for", "vs", "a", "an"}
)

_MONTHS = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
    }
)  # fmt: skip


def tokenize_for_dedup(title: str) -> frozenset[str]:
    tokens = re.sub(r"[^\w\s]", " ", title.lower()).split()
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 3)


def tfidf_tokenize(text: str) -> list[str]:
    cve_tokens = [m.lower() for m in re.findall(r"CVE-\d{4}-\d+", text, re.IGNORECASE)]
    text_no_cve = re.sub(r"CVE-\d{4}-\d+", " ", text, flags=re.IGNORECASE)
    words = re.sub(r"[^\w\s]", " ", text_no_cve.lower()).split()
    filtered = [w for w in words if w not in _STOP_WORDS and len(w) > 3]
    return cve_tokens + filtered


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _is_named_entity_token(tok: str, title: str) -> bool:
    if re.match(r"^cve-\d{4}-\d+$", tok):
        return True
    if re.match(r"^20\d{2}$", tok):
        return True
    if tok in _MONTHS:
        return True
    for word in title.split():
        w = re.sub(r"[^\w]", "", word)
        if w.lower() == tok and len(w) > 2 and w[0].isupper():
            return True
    return False


def confidence_label(source_count: int) -> str:
    if source_count >= 5:
        return "high"
    if source_count >= 3:
        return "medium"
    return "low"


def cluster_id(cluster_name: str) -> str:
    normalized = re.sub(r"\s+", " ", cluster_name.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def derive_cluster_name(titles: list[str]) -> str:
    """Ekstrak nama cluster pendek dari sekumpulan judul artikel. Entity
    bernama (CVE, tahun, proper noun) qualify di threshold frekuensi
    lebih rendah dan skor lebih tinggi pas seleksi run terbaik."""
    titles = [t.strip() for t in titles if t.strip()]
    if not titles:
        return "Unknown Cluster"
    if len(titles) == 1:
        return titles[0]

    n = len(titles)
    base_threshold = max(2, n * 0.5)
    entity_threshold = max(2, n * 0.3)

    freq: Counter[str] = Counter()
    for title in titles:
        toks: set[str] = set(re.sub(r"[^\w\s]", " ", title.lower()).split())
        for cve in re.findall(r"CVE-\d{4}-\d+", title, re.IGNORECASE):
            toks.add(cve.lower())
        for tok in toks:
            freq[tok] += 1

    core: set[str] = set()
    entity_tokens: set[str] = set()
    for tok, cnt in freq.items():
        if tok in _STOP_WORDS or len(tok) <= 2:
            continue
        is_ent = any(_is_named_entity_token(tok, t) for t in titles)
        if is_ent and cnt >= entity_threshold:
            core.add(tok)
            entity_tokens.add(tok)
        elif cnt >= base_threshold:
            core.add(tok)

    if not core:
        return titles[0]

    best_words: list[str] = []
    best_score = 0

    for title in titles:
        words = title.split()
        pairs: list[tuple[str, str]] = []
        for w in words:
            if re.match(r"CVE-\d{4}-\d+", w, re.IGNORECASE):
                pairs.append((w, w.lower()))
            else:
                pairs.append(
                    (re.sub(r"^[^\w]+|[^\w]+$", "", w), re.sub(r"[^\w]", "", w.lower()))
                )

        run: list[str] = []
        run_score = 0

        for display, lk in pairs:
            if lk in core:
                run.append(display)
                run_score += 3 if lk in entity_tokens else 1
            elif lk in _STOP_WORDS and run:
                run.append(display)
            else:
                while run and re.sub(r"[^\w]", "", run[-1].lower()) in _STOP_WORDS:
                    run.pop()
                if run and run_score > best_score:
                    best_score = run_score
                    best_words = run[:]
                run = []
                run_score = 0

        while run and re.sub(r"[^\w]", "", run[-1].lower()) in _STOP_WORDS:
            run.pop()
        if run and run_score > best_score:
            best_score = run_score
            best_words = run[:]

    if not best_words:
        return titles[0]

    cased = []
    for i, w in enumerate(best_words):
        lw = re.sub(r"[^\w]", "", w.lower())
        if i == 0 or lw not in _LOWERCASE_INNER:
            cased.append(w[0].upper() + w[1:] if w else w)
        else:
            cased.append(w.lower())

    return " ".join(cased)
