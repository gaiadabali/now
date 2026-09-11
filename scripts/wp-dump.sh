#!/usr/bin/env bash
# Pull a fresh dump of a live NOW! WordPress site into this repo.
#
# Read-only on the remote. mysqldump and tar are piped through gzip straight
# into an SSH stream, so nothing is ever written to the production
# filesystem — no staging file, no plugin, no backup job, nothing to clean up.
#
#   scripts/wp-dump.sh                    # both databases
#   scripts/wp-dump.sh --site bali        # one site
#   scripts/wp-dump.sh --uploads          # databases + media (large!)
#   scripts/wp-dump.sh --site bali --uploads-only
#
# Config comes from the repo's gitignored .env (or the environment):
#
#   WP_SSH_HOST, WP_SSH_PORT, WP_SSH_USER
#   WP_SSH_KEY            path to a private key   (recommended)
#   WP_SSH_PASSWORD       only used if sshpass is installed
#   WP_DB_JAKARTA, WP_DB_BALI
#   WP_REMOTE_ROOT        e.g. /home/<account>/domains
#   WP_DOMAIN_JAKARTA, WP_DOMAIN_BALI
#
# See .env.example for the block to copy.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITES=()
WANT_DB=1
WANT_UPLOADS=0
OUT_DIR=""

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
log() { printf '\033[36m==>\033[0m %s\n' "$*"; }

usage() {
    sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --site)         SITES+=("$2"); shift 2 ;;
        --uploads)      WANT_UPLOADS=1; shift ;;
        --uploads-only) WANT_UPLOADS=1; WANT_DB=0; shift ;;
        --db-only)      WANT_UPLOADS=0; WANT_DB=1; shift ;;
        --out)          OUT_DIR="$2"; shift 2 ;;
        -h|--help)      usage 0 ;;
        *)              die "unknown argument: $1 (try --help)" ;;
    esac
done

# ── config ───────────────────────────────────────────────────────────────
if [[ -f "$REPO_ROOT/.env" ]]; then
    # shellcheck disable=SC1091
    set -a; source "$REPO_ROOT/.env"; set +a
fi

: "${WP_SSH_HOST:?set WP_SSH_HOST in .env — see .env.example}"
: "${WP_SSH_USER:?set WP_SSH_USER in .env — see .env.example}"
WP_SSH_PORT="${WP_SSH_PORT:-65002}"
WP_REMOTE_ROOT="${WP_REMOTE_ROOT:-/home/$WP_SSH_USER/domains}"

[[ ${#SITES[@]} -eq 0 ]] && SITES=(jakarta bali)

# Per-site settings are read from "${VAR}_${SLUG^^}" — no site literals.
site_db()     { local v="WP_DB_${1^^}";     echo "${!v:-}"; }
site_domain() { local v="WP_DOMAIN_${1^^}"; echo "${!v:-}"; }

# ── ssh transport ────────────────────────────────────────────────────────
SSH_OPTS=(-p "$WP_SSH_PORT"
          -o StrictHostKeyChecking=accept-new
          -o ConnectTimeout=20
          -o ServerAliveInterval=20
          -o ServerAliveCountMax=6)
SSH_PREFIX=()

if [[ -n "${WP_SSH_KEY:-}" ]]; then
    [[ -f "$WP_SSH_KEY" ]] || die "WP_SSH_KEY does not exist: $WP_SSH_KEY"
    SSH_OPTS+=(-i "$WP_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes)
    log "auth: private key $WP_SSH_KEY"
elif [[ -n "${WP_SSH_PASSWORD:-}" ]]; then
    command -v sshpass >/dev/null 2>&1 || die \
        "WP_SSH_PASSWORD is set but sshpass is not installed. Either install
       sshpass, or (better) use key auth — see 'Key setup' in the README
       section of this script's docs."
    SSH_PREFIX=(sshpass -e ssh)
    export SSHPASS="$WP_SSH_PASSWORD"
    log "auth: password via sshpass"
else
    # No credential configured: rely on the agent / default identity and let
    # ssh fail loudly rather than hanging on an interactive prompt.
    SSH_OPTS+=(-o BatchMode=yes)
    log "auth: default identity / ssh-agent"
fi

remote() {
    if [[ ${#SSH_PREFIX[@]} -gt 0 ]]; then
        "${SSH_PREFIX[@]}" "${SSH_OPTS[@]}" "$WP_SSH_USER@$WP_SSH_HOST" "$@"
    else
        ssh "${SSH_OPTS[@]}" "$WP_SSH_USER@$WP_SSH_HOST" "$@"
    fi
}

# ── pre-flight ───────────────────────────────────────────────────────────
# Validate every requested site before opening a connection, so a typo in
# --site fails in a millisecond with a useful message instead of after an
# SSH handshake.
for slug in "${SITES[@]}"; do
    [[ "$slug" =~ ^[a-z][a-z0-9-]*$ ]] \
        || die "invalid site slug: '$slug'"
    [[ -n "$(site_db "$slug")" ]] \
        || die "no database configured for '$slug' — set WP_DB_${slug^^} in .env"
    if [[ $WANT_UPLOADS -eq 1 && -z "$(site_domain "$slug")" ]]; then
        die "no domain configured for '$slug' — set WP_DOMAIN_${slug^^} in .env (needed for --uploads)"
    fi
done

log "connecting to $WP_SSH_USER@$WP_SSH_HOST:$WP_SSH_PORT"
remote "true" || die "SSH failed. Check credentials, and that SSH is enabled
       for this hosting account (hPanel → Advanced → SSH Access)."

command -v gzip >/dev/null 2>&1 || die "gzip is required locally"
remote "command -v mysqldump >/dev/null" \
    || die "mysqldump not found on the remote host"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# ── per site ─────────────────────────────────────────────────────────────
for slug in "${SITES[@]}"; do
    db="$(site_db "$slug")"
    [[ -n "$db" ]] || die "no database configured for '$slug' (set WP_DB_${slug^^})"

    dest="${OUT_DIR:-$REPO_ROOT/$slug/db/dumps}"
    mkdir -p "$dest"

    if [[ $WANT_DB -eq 1 ]]; then
        sql="$dest/${slug}-${STAMP}.sql.gz"
        log "$slug: dumping $db"

        # --single-transaction  consistent snapshot without locking the live site
        # --quick               stream rows instead of buffering the whole table
        # --skip-lock-tables    shared hosting rarely grants LOCK TABLES
        # gzip on the remote    compress before the wire, not after
        remote "mysqldump --single-transaction --quick --skip-lock-tables \
                    --default-character-set=utf8mb4 --routines --events \
                    --no-tablespaces '$db' | gzip -6" > "$sql"

        gzip -t "$sql" 2>/dev/null || die "$slug: dump failed gzip integrity check"

        bytes=$(wc -c < "$sql")
        [[ "$bytes" -gt 1048576 ]] || die \
            "$slug: dump is only $bytes bytes — almost certainly an error
       message, not a database. Inspect: $sql"

        tables=$(gzip -dc "$sql" | grep -c '^CREATE TABLE' || true)
        log "$slug: $(numfmt --to=iec "$bytes" 2>/dev/null || echo "$bytes B") gzipped, $tables tables"
        printf '%s\n' "$sql" >> "$dest/.latest"
        ln -sf "$(basename "$sql")" "$dest/${slug}-latest.sql.gz" 2>/dev/null || true
    fi

    if [[ $WANT_UPLOADS -eq 1 ]]; then
        domain="$(site_domain "$slug")"
        [[ -n "$domain" ]] || die "no domain configured for '$slug' (set WP_DOMAIN_${slug^^})"
        web="$WP_REMOTE_ROOT/$domain/public_html"
        tar_out="$dest/${slug}-uploads-${STAMP}.tar.gz"

        # TWO directories, not one. wp-content/uploads is the media library;
        # public_html/uploads is Jakarta's pre-WordPress CKEditor store, which
        # holds inline images for 47.7% of its articles and is invisible to
        # both the media library and the database (F34).
        log "$slug: archiving wp-content/uploads + legacy uploads/ (large)"
        remote "cd '$web' && tar czf - \
                    \$( [ -d wp-content/uploads ] && echo wp-content/uploads ) \
                    \$( [ -d uploads ] && echo uploads ) 2>/dev/null" > "$tar_out"

        gzip -t "$tar_out" 2>/dev/null || die "$slug: uploads archive failed integrity check"
        bytes=$(wc -c < "$tar_out")
        log "$slug: $(numfmt --to=iec "$bytes" 2>/dev/null || echo "$bytes B") of media"
    fi
done

log "done — dumps are under <site>/db/dumps/ and are gitignored"
