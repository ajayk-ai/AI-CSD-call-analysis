<#
.SYNOPSIS
    Triggers one analysis run against a already-running backend.

.DESCRIPTION
    Same operation as the dashboard's "Run Analysis" button. Called by
    run-analysis.bat; kept as a .ps1 because multi-line PowerShell embedded in
    a .bat via ^ continuation does not survive cmd's parsing.

.PARAMETER Limit
    Recordings to send to Gemini. Omit for the backend's PIPELINE_RUN_LIMIT,
    0 for no cap (processes the entire backlog).
#>
param(
    [int] $Limit = -1,
    [string] $ApiBase = 'http://localhost:8000'
)

$ErrorActionPreference = 'Stop'

try {
    Invoke-RestMethod "$ApiBase/api/health" -TimeoutSec 5 | Out-Null
} catch {
    Write-Host '[X] Backend is not running. Start it with start-backend.bat first.' -ForegroundColor Red
    exit 1
}

$url = "$ApiBase/api/pipeline/run"
if ($Limit -ge 0) { $url += "?limit=$Limit" }
if ($Limit -eq 0) {
    Write-Host '[!] No limit set - this will process every remaining recording.' -ForegroundColor Yellow
}

Write-Host 'Running analysis (a few seconds per recording)...'

try {
    # No timeout: a large batch legitimately runs for minutes, and the run is
    # resumable anyway - anything that fails is retried on the next click.
    $result = Invoke-RestMethod $url -Method Post -TimeoutSec 0
} catch {
    Write-Host "[X] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$analyzed = $result.newly_processed - $result.skipped_by_prescreen

Write-Host ''
Write-Host ('  Found in bucket   : {0}' -f $result.found_in_bucket)
Write-Host ('  Sent to Gemini    : {0}' -f $analyzed) -ForegroundColor Green
Write-Host ('  Skipped (free)    : {0}' -f $result.skipped_by_prescreen)
Write-Host ('  Already analyzed  : {0}' -f $result.already_processed)
Write-Host ('  Failed            : {0}' -f $result.failed)
Write-Host ('  Still queued      : {0}' -f $result.remaining_pending)

if ($result.errors.Count -gt 0) {
    Write-Host ''
    Write-Host 'Errors:' -ForegroundColor Red
    foreach ($err in $result.errors) { Write-Host "  - $err" -ForegroundColor Red }
}

Write-Host ''
if ($result.remaining_pending -gt 0) {
    Write-Host ('Run again to process the next {0}.' -f $result.limit_applied)
} else {
    Write-Host 'Nothing left queued.'
}

exit 0
