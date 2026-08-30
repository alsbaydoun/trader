$ErrorActionPreference = "Stop"

function Stop-PortOwner {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "Nothing is listening on port $Port."
        return
    }

    $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            Write-Host "Stopping process $_ on port $Port."
            Stop-Process -Id $_ -Force
        }
}

Stop-PortOwner -Port 5173
Stop-PortOwner -Port 8000
Write-Host "Trader local services stopped."
