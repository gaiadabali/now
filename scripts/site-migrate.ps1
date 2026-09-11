#!/usr/bin/env pwsh
# site:migrate — apply the now-db migration set to one or every registered
# city DB. Idempotent: a second run applies nothing new.
#
# Usage:
#   scripts/site-migrate.ps1 --all
#   scripts/site-migrate.ps1 --url <dsn-or-db-name>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

if (-not $Args -or $Args.Count -eq 0) {
    Write-Error "usage: site-migrate.ps1 --all | --url <dsn-or-db-name>"
    exit 2
}

python -m now_db.cli migrate @Args
exit $LASTEXITCODE
