"""Ekstraktor AST per family. Prinsipnya: kenali bentuk KANONIK secara
presisi, dan kalau kodenya nyimpang dari itu (filter tambahan, logic
custom di dalam loop, dst), TANDAIN buat review manual -- JANGAN nebak
atau diam-diam ngasilin scraper yang salah. Contoh nyata yang kena:
`akamaiThreat.py` punya `if re.search("security", featured_link): ...` di
dalam loop -- itu bukan boilerplate RSS biasa, extractor ini harus
ngenalin dan nolak generate otomatis buat file itu.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RssExtraction:
    feeds: list[str] = field(default_factory=list)
    item_path: str = ".//item"
    title_path: str = "title"
    link_path: str = "link"
    date_path: str | None = None
    xml_fixups: list[tuple[str, str]] = field(default_factory=list)
    html_unescape: bool = False
    legacy_label: str | None = None
    needs_review: list[str] = field(default_factory=list)


@dataclass
class XPathExtraction:
    url: str | None = None
    title_xpath: str | None = None
    link_xpath: str | None = None
    base_url: str = ""
    indexed: bool = True
    max_items: int = 10
    wait_for: str | None = None
    legacy_label: str | None = None
    needs_review: list[str] = field(default_factory=list)


def _literal_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_top_level_str_assign(tree: ast.Module, name_contains: str) -> str | None:
    """Cari `xxx = 'literal'` di top-level modul, nama variabel ngandung
    `name_contains` (case-insensitive)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and name_contains.lower() in target.id.lower():
                val = _literal_str(node.value)
                if val:
                    return val
    return None


def _find_replace_chain(node: ast.AST) -> list[tuple[str, str]]:
    """Rantai `.replace("a", "b").replace("c", "d")` -- balikin
    [("a","b"), ("c","d")] urut dari yang PALING DALAM (paling awal
    dieksekusi) ke luar."""
    chain: list[tuple[str, str]] = []
    current = node
    while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
        if current.func.attr == "replace" and len(current.args) == 2:
            old = _literal_str(current.args[0])
            new = _literal_str(current.args[1])
            if old is not None and new is not None:
                chain.append((old, new))
        current = current.func.value
    chain.reverse()
    return chain


def _find_push_job_call(tree: ast.Module) -> ast.Call | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "push_job"
        ):
            return node
    return None


def _legacy_label(push_job_call: ast.Call | None) -> str | None:
    if push_job_call is None or len(push_job_call.args) < 2:
        return None
    return _literal_str(push_job_call.args[1])


def _find_for_loop_over_findall(tree: ast.Module) -> ast.For | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
            call = node.iter
            if isinstance(call.func, ast.Attribute) and call.func.attr == "findall":
                return node
    return None


_ALLOWED_LOOP_NODE_TYPES = (
    ast.Assign,
    ast.If,  # ditelusuri lebih lanjut -- cuma if is_new_and_mark(...) yang diizinin
    ast.Expr,
    ast.Pass,
)


def _loop_body_is_canonical(for_node: ast.For) -> list[str]:
    """Balikin daftar alasan kalau body loop NYIMPANG dari pola kanonik
    (title/link assign -> key -> if is_new_and_mark: push_job). List kosong
    = kanonik, aman digenerate otomatis."""
    reasons = []
    for stmt in for_node.body:
        if isinstance(stmt, ast.Assign):
            continue  # title_el = ..., key = ..., dst -- normal
        if isinstance(stmt, ast.If):
            test = stmt.test
            is_dedup_check = (
                isinstance(test, ast.Call)
                and isinstance(test.func, ast.Name)
                and test.func.id == "is_new_and_mark"
            )
            if not is_dedup_check:
                cond_src = ast.dump(test)[:60]
                reasons.append(f"ada if selain dedup-check di dalam loop: {cond_src}")
            # else: telusuri isi -- boleh ada assign lain + push_job di dalamnya,
            # gak divalidasi lebih detail, itu emang variasi normal (mis. base_url join)
        else:
            reasons.append(f"statement gak dikenal di loop: {type(stmt).__name__}")
    return reasons


def extract_rss(path: Path) -> RssExtraction:
    result = RssExtraction()
    try:
        tree = ast.parse(path.read_text(errors="ignore"), filename=str(path))
    except SyntaxError as e:
        result.needs_review.append(f"SyntaxError: {e}")
        return result

    # feed URL(s)
    url = _find_top_level_str_assign(tree, "url")
    if url:
        result.feeds = [url]
    else:
        # xxx_list = [...] -- daftar literal. Dicek dari ISI-nya (semua
        # elemen literal string yang mulai "http"), BUKAN nama variabelnya --
        # `articThreat.py` makainya "link_list", bukan "url_list"/"urls",
        # dan gak ada alasan buat nebak-nebak konvensi penamaan kalau
        # kontennya sendiri udah jelas nunjuk kumpulan URL feed.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                t = node.targets[0]
                if isinstance(t, ast.Name) and isinstance(node.value, ast.List) and node.value.elts:
                    literals = [_literal_str(el) for el in node.value.elts]
                    if all(lit and lit.startswith("http") for lit in literals):
                        result.feeds = [lit for lit in literals if lit]
                        break
    if not result.feeds:
        result.needs_review.append("gak nemu assignment URL feed literal")

    # xml fixups -- rantai .replace() di argumen ET.fromstring(...), dan
    # apakah seluruh argumen itu dibungkus html.unescape(...)/html_lib.unescape(...).
    # Pola ini muncul di 51/52 scraper RSS lama yang punya rantai .replace() --
    # tanpa unescape, entity numerik yang udah valid (mis. "&#038;") kena
    # double-escape sama .replace("&","&amp;") terus gak pernah ke-decode.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fromstring"
        ):
            fromstring_arg = node.args[0] if node.args else None
            if (
                isinstance(fromstring_arg, ast.Call)
                and isinstance(fromstring_arg.func, ast.Attribute)
                and fromstring_arg.func.attr == "unescape"
            ):
                result.html_unescape = True
            for arg in ast.walk(node):
                if (
                    isinstance(arg, ast.Call)
                    and isinstance(arg.func, ast.Attribute)
                    and arg.func.attr == "replace"
                ):
                    result.xml_fixups = _find_replace_chain(arg)
                    break

    # for-loop atas root.findall(...)
    for_node = _find_for_loop_over_findall(tree)
    if for_node is None:
        result.needs_review.append("gak nemu 'for X in root.findall(...)'")
        return result

    findall_call = for_node.iter
    assert isinstance(findall_call, ast.Call)
    item_path = _literal_str(findall_call.args[0]) if findall_call.args else None
    if item_path:
        result.item_path = item_path

    # title_el = item.find('...'), link_el = item.find('...')
    for stmt in ast.walk(for_node):
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            var_name = stmt.targets[0].id.lower()
            call = stmt.value
            # `str(item.find('x').text)...` dibungkus str()/.strip() -- gali sampai .find()
            probe = call
            while (
                isinstance(probe, ast.Call)
                and probe.args
                and not (isinstance(probe.func, ast.Attribute) and probe.func.attr == "find")
            ):
                probe = probe.args[0] if probe.args else None
                if probe is None:
                    break
            find_call = probe
            if (
                isinstance(find_call, ast.Attribute)
                and find_call.attr == "text"
                and isinstance(find_call.value, ast.Call)
                and isinstance(find_call.value.func, ast.Attribute)
                and find_call.value.func.attr == "find"
            ):
                find_call = find_call.value
            if (
                isinstance(find_call, ast.Call)
                and isinstance(find_call.func, ast.Attribute)
                and find_call.func.attr == "find"
                and find_call.args
            ):
                path_literal = _literal_str(find_call.args[0])
                if path_literal and ("title" in var_name):
                    result.title_path = path_literal
                elif path_literal and ("link" in var_name or "url" in var_name):
                    result.link_path = path_literal
                elif path_literal and ("date" in var_name or "pub" in var_name):
                    result.date_path = path_literal

    result.legacy_label = _legacy_label(_find_push_job_call(tree))

    result.needs_review.extend(_loop_body_is_canonical(for_node))
    return result


def _find_base_url_concat(tree: ast.Module) -> str | None:
    """Pola umum di scraper lama (28 file): `"url": "https://situs.com" +
    article_url` di dalam dict literal -- href dari halaman aslinya relatif,
    di-absolut-kan manual sebelum push_job(). Balikin literal-nya kalau
    ketemu; `XPathScraper.base_url` udah punya urljoin() bawaan buat ini,
    tinggal diisi (lihat bizoneThreat.py)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=False):
            key_lit = _literal_str(key)
            if not key_lit or not ("url" in key_lit.lower() or "link" in key_lit.lower()):
                continue
            if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
                left_lit = _literal_str(value.left)
                if left_lit and left_lit.startswith("http"):
                    return left_lit
    return None


def extract_xpath(path: Path, *, runtime: str) -> XPathExtraction:
    """`runtime`: "light" (requests+lxml) atau "browser" (playwright)."""
    result = XPathExtraction()
    try:
        tree = ast.parse(path.read_text(errors="ignore"), filename=str(path))
    except SyntaxError as e:
        result.needs_review.append(f"SyntaxError: {e}")
        return result

    # URL: literal argumen pertama requests.get(...) atau page.goto(...)
    target_call_attr = "goto" if runtime == "browser" else "get"
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == target_call_attr
            and node.args
        ):
            url = _literal_str(node.args[0])
            if url:
                result.url = url
                break
    if not result.url:
        result.needs_review.append(f"gak nemu literal URL di panggilan .{target_call_attr}(...)")

    # range(1, N) -> max_items
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and len(node.args) == 2
        ):
            lo, hi = node.args
            if (
                isinstance(lo, ast.Constant)
                and lo.value == 1
                and isinstance(hi, ast.Constant)
                and isinstance(hi.value, int)
            ):
                result.max_items = hi.value - 1
                break

    # XPath f-string dgn {i} -- cari 2 pola (title/link) di .xpath(...) atau
    # .locator(...).text_content()/.get_attribute("href")
    xpaths: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            xp = _joined_str_to_template(node)
            if xp and "{i}" in xp:
                # `page.locator(f"xpath=/html/...")` -- "xpath=" itu sintaks
                # SELECTOR Playwright, bukan bagian XPath-nya. Framework kita
                # selalu parse lewat lxml (`tree.xpath(...)`) walau HTML-nya
                # datang dari Playwright (lihat XPathScraper._get_html) --
                # prefix ini HARUS dibuang, kalau kebawa scraper hasil
                # generate bakal nge-xpath string yang gak valid.
                xp = xp.removeprefix("xpath=")
                xpaths.append(xp)
    # dedup jaga urutan
    seen: set[str] = set()
    uniq = [x for x in xpaths if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]

    if runtime == "browser" and len(uniq) == 1:
        # satu base path dipakai buat title (/text()) DAN link (/@href) lewat
        # .text_content()/.get_attribute() -- lihat trendmicroThreat.py
        base = uniq[0]
        result.title_xpath = f"{base}/text()" if not base.endswith(("/text()", "/@href")) else base
        result.link_xpath = f"{base}/@href" if not base.endswith(("/text()", "/@href")) else base
    elif len(uniq) >= 2:
        # heuristik: yang match "@href"/".get('href'..." pola dianggap link
        for xp in uniq:
            if xp.endswith("/@href") or xp.endswith("/text()"):
                if xp.endswith("/@href"):
                    result.link_xpath = xp
                else:
                    result.title_xpath = xp
        if result.title_xpath is None or result.link_xpath is None:
            result.title_xpath, result.link_xpath = uniq[0], uniq[1]
    else:
        result.needs_review.append(
            f"XPath ter-ekstrak {len(uniq)} (butuh 1 atau 2 dgn placeholder {{i}})"
        )

    result.base_url = _find_base_url_concat(tree) or ""
    result.legacy_label = _legacy_label(_find_push_job_call(tree))
    return result


def _joined_str_to_template(node: ast.JoinedStr) -> str | None:
    """f"...{i}..." -> "...{i}..." (placeholder dipertahankan APA ADANYA
    kalau nama variabelnya `i`, selain itu None -- gak mau nebak placeholder
    lain)."""
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
            if value.value.id != "i":
                return None
            parts.append("{i}")
        else:
            return None
    return "".join(parts)
