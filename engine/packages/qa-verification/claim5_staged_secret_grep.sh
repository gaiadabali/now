#!/bin/bash
# Re-run F48's credential grep over STAGED BLOB CONTENT (git show ":path"),
# not the working tree -- catches the case where a file was staged clean
# but the working copy was edited afterward (or vice versa).
set -u
cd "$(dirname "$0")/../../.."

PATTERN='(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|password\s*[:=]\s*["'"'"']?[^"'"'"' ]{6,}|POSTGRES_PASSWORD\s*=\s*[^ ]+|PGPASSWORD|secret[_-]?key\s*[:=]|api[_-]?key\s*[:=]\s*["'"'"']?[A-Za-z0-9]{10,}|mongodb(\+srv)?://[^ ]*:[^ ]*@|postgres(ql)?://[^ ]*:[^ ]*@|xox[baprs]-[0-9A-Za-z-]+|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})'

hits=0
total=0
while IFS= read -r f; do
  total=$((total+1))
  blob="$(git show ":$f" 2>/dev/null)"
  if [ -z "$blob" ]; then continue; fi
  match=$(printf '%s\n' "$blob" | grep -nEi "$PATTERN")
  if [ -n "$match" ]; then
    hits=$((hits+1))
    echo "=== $f ==="
    echo "$match"
  fi
done < <(git diff --cached --name-only)

echo ""
echo "Files scanned (staged blobs): $total"
echo "Files with a hit: $hits"
