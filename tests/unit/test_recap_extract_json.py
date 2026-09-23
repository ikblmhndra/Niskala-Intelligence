"""Unit test `cti_api.services.recap._extract_json()` -- fungsi murni,
gak butuh DB. Fase 7.5: dulu regex sendiri, sekarang numpang
`cti_core.llm.client.parse_json_response()` -- test ini mastiin
kontrak lama (gak pernah raise, fallback `{"_raw": raw}`) tetap sama
persis pasca refactor."""

from __future__ import annotations

from cti_api.services import recap as svc


def test_extract_json_empty_returns_empty_dict() -> None:
    assert svc._extract_json("") == {}


def test_extract_json_plain_json() -> None:
    assert svc._extract_json('{"headline": "hi"}') == {"headline": "hi"}


def test_extract_json_strips_code_fence() -> None:
    raw = '```json\n{"headline": "hi"}\n```'
    assert svc._extract_json(raw) == {"headline": "hi"}


def test_extract_json_strips_think_block() -> None:
    raw = '<think>thinking...</think>{"headline": "hi"}'
    assert svc._extract_json(raw) == {"headline": "hi"}


def test_extract_json_unparseable_falls_back_to_raw_sentinel() -> None:
    raw = "the model refused to answer in JSON"
    assert svc._extract_json(raw) == {"_raw": raw}
