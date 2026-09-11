#!/usr/bin/env pwsh
# site:create <slug> — provision a city DB, migrate it, seed it, register it
# in the platform `sites` roster, and scaffold <slug>/{site,cms,content}/.
#
# Thin wrapper: all real logic lives in now_db.provisioning (Python) — see
# engine/packages/db/README.md for setup and connection env vars.
#
# Usage:
#   scripts/site-create.ps1 jakarta --hostname nowjakarta.co.id --name "NOW! Jakarta"
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

if (-not $Args -or $Args.Count -eq 0) {
    Write-Error "usage: site-create.ps1 <slug> --hostname <host> --name <name> [--locale en] [--timezone Asia/Jakarta] [--currency IDR] [--module <name> ...]"
    exit 2
}

python -m now_db.cli create @Args
exit $LASTEXITCODE
