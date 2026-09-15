<#
.SYNOPSIS
    Stops whatever is listening on the app's ports.

.DESCRIPTION
    Matches processes BY PORT rather than by image name, so an unrelated
    python.exe or node.exe on the machine is never touched.
#>
param(
    [int[]] $Ports = @(8000, 5173)
)

# Pick up a non-default backend PORT from .env so this still finds it.
$envFile = Join-Path $PSScriptRoot "..\backend\.env"
if (Test-Path $envFile) {
    $portLine = Get-Content $envFile | Where-Object { $_ -match '^\s*PORT\s*=\s*(\d+)\s*$' } | Select-Object -Last 1
    if ($portLine -and $portLine -match '^\s*PORT\s*=\s*(\d+)\s*$') {
        $configuredPort = [int]$Matches[1]
        if ($configuredPort -ne 8000) { $Ports += $configuredPort }
    }
}

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "  nothing listening on $port"
        continue
    }

    # $procId, not $pid - $pid is a read-only automatic variable and assigning
    # to it is a hard error.
    foreach ($procId in ($connections.OwningProcess | Sort-Object -Unique)) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  stopped $($proc.ProcessName) (pid $procId) on port $port" -ForegroundColor Green
    }
}
