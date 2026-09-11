<#
.SYNOPSIS
Pull a fresh dump of a live NOW! WordPress site into this repo.

.DESCRIPTION
Windows counterpart to wp-dump.sh. Read-only on the remote: mysqldump and tar
are piped through gzip into an SSH stream, so nothing is written to the
production filesystem.

Binary output is copied from the process's raw stdout stream rather than
through a PowerShell pipeline — a pipeline would decode the gzip bytes as text
and corrupt every dump.

Config is read from the repo's gitignored .env (see .env.example):
  WP_SSH_HOST, WP_SSH_PORT, WP_SSH_USER, WP_SSH_KEY
  WP_DB_JAKARTA, WP_DB_BALI, WP_DOMAIN_JAKARTA, WP_DOMAIN_BALI, WP_REMOTE_ROOT

Password auth is not supported here — use a key (see .env.example).

.EXAMPLE
scripts\wp-dump.ps1
.EXAMPLE
scripts\wp-dump.ps1 -Site bali -Uploads
#>
[CmdletBinding()]
param(
    [string[]]$Site = @('jakarta', 'bali'),
    [switch]$Uploads,
    [switch]$UploadsOnly,
    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# ── config ───────────────────────────────────────────────────────────────
$cfg = @{}
$envFile = Join-Path $repoRoot '.env'
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $cfg[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
        }
    }
}
function Get-Cfg($name, $fallback = $null) {
    # The environment wins over .env, matching the shell script.
    $fromEnv = [Environment]::GetEnvironmentVariable($name)
    if ($fromEnv) { return $fromEnv }
    if ($cfg.ContainsKey($name) -and $cfg[$name]) { return $cfg[$name] }
    return $fallback
}

$sshHost = Get-Cfg 'WP_SSH_HOST'
$sshUser = Get-Cfg 'WP_SSH_USER'
$sshPort = Get-Cfg 'WP_SSH_PORT' '65002'
$sshKey  = Get-Cfg 'WP_SSH_KEY'
$remoteRoot = Get-Cfg 'WP_REMOTE_ROOT' "/home/$sshUser/domains"

if (-not $sshHost) { throw 'Set WP_SSH_HOST in .env — see .env.example' }
if (-not $sshUser) { throw 'Set WP_SSH_USER in .env — see .env.example' }
if (-not $sshKey) {
    throw 'Set WP_SSH_KEY in .env. wp-dump.ps1 requires key auth; see .env.example.'
}
if (-not (Test-Path $sshKey)) { throw "WP_SSH_KEY does not exist: $sshKey" }

$sshArgs = @(
    '-p', $sshPort, '-i', $sshKey,
    '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20',
    '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=6',
    "$sshUser@$sshHost"
)

# Stream a remote command's stdout straight into a file, bytes untouched.
function Invoke-RemoteToFile($remoteCommand, $destination) {
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = 'ssh'
    foreach ($a in $sshArgs) { $psi.ArgumentList.Add($a) }
    $psi.ArgumentList.Add($remoteCommand)
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false

    $proc = [System.Diagnostics.Process]::Start($psi)
    $out = [System.IO.File]::Create($destination)
    try {
        $proc.StandardOutput.BaseStream.CopyTo($out)
    } finally {
        $out.Dispose()
    }
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) {
        throw "ssh exited $($proc.ExitCode): $stderr"
    }
}

function Invoke-RemoteText($remoteCommand) {
    & ssh @sshArgs $remoteCommand 2>&1
    if ($LASTEXITCODE -ne 0) { throw "ssh exited $LASTEXITCODE" }
}

function Format-Bytes([long]$b) {
    foreach ($u in 'B', 'KB', 'MB', 'GB', 'TB') {
        if ($b -lt 1024 -or $u -eq 'TB') { return ('{0:N1} {1}' -f $b, $u) }
        $b = $b / 1024
    }
}

Write-Step "connecting to ${sshUser}@${sshHost}:${sshPort}"
Invoke-RemoteText 'true' | Out-Null

$wantDb = -not $UploadsOnly
$wantUploads = $Uploads -or $UploadsOnly
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

foreach ($slug in $Site) {
    $db = Get-Cfg "WP_DB_$($slug.ToUpper())"
    if (-not $db) { throw "No database configured for '$slug' (set WP_DB_$($slug.ToUpper()))" }

    $dest = if ($OutDir) { $OutDir } else { Join-Path $repoRoot "$slug\db\dumps" }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    if ($wantDb) {
        $sql = Join-Path $dest "$slug-$stamp.sql.gz"
        Write-Step "$slug`: dumping $db"
        $cmd = "mysqldump --single-transaction --quick --skip-lock-tables " +
               "--default-character-set=utf8mb4 --routines --events " +
               "--no-tablespaces '$db' | gzip -6"
        Invoke-RemoteToFile $cmd $sql

        $bytes = (Get-Item $sql).Length
        if ($bytes -lt 1MB) {
            throw "$slug`: dump is only $bytes bytes — almost certainly an error message, not a database. Inspect: $sql"
        }
        Write-Step "$slug`: $(Format-Bytes $bytes) gzipped -> $sql"
    }

    if ($wantUploads) {
        $domain = Get-Cfg "WP_DOMAIN_$($slug.ToUpper())"
        if (-not $domain) { throw "No domain configured for '$slug' (set WP_DOMAIN_$($slug.ToUpper()))" }
        $web = "$remoteRoot/$domain/public_html"
        $tar = Join-Path $dest "$slug-uploads-$stamp.tar.gz"

        # TWO directories. wp-content/uploads is the media library;
        # public_html/uploads is Jakarta's pre-WordPress CKEditor store, which
        # holds inline images for 47.7% of its articles and appears in neither
        # the media library nor the database (F34).
        Write-Step "$slug`: archiving wp-content/uploads + legacy uploads/ (large)"
        $cmd = "cd '$web' && tar czf - " +
               "`$( [ -d wp-content/uploads ] && echo wp-content/uploads ) " +
               "`$( [ -d uploads ] && echo uploads ) 2>/dev/null"
        Invoke-RemoteToFile $cmd $tar
        Write-Step "$slug`: $(Format-Bytes (Get-Item $tar).Length) of media -> $tar"
    }
}

Write-Step 'done — dumps are under <site>\db\dumps\ and are gitignored'
