"""Snapshot test `routers/pkg_vuln.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`).

`add_package()` (registry existence check), `scan_package()`/
`scan_all_packages()`/`resolve_package_deps()` (osv.dev + registry
lookup) SEMUA panggil jaringan asli -- di-mock di titik yang sama
(`cti_api.services.pkg_vuln`, module-level function). Endpoint yang
nge-trigger `BackgroundTasks` (`scan`/`resolve-deps`/`import-lockfile`)
beneran ke-`await` SEBELUM response balik (`ASGITransport`, sama
observasi kayak `test_attack_router_snapshot.py`)."""

from __future__ import annotations

import contextlib
import datetime
from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, patch

import pytest
from cti_api.services import pkg_vuln as pkg_vuln_service
from cti_core.db.models.package import MonitoredPackage, PackageVuln
from cti_core.db.repositories.package import AsyncPackageVulnRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {
        r"(.*\.)?id$": (int,),
        r"(.*\.)?added_date$": (str,),
        r"(.*\.)?last_scan$": (str,),
        r"(.*\.)?dep_resolved_at$": (str,),
        r"(.*\.)?resolved_at$": (str,),
    },
    regex=True,
    strict=False,
)


@contextlib.contextmanager
def _no_network(*, registry_exists: bool = True) -> Iterator[None]:
    """Semua panggilan jaringan asli `pkg_vuln.py` (registry existence
    check + osv.dev scan/resolve-deps) di-mock sekaligus -- dipakai tiap
    endpoint yang (langsung atau lewat `BackgroundTasks`) bisa nyentuh
    salah satu dari titik ini."""
    with (
        patch.object(
            pkg_vuln_service, "_package_exists_on_registry", AsyncMock(return_value=registry_exists)
        ),
        patch.object(pkg_vuln_service, "scan_package", AsyncMock(return_value={})),
        patch.object(pkg_vuln_service, "scan_all_packages", AsyncMock(return_value={})),
        patch.object(pkg_vuln_service, "resolve_package_deps", AsyncMock(return_value={})),
    ):
        yield


async def _seed_package(session: AsyncSession) -> MonitoredPackage:
    pkg = MonitoredPackage(
        name="lodash",
        ecosystem="npm",
        version="4.17.20",
        client_id="default",
        added_date=datetime.date(2026, 9, 1),
        vuln_count=1,
        critical_count=1,
        highest_severity="CRITICAL",
    )
    session.add(pkg)
    await session.flush()
    session.add(
        PackageVuln(
            package_name="lodash",
            ecosystem="npm",
            pinned_version="4.17.20",
            advisory_id="GHSA-1234",
            severity="CRITICAL",
            client_id="default",
            last_updated=datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC),
        )
    )
    await session.flush()
    return pkg


async def test_get_packages(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_package(api_session)
    resp = await api_client.get("/api/pkgvuln/packages", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_post_package(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    with _no_network():
        resp = await api_client.post(
            "/api/pkgvuln/packages",
            headers=auth_header(),
            json={"name": "express", "ecosystem": "npm", "version": None},
        )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_patch_package(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    pkg = await _seed_package(api_session)
    with _no_network():
        resp = await api_client.patch(
            f"/api/pkgvuln/packages/{pkg.id}", headers=auth_header(), json={"version": "4.17.21"}
        )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_remove_package(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    pkg = await _seed_package(api_session)
    resp = await api_client.delete(f"/api/pkgvuln/packages/{pkg.id}", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_resolve_deps(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    pkg = await _seed_package(api_session)
    with _no_network():
        resp = await api_client.post(
            f"/api/pkgvuln/packages/{pkg.id}/resolve-deps", headers=auth_header()
        )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_get_deps_not_found(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    pkg = await _seed_package(api_session)
    resp = await api_client.get(f"/api/pkgvuln/packages/{pkg.id}/deps", headers=auth_header())
    assert resp.status_code == 404
    assert resp.json() == snapshot


async def test_scan_one_package(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    pkg = await _seed_package(api_session)
    with _no_network():
        resp = await api_client.post(f"/api/pkgvuln/packages/{pkg.id}/scan", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_scan_all(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    with _no_network():
        resp = await api_client.post("/api/pkgvuln/scan", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_import_lockfile(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    with _no_network():
        resp = await api_client.post(
            "/api/pkgvuln/import-lockfile",
            headers=auth_header(),
            files={"file": ("package.json", b'{"dependencies": {"lodash": "^4.17.20"}}')},
        )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_get_vulns(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_package(api_session)
    resp = await api_client.get("/api/pkgvuln/vulns", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_ack_vuln(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_package(api_session)
    vulns, _ = await AsyncPackageVulnRepo(api_session).list_filtered("default")
    resp = await api_client.patch(f"/api/pkgvuln/vulns/{vulns[0].id}/ack", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_get_pkg_stats(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_package(api_session)
    resp = await api_client.get("/api/pkgvuln/stats", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot
