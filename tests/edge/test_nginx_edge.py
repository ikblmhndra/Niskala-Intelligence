"""Edge nginx (docker/nginx.Dockerfile + docker/nginx/): generator sertifikat self-signed,
konfigurasi proxy, dan kabel compose-nya.

Container BENERAN (docker CLI), bukan mock: yang mau dibuktikan adalah perilaku nginx/openssl
sungguhan -- SAN sertifikat, header X-Forwarded-For, resolusi ulang upstream -- dan itu tidak bisa
dibuktikan tanpa mereka. Skip kalau Docker tidak tersedia. Butuh jaringan sekali (build image:
`apk add openssl`).

Tiap bug di bawah pernah (atau hampir) terjadi: nginx menyimpan IP `web` selamanya setelah recreate
(502 sampai restart), `$host` membuang port, XFF tidak ditambah (rate limit login mengunci semua
orang).
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import pathlib
import re
import shutil
import socket
import ssl
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
IMAGE = "cti-nginx-edge-test:1"
HOOK = "/docker-entrypoint.d/05-selfsigned-cert.sh"
CRT = "/etc/nginx/tls/cti.crt"
KEY = "/etc/nginx/tls/cti.key"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker tidak tersedia")


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=240)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"docker {' '.join(args)[:200]} gagal ({proc.returncode}): {proc.stderr.strip()[-600:]}"
        )
    return proc


# --------------------------------------------------------------------------------------------------
# fixture
# --------------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def image(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Build dari salinan file di direktori sementara (bukan context repo penuh): cepat, dan tidak
    tergantung .dockerignore. `tls/` sengaja tidak ikut -- itu tempat KUNCI PRIVAT operator."""
    ctx = tmp_path_factory.mktemp("nginx-ctx")
    (ctx / "docker").mkdir()
    shutil.copy(REPO / "docker/nginx.Dockerfile", ctx / "docker/nginx.Dockerfile")
    shutil.copytree(
        REPO / "docker/nginx", ctx / "docker/nginx", ignore=shutil.ignore_patterns("tls")
    )
    docker("build", "-q", "-f", str(ctx / "docker/nginx.Dockerfile"), "-t", IMAGE, str(ctx))
    return IMAGE


@pytest.fixture()
def tls_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "tls"
    d.mkdir()
    return d


@pytest.fixture()
def net() -> Iterator[str]:
    name = f"cti-edge-test-{uuid.uuid4().hex[:8]}"
    docker("network", "create", name)
    try:
        yield name
    finally:
        ids = docker("ps", "-aq", "--filter", f"network={name}", check=False).stdout.split()
        if ids:
            docker("rm", "-f", *ids, check=False)
        docker("network", "rm", name, check=False)


# --------------------------------------------------------------------------------------------------
# helper: generator sertifikat
# --------------------------------------------------------------------------------------------------


def run_hook(
    image: str, tls_dir: pathlib.Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    args = ["run", "--rm", "-v", f"{tls_dir}:/etc/nginx/tls", "--entrypoint", HOOK]
    for k, v in (env or {}).items():
        args += ["-e", f"{k}={v}"]
    return docker(*args, image, check=False)


def sh(image: str, tls_dir: pathlib.Path, script: str) -> subprocess.CompletedProcess[str]:
    return docker(
        "run", "--rm", "-v", f"{tls_dir}:/etc/nginx/tls", "--entrypoint", "sh", image, "-c", script,
        check=False,
    )  # fmt: skip


def san_of(image: str, tls_dir: pathlib.Path) -> str:
    out = sh(image, tls_dir, f"openssl x509 -noout -ext subjectAltName -in {CRT}").stdout
    return "".join(out.splitlines()[1:]).replace(" ", "").replace("IPAddress:", "IP:")


def fingerprint(image: str, tls_dir: pathlib.Path) -> str:
    out = sh(image, tls_dir, f"openssl x509 -noout -fingerprint -sha256 -in {CRT}").stdout.strip()
    assert out.startswith("sha256 Fingerprint="), out
    return out


def digests(image: str, tls_dir: pathlib.Path) -> str:
    return sh(image, tls_dir, f"sha256sum {CRT} {KEY}").stdout


def pub_hashes(image: str, tls_dir: pathlib.Path) -> tuple[str, str]:
    crt = sh(image, tls_dir, f"openssl x509 -noout -pubkey -in {CRT} | openssl sha256").stdout
    key = sh(image, tls_dir, f"openssl pkey -pubout -in {KEY} | openssl sha256").stdout
    return crt.strip(), key.strip()


# --------------------------------------------------------------------------------------------------
# generator sertifikat self-signed
# --------------------------------------------------------------------------------------------------


def test_generates_cert_with_expected_san_and_locked_down_key(image, tls_dir):
    res = run_hook(image, tls_dir, {"NGINX_TLS_HOSTS": "cti.example.internal, 172.25.1.77"})

    assert res.returncode == 0, res.stderr
    assert "sertifikat self-signed dibuat (belum ada)" in res.stdout
    # localhost + 127.0.0.1 SELALU ada; IP dan DNS terklasifikasi benar; spasi di daftar diabaikan
    assert (
        san_of(image, tls_dir)
        == "DNS:localhost,IP:127.0.0.1,DNS:cti.example.internal,IP:172.25.1.77"
    )
    assert (
        "cti.example.internal"
        in sh(image, tls_dir, f"openssl x509 -noout -subject -in {CRT}").stdout
    )
    ext = sh(
        image, tls_dir, f"openssl x509 -noout -ext basicConstraints,extendedKeyUsage -in {CRT}"
    ).stdout
    assert "CA:FALSE" in ext and "TLS Web Server Authentication" in ext
    # kunci privat hanya bisa dibaca pemiliknya; tidak ada sisa direktori sementara
    modes = sh(image, tls_dir, f"stat -c '%a %n' {KEY} {CRT}").stdout.split("\n")
    assert f"600 {KEY}" in modes and f"644 {CRT}" in modes
    assert sh(image, tls_dir, "ls -A /etc/nginx/tls").stdout.split() == ["cti.crt", "cti.key"]
    # berlaku ~365 hari: lewat 364, habis sebelum 366
    assert (
        sh(image, tls_dir, f"openssl x509 -noout -checkend {364 * 86400} -in {CRT}").returncode == 0
    )
    assert (
        sh(image, tls_dir, f"openssl x509 -noout -checkend {366 * 86400} -in {CRT}").returncode == 1
    )


def test_key_matches_certificate(image, tls_dir):
    run_hook(image, tls_dir)
    crt, key = pub_hashes(image, tls_dir)
    assert crt and crt == key


def test_second_start_keeps_the_same_certificate(image, tls_dir):
    env = {"NGINX_TLS_HOSTS": "cti.example.internal"}
    run_hook(image, tls_dir, env)
    first = fingerprint(image, tls_dir)

    again = run_hook(image, tls_dir, env)

    assert "dipakai apa adanya" in again.stdout
    assert fingerprint(image, tls_dir) == first  # yang sudah memercayainya tidak perlu mengulang


def test_regenerates_when_host_list_changes(image, tls_dir):
    run_hook(image, tls_dir, {"NGINX_TLS_HOSTS": "old.example.internal"})
    first = fingerprint(image, tls_dir)

    res = run_hook(image, tls_dir, {"NGINX_TLS_HOSTS": "new.example.internal,10.1.2.3"})

    assert "daftar host berubah" in res.stdout
    assert fingerprint(image, tls_dir) != first
    assert (
        san_of(image, tls_dir) == "DNS:localhost,IP:127.0.0.1,DNS:new.example.internal,IP:10.1.2.3"
    )


def test_renews_when_close_to_expiry(image, tls_dir):
    run_hook(image, tls_dir, {"NGINX_TLS_DAYS": "10"})  # 10 hari < ambang 30 hari
    first = fingerprint(image, tls_dir)

    res = run_hook(image, tls_dir)  # start berikutnya, default 365 hari

    assert "kedaluwarsa dalam <= 30 hari" in res.stdout
    assert fingerprint(image, tls_dir) != first
    assert (
        sh(image, tls_dir, f"openssl x509 -noout -checkend {300 * 86400} -in {CRT}").returncode == 0
    )


def test_operator_certificate_is_never_touched(image, tls_dir):
    """Sertifikat dari CA internal: TIDAK BOLEH ditimpa -- walau hampir kedaluwarsa dan daftar host
    berbeda (dua-duanya akan memicu pembuatan ulang kalau ini sertifikat buatan skrip)."""
    made = sh(
        image,
        tls_dir,
        "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=corp.internal "
        f"-keyout {KEY} -out {CRT} >/dev/null 2>&1",
    )
    assert made.returncode == 0
    before = digests(image, tls_dir)

    res = run_hook(image, tls_dir, {"NGINX_TLS_HOSTS": "something.else.internal"})

    assert res.returncode == 0
    assert "tidak diubah" in res.stdout
    assert digests(image, tls_dir) == before


def test_half_pair_fails_loudly_and_changes_nothing(image, tls_dir):
    (tls_dir / "cti.key").write_text("bukan kunci sungguhan")

    res = run_hook(image, tls_dir)

    assert res.returncode != 0
    assert "hanya salah satu" in res.stderr
    assert sorted(p.name for p in tls_dir.iterdir()) == ["cti.key"]
    assert (tls_dir / "cti.key").read_text() == "bukan kunci sungguhan"


def test_replaced_key_is_detected_and_certificate_regenerated(image, tls_dir):
    run_hook(image, tls_dir)
    swapped = sh(
        image, tls_dir, f"openssl genrsa -out {KEY} 2048 >/dev/null 2>&1 && chmod 600 {KEY}"
    )
    assert swapped.returncode == 0
    crt, key = pub_hashes(image, tls_dir)
    assert crt != key  # prasyarat: sekarang memang tidak cocok

    res = run_hook(image, tls_dir)

    assert "kunci tidak cocok dengan sertifikat" in res.stdout
    crt, key = pub_hashes(image, tls_dir)
    assert crt == key


def test_wildcards_ips_and_duplicates(image, tls_dir):
    res = run_hook(
        image,
        tls_dir,
        {"NGINX_TLS_HOSTS": "*.corp.local, 10.0.0.5,localhost,127.0.0.1,cti.corp.local,10.0.0.5"},
    )

    assert res.returncode == 0, res.stderr
    # localhost / 127.0.0.1 / 10.0.0.5 yang berulang tidak digandakan; wildcard tidak diperluas glob
    assert san_of(image, tls_dir) == (
        "DNS:localhost,IP:127.0.0.1,DNS:*.corp.local,IP:10.0.0.5,DNS:cti.corp.local"
    )


@pytest.mark.parametrize(
    ("hosts", "message"),
    [
        ("::1", "IPv6 belum didukung"),
        ("fe80::1,cti.example.internal", "IPv6 belum didukung"),
        ("bad;host", "nama host tidak valid"),
        ("a b$c", "nama host tidak valid"),
        ("999.1.1.1", "alamat IPv4 tidak valid"),
        ("1.2.3", "alamat IPv4 tidak valid"),
    ],
)
def test_invalid_hosts_are_rejected_without_writing_anything(image, tls_dir, hosts, message):
    res = run_hook(image, tls_dir, {"NGINX_TLS_HOSTS": hosts})

    assert res.returncode != 0
    assert message in res.stderr
    assert list(tls_dir.iterdir()) == []


@pytest.mark.parametrize("var", ["NGINX_TLS_DAYS", "NGINX_TLS_RENEW_DAYS"])
def test_non_numeric_validity_is_rejected(image, tls_dir, var):
    res = run_hook(image, tls_dir, {var: "abc"})

    assert res.returncode != 0
    assert var in res.stderr
    assert list(tls_dir.iterdir()) == []


# --------------------------------------------------------------------------------------------------
# helper: nginx + upstream palsu bernama `web`
# --------------------------------------------------------------------------------------------------

# Upstream palsu: memantulkan header yang diterimanya sebagai `kunci=nilai` per baris.
_ECHO = "\\n".join(
    [
        "id={ident}",
        "host=$http_host",
        "xff=$http_x_forwarded_for",
        "real_ip=$http_x_real_ip",
        "proto=$http_x_forwarded_proto",
        "xfhost=$http_x_forwarded_host",
        "uri=$request_uri",
        "",
    ]
)
UPSTREAM_CONF = (
    """
pid /tmp/up.pid;
error_log /dev/stderr;
events {{}}
http {{
    access_log off;
    client_max_body_size 100m;  # batas 20m harus datang dari EDGE, bukan dari upstream palsu
    server {{
        listen 3000;
        location / {{
            default_type text/plain;
            return 200 "@@ECHO@@";
        }}
    }}
}}
"""
).replace("@@ECHO@@", _ECHO)


@dataclass
class Edge:
    name: str
    https_port: int
    http_port: int


@dataclass
class Resp:
    status: int
    headers: dict[str, str]
    body: str

    @property
    def fields(self) -> dict[str, str]:
        return dict(line.split("=", 1) for line in self.body.splitlines() if "=" in line)


def start_upstream(image: str, net: str, tmp_path: pathlib.Path, ident: str) -> str:
    conf = tmp_path / f"up-{ident}.conf"
    conf.write_text(UPSTREAM_CONF.format(ident=ident))
    name = f"cti-edge-test-up-{ident}-{uuid.uuid4().hex[:6]}"
    docker(
        "run", "-d", "--rm", "--name", name, "--network", net, "--network-alias", "web",
        "-v", f"{conf}:/up.conf:ro", "--entrypoint", "nginx", image,
        "-c", "/up.conf", "-g", "daemon off;",
    )  # fmt: skip
    return name


def _mapped_port(name: str, container_port: int) -> int:
    out = docker("port", name, f"{container_port}/tcp").stdout.splitlines()
    return int(out[0].rsplit(":", 1)[1])


def start_edge(
    image: str, net: str, tls_dir: pathlib.Path, env: dict[str, str] | None = None
) -> Edge:
    name = f"cti-edge-test-nginx-{uuid.uuid4().hex[:6]}"
    args = [
        "run", "-d", "--rm", "--name", name, "--network", net,
        "-v", f"{tls_dir}:/etc/nginx/tls", "-p", "127.0.0.1::443", "-p", "127.0.0.1::80",
        "-e", "NGINX_TLS_HOSTS=cti.test",
    ]  # fmt: skip
    for k, v in (env or {}).items():
        args += ["-e", f"{k}={v}"]
    docker(*args, image)
    edge = Edge(name, _mapped_port(name, 443), _mapped_port(name, 80))
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if https(edge, "/nginx-health").status == 200:
                return edge
        except OSError:
            pass
        time.sleep(0.3)
    logs = docker("logs", name, check=False)
    raise AssertionError(
        f"nginx tidak siap dalam 20 dtk:\n{logs.stdout[-800:]}{logs.stderr[-800:]}"
    )


def _do(conn: http.client.HTTPConnection, method, path, headers, body) -> Resp:
    conn.request(method, path, body=body, headers=headers or {})
    r = conn.getresponse()
    data = r.read().decode(errors="replace")
    resp = Resp(r.status, {k.lower(): v for k, v in r.getheaders()}, data)
    conn.close()
    return resp


def https(edge: Edge, path: str, method: str = "GET", headers=None, body=None) -> Resp:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection("127.0.0.1", edge.https_port, context=ctx, timeout=15)
    return _do(conn, method, path, headers, body)


def plain(edge: Edge, path: str, headers=None) -> Resp:
    conn = http.client.HTTPConnection("127.0.0.1", edge.http_port, timeout=15)
    return _do(conn, "GET", path, headers, None)


# --------------------------------------------------------------------------------------------------
# proxy
# --------------------------------------------------------------------------------------------------


def test_proxies_to_web_and_appends_the_real_client_ip(image, net, tls_dir, tmp_path):
    """Kontrak yang dipakai apps/web/src/lib/auth/client-ip.ts (TRUSTED_PROXY_HOPS=1): nginx
    MENAMBAH IP klien di ujung KANAN X-Forwarded-For dan menimpa header identitas lain dari
    klien."""
    start_upstream(image, net, tmp_path, "A")
    edge = start_edge(image, net, tls_dir)

    r = https(
        edge,
        "/some/path?a=1",
        headers={
            "Host": "cti.test:8443",
            "X-Forwarded-For": "6.6.6.6",  # klien memalsukan
            "X-Real-IP": "9.9.9.9",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": "evil.example",
        },
    )

    f = r.fields
    assert r.status == 200 and f["id"] == "A" and f["uri"] == "/some/path?a=1"
    chain = [p.strip() for p in f["xff"].split(",")]
    assert len(chain) == 2 and chain[0] == "6.6.6.6"  # yang dipalsukan tetap di KIRI...
    assert (
        re.fullmatch(r"\d+\.\d+\.\d+\.\d+", chain[1]) and chain[1] != "6.6.6.6"
    )  # ...IP nyata di KANAN
    assert f["real_ip"] == chain[1]  # X-Real-IP klien ditimpa
    assert f["proto"] == "https"
    # Host membawa port apa adanya (bukan $host): Origin/redirect web di port non-standar cocok
    assert f["host"] == "cti.test:8443" and f["xfhost"] == "cti.test:8443"


def test_health_endpoint_is_answered_by_nginx_itself(image, net, tls_dir, tmp_path):
    start_upstream(image, net, tmp_path, "A")
    edge = start_edge(image, net, tls_dir)

    r = https(edge, "/nginx-health")

    assert r.status == 200 and r.body == "ok\n"  # bukan halaman web
    assert r.headers["server"] == "nginx"  # tanpa nomor versi (server_tokens off)


def healthcheck_command(image: str) -> str:
    raw = docker("inspect", "--format", "{{json .Config.Healthcheck.Test}}", image).stdout
    test = json.loads(raw)
    assert test[0] == "CMD-SHELL"
    return test[1]


def test_image_healthcheck_command_passes(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir)

    res = docker("exec", edge.name, "sh", "-c", healthcheck_command(image), check=False)

    assert res.returncode == 0, res.stderr


def test_healthcheck_leaves_the_nginx_log_quiet(image, net, tls_dir):
    """Healthcheck lewat https (wget busybox -> proses anak `ssl_client` yatim) membuat nginx
    (PID 1) menulis 'SIGCHLD received' + 'unknown process exited' tiap 15 dtk (~11.500/hari)."""
    edge = start_edge(image, net, tls_dir)
    before = docker_logs(edge.name)

    for _ in range(5):
        res = docker("exec", edge.name, "sh", "-c", healthcheck_command(image), check=False)
        assert res.returncode == 0
    time.sleep(1)

    new_lines = docker_logs(edge.name)[len(before) :]
    assert new_lines.strip() == "", new_lines  # tidak ada notice proses yatim, tidak ada access log


def test_internal_health_listener_is_not_reachable_from_the_network(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir)

    def probe(url: str) -> int:
        res = docker(
            "run", "--rm", "--network", net, "--entrypoint", "wget", image,
            "-q", "-T", "3", "--no-check-certificate", "-O", "/dev/null", url,
            check=False,
        )  # fmt: skip
        return res.returncode

    assert (
        probe(f"https://{edge.name}/nginx-health") == 0
    )  # prasyarat: jaringan memang bisa menjangkau edge
    assert (
        probe(f"http://{edge.name}:8081/nginx-health") != 0
    )  # listener healthcheck hanya loopback


def served_certificate(edge: Edge) -> tuple[str, str]:
    """(fingerprint SHA-256, versi TLS) dari sertifikat yang DISAJIKAN nginx."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with (
        socket.create_connection(("127.0.0.1", edge.https_port), timeout=10) as raw,
        ctx.wrap_socket(raw, server_hostname="cti.test") as tls,
    ):
        der = tls.getpeercert(binary_form=True)
        version = tls.version() or ""
    return hashlib.sha256(der or b"").hexdigest().upper(), version


def test_serves_the_generated_certificate_over_modern_tls(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir)

    served, version = served_certificate(edge)

    on_disk = fingerprint(image, tls_dir).split("=", 1)[1].replace(":", "")
    assert served == on_disk
    assert version in ("TLSv1.2", "TLSv1.3")


def docker_logs(name: str) -> str:
    proc = docker("logs", name, check=False)
    return proc.stdout + proc.stderr


def test_renewal_loop_swaps_in_a_fresh_certificate_without_restarting_the_container(
    image, net, tls_dir
):
    """Tanpa loop ini nginx yang berjalan > 1 tahun tanpa restart kedaluwarsa diam-diam.
    Sertifikat 10 hari (< ambang 30 hari) diganti loop dan nginx di-reload -- TANPA restart."""
    edge = start_edge(
        image, net, tls_dir, {"NGINX_TLS_DAYS": "10", "NGINX_TLS_RENEW_CHECK_SECONDS": "2"}
    )
    first, _ = served_certificate(edge)

    current = first
    deadline = time.time() + 30
    while current == first and time.time() < deadline:
        time.sleep(1)
        current, _ = served_certificate(edge)

    assert current != first, "sertifikat yang disajikan tidak pernah berganti"
    assert "nginx -s reload" in docker_logs(edge.name)
    assert docker("inspect", "--format", "{{.RestartCount}}", edge.name).stdout.strip() == "0"


def test_renewal_loop_leaves_an_operator_certificate_alone_and_never_reloads(image, net, tls_dir):
    made = sh(
        image,
        tls_dir,
        "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=corp.internal "
        f"-keyout {KEY} -out {CRT} >/dev/null 2>&1",
    )
    assert made.returncode == 0
    before = digests(image, tls_dir)
    edge = start_edge(image, net, tls_dir, {"NGINX_TLS_RENEW_CHECK_SECONDS": "2"})
    first, _ = served_certificate(edge)

    time.sleep(7)  # >= 3 putaran loop

    logs = docker_logs(edge.name)
    assert (
        logs.count("tidak diubah") >= 3
    )  # sekali saat start + putaran loop (loop BENAR-BENAR jalan)
    assert "nginx -s reload" not in logs
    assert served_certificate(edge)[0] == first
    assert digests(image, tls_dir) == before


@pytest.mark.parametrize("value", ["0", "05", "abc", "-5", "1.5"])
def test_renewal_loop_rejects_a_bad_interval(image, value):
    res = docker(
        "run", "--rm", "-e", f"NGINX_TLS_RENEW_CHECK_SECONDS={value}",
        "--entrypoint", "/docker-entrypoint.d/06-cert-renew-loop.sh", image,
        check=False,
    )  # fmt: skip

    assert res.returncode != 0
    assert "NGINX_TLS_RENEW_CHECK_SECONDS" in res.stderr


def test_http_redirects_to_the_public_https_port(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir, {"NGINX_PUBLIC_HTTPS_PORT": "8443"})

    r = plain(edge, "/a/b?x=1&y=2", {"Host": "cti.test:8080"})

    assert r.status == 301
    assert r.headers["location"] == "https://cti.test:8443/a/b?x=1&y=2"


def test_http_redirect_defaults_to_443(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir)

    r = plain(edge, "/login", {"Host": "cti.test"})

    assert r.status == 301 and r.headers["location"] == "https://cti.test:443/login"


def test_http_redirects_whatever_the_host_header_says(image, net, tls_dir):
    """`default.conf` bawaan image nginx melayani Host `localhost` dengan halaman "Welcome to
    nginx"; harus sudah dibuang supaya SEMUA host kena redirect."""
    edge = start_edge(image, net, tls_dir)

    for host in ("localhost", "172.25.1.77", "apa-saja.example"):
        r = plain(edge, "/x", {"Host": host})
        assert r.status == 301, (host, r.status)
        assert r.headers["location"] == f"https://{host}:443/x"


def test_effective_config_restricts_tls_and_hides_version(image, net, tls_dir):
    edge = start_edge(image, net, tls_dir)

    conf = docker("exec", edge.name, "nginx", "-T", check=False).stdout

    assert "ssl_protocols       TLSv1.2 TLSv1.3;" in conf  # tanpa TLS 1.0/1.1
    assert "ssl_session_tickets off;" in conf
    assert "server_tokens off;" in conf
    assert "Welcome to nginx" not in conf  # default.conf bawaan tidak ikut termuat


def test_reresolves_upstream_when_web_is_replaced(image, net, tls_dir, tmp_path):
    """Regresi paling mahal: nginx yang menyimpan IP `web` saat start memberi 502 SELAMANYA
    setelah `web` di-recreate (deploy, rollback.py). Di sini `web` lama dimatikan dan diganti
    container lain."""
    a = start_upstream(image, net, tmp_path, "A")
    edge = start_edge(image, net, tls_dir)
    assert https(edge, "/").fields["id"] == "A"

    start_upstream(image, net, tmp_path, "B")  # sebentar dua-duanya beralias `web`
    docker("rm", "-f", a)

    seen: list[str | int] = []
    deadline = time.time() + 40
    while time.time() < deadline:
        r = https(edge, "/")
        seen.append(r.fields.get("id", "?") if r.status == 200 else r.status)
        if seen[-3:] == ["B", "B", "B"]:
            break
        time.sleep(1)
    assert seen[-3:] == ["B", "B", "B"], (
        f"nginx tidak menemukan web baru; respons berturut-turut: {seen}"
    )


def test_starts_and_answers_502_when_web_does_not_exist_yet(image, net, tls_dir):
    """nginx tidak boleh gagal start hanya karena `web` belum ada ("host not found in upstream")."""
    edge = start_edge(image, net, tls_dir)

    assert https(edge, "/nginx-health").status == 200
    assert https(edge, "/").status == 502


def test_upload_limit_is_20m(image, net, tls_dir, tmp_path):
    start_upstream(image, net, tmp_path, "A")
    edge = start_edge(image, net, tls_dir)

    small = https(edge, "/upload", method="POST", body=b"x" * (5 * 1024 * 1024))
    assert small.status == 200

    # Content-Length > batas dijawab 413 begitu header diterima -- tanpa mengirim 21 MB
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection("127.0.0.1", edge.https_port, context=ctx, timeout=15)
    conn.putrequest("POST", "/upload")
    conn.putheader("Content-Length", str(21 * 1024 * 1024))
    conn.endheaders()
    assert conn.getresponse().status == 413
    conn.close()


# --------------------------------------------------------------------------------------------------
# kabel compose
# --------------------------------------------------------------------------------------------------

COMPOSE_CANARY = "SECRET_CANARY"


def compose_config(
    tmp_path: pathlib.Path, env: dict[str, str] | None = None, profile: bool = True
) -> dict:
    env_file = tmp_path / "app.env"
    env_file.write_text(f"{COMPOSE_CANARY}=1\n")
    run_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", ""),
        "CTI_ENV_FILE": str(env_file),
        **(env or {}),
    }
    cmd = ["docker", "compose", "-f", str(REPO / "docker-compose.yml")]
    if profile:
        cmd += ["--profile", "app"]
    proc = subprocess.run(
        [*cmd, "config", "--format", "json"],
        capture_output=True,
        text=True,
        env=run_env,
        cwd=REPO,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    return json.loads(proc.stdout)


def _ports(svc: dict) -> dict[str, dict]:
    return {str(p["target"]): p for p in svc["ports"]}


def test_compose_nginx_is_in_app_profile_only(tmp_path):
    assert "nginx" in compose_config(tmp_path)["services"]
    assert (
        "nginx" not in compose_config(tmp_path, profile=False)["services"]
    )  # kerja harian di laptop


def test_compose_nginx_publishes_80_443_and_ports_are_overridable(tmp_path):
    default = compose_config(tmp_path)["services"]["nginx"]
    ports = _ports(default)
    assert ports["80"]["published"] == "80" and ports["443"]["published"] == "443"
    assert ports["80"]["host_ip"] == "0.0.0.0" and ports["443"]["host_ip"] == "0.0.0.0"
    assert default["environment"]["NGINX_PUBLIC_HTTPS_PORT"] == "443"

    custom = compose_config(
        tmp_path,
        {"NGINX_HTTP_PORT": "18080", "NGINX_HTTPS_PORT": "18443", "NGINX_BIND_ADDR": "127.0.0.1"},
    )["services"]["nginx"]
    ports = _ports(custom)
    assert ports["80"]["published"] == "18080" and ports["443"]["published"] == "18443"
    assert ports["80"]["host_ip"] == "127.0.0.1" and ports["443"]["host_ip"] == "127.0.0.1"
    # redirect http -> https harus mengikuti port HTTPS yang benar-benar dibuka di host
    assert custom["environment"]["NGINX_PUBLIC_HTTPS_PORT"] == "18443"


def test_compose_nginx_passes_certificate_settings_and_mounts_the_tls_dir(tmp_path):
    default = compose_config(tmp_path)["services"]["nginx"]
    assert default["environment"]["NGINX_TLS_HOSTS"] == ""
    assert default["environment"]["NGINX_TLS_DAYS"] == "365"
    (mount,) = default["volumes"]
    assert mount["target"] == "/etc/nginx/tls"
    assert pathlib.Path(mount["source"]) == REPO / "docker/nginx/tls"

    custom = compose_config(
        tmp_path,
        {
            "NGINX_TLS_HOSTS": "cti.example.internal,10.0.0.5",
            "NGINX_TLS_DAYS": "90",
            "NGINX_TLS_DIR": "/srv/certs",
        },
    )["services"]["nginx"]
    assert custom["environment"]["NGINX_TLS_HOSTS"] == "cti.example.internal,10.0.0.5"
    assert custom["environment"]["NGINX_TLS_DAYS"] == "90"
    assert custom["volumes"][0]["source"] == "/srv/certs"


def test_compose_nginx_image_does_not_follow_cti_tag(tmp_path):
    """rollback.py mengganti CTI_TAG; edge tidak boleh ikut berubah (dan tidak butuh image lama)."""
    v1 = compose_config(tmp_path, {"CTI_TAG": "v1"})["services"]
    v2 = compose_config(tmp_path, {"CTI_TAG": "v2"})["services"]
    assert v1["api"]["image"] != v2["api"]["image"]  # prasyarat: CTI_TAG memang berpengaruh
    assert v1["nginx"]["image"] == v2["nginx"]["image"]


def test_compose_nginx_gets_no_app_secrets(tmp_path):
    services = compose_config(tmp_path)["services"]
    assert COMPOSE_CANARY in services["api"].get(
        "environment", {}
    )  # prasyarat: env aplikasi memang mengalir
    nginx = services["nginx"]
    assert COMPOSE_CANARY not in nginx.get("environment", {})
    assert "env_file" not in nginx


def test_compose_nginx_waits_for_healthy_web(tmp_path):
    nginx = compose_config(tmp_path)["services"]["nginx"]
    assert nginx["depends_on"]["web"]["condition"] == "service_healthy"


def test_private_key_directory_is_kept_out_of_git_and_images():
    assert "docker/nginx/tls/*" in (REPO / ".gitignore").read_text()
    assert "docker/nginx/tls/" in (REPO / ".dockerignore").read_text()
