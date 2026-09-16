#!/usr/bin/env bash
# Fase 0.2 — Rekam crontab + systemd timer dari prod.
#
# Jadwal 206 scraper CUMA hidup di crontab host produksi. Gak ada di repo,
# dan gak bisa direkonstruksi dari source. Ini juga satu-satunya cara tahu
# scraper mana yang sebenernya aktif.
source "$(dirname "$0")/_common.sh"
need_cmd ssh
need_env CTI_PROD_HOST

OUT="$REPO_ROOT/docs/legacy/crontab.txt"
mkdir -p "$(dirname "$OUT")"

info "ngumpulin jadwal dari $CTI_PROD_HOST"
{
  echo "# Direkam: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Host: $CTI_PROD_HOST"
  echo
  ssh "$CTI_PROD_HOST" '
    echo "### crontab user saat ini"; crontab -l 2>/dev/null || echo "(kosong)"
    echo; echo "### crontab per user"
    for u in $(cut -d: -f1 /etc/passwd); do
      c=$(sudo crontab -l -u "$u" 2>/dev/null) || continue
      [ -n "$c" ] && { echo "## user: $u"; echo "$c"; }
    done
    echo; echo "### /etc/crontab"; cat /etc/crontab 2>/dev/null
    echo; echo "### /etc/cron.d"
    for f in /etc/cron.d/*; do [ -f "$f" ] && { echo "## $f"; cat "$f"; }; done
    echo; echo "### systemd timer"; systemctl list-timers --all --no-pager 2>/dev/null
    echo; echo "### systemd unit terkait cti"
    # Pola sengaja spesifik: 'cti' polos cocok sama kata "active" dan
    # nge-dump tiap unit device di host.
    systemctl list-units --all --type=service --no-pager 2>/dev/null \
      | grep -iE "scraper|nlp[_-]?worker|ioc[_-]?sync|cti[-_.]" || echo "(tidak ada)"
    echo; echo "### definisi unit"
    for u in cti-web nlp_worker iocSyncer scraper-news; do
      systemctl cat "$u.service" 2>/dev/null && echo
    done

    echo; echo "### identitas host -- apakah ini HOST SCRAPER?"
    echo "hostname: $(hostname)"
    echo "isi /opt:"; ls -1 /opt 2>/dev/null | sed "s/^/  /"
    echo "proses python yang jalan:"
    ps aux 2>/dev/null | grep -E "[p]ython.*(Threat|nlp_worker|iocSyncer|run\.py)" \
      | awk "{print \"  \" \$11, \$12, \$13}" | head -20 || echo "  (tidak ada)"
  '
} > "$OUT"

ENTRIES=$(grep -cE '^\s*[0-9*]' "$OUT" || true)
SCRIPTS=$(grep -oE '[A-Za-z0-9_]+\.py' "$OUT" | sort -u | wc -l | tr -d " ")
ok "ketulis ke docs/legacy/crontab.txt ($ENTRIES baris jadwal)"

info "script yang kesebut:"
grep -oE '[A-Za-z0-9_]+\.py' "$OUT" | sort -u | head -20
echo "  ... total unik: $(grep -oE '[A-Za-z0-9_]+\.py' "$OUT" | sort -u | wc -l | tr -d ' ')"

if [ "$SCRIPTS" -lt 50 ]; then
  warn "cuma $SCRIPTS script .py kesebut — diharapkan ~200. Kemungkinan:"
  warn "  1. HOST SALAH. Cek bagian \"identitas host\": /opt harusnya ada"
  warn "     ScraperNewsRevamp/ScraperNewsWeb, dan ada proses python jalan."
  warn "  2. sudo crontab -l gagal diam-diam (butuh password). Coba manual:"
  warn "     ssh '$CTI_PROD_HOST' \"sudo crontab -l -u <user-scraper>\""
  warn "  3. Dijadwalin pakai cara lain (supervisor, systemd timer, loop)."
  warn ""
  warn "JANGAN tandai Fase 0.2 selesai sampai file ini berisi jadwal beneran."
fi

echo
echo "Commit file ini: git add docs/legacy/crontab.txt"
