"""Adaptasi dari `ScraperNewsWeb/app/models/ta_group.py` -- `id` sekarang
`int` (Postgres bigint), BUKAN `str` (Mongo ObjectId hex)."""

from __future__ import annotations

from pydantic import BaseModel


class TAGroupOut(BaseModel):
    id: int
    name: str
    added_date: str
    source: str


class TAGroupAdd(BaseModel):
    name: str


class TAGroupListResponse(BaseModel):
    groups: list[TAGroupOut]
    total: int
    page: int
    page_size: int


class TAWhitelistOut(BaseModel):
    id: int
    name: str
    added_date: str


class TAWhitelistListResponse(BaseModel):
    items: list[TAWhitelistOut]
    total: int
    page: int
    page_size: int


class TAWatchlistOut(BaseModel):
    id: int
    name: str
    added_date: str
    dormancy_state: str = "DORMANT"


class TAWatchlistListResponse(BaseModel):
    items: list[TAWatchlistOut]
    total: int
    page: int
    page_size: int
