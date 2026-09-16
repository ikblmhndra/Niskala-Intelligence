# Sourced by the salvage scripts. Not executable on its own.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }

need_env() {
  for v in "$@"; do
    [ -n "${!v:-}" ] || die "\$$v belum di-set. Lihat docs/phases/PHASE_0_SALVAGE.md"
  done
}

need_cmd() {
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "butuh '$c' tapi gak ketemu di PATH"
  done
}
