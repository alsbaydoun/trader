$ErrorActionPreference = "SilentlyContinue"

function Get-PortStatus {
    param(
        [string]$Name,
        [int]$Port,
        [string]$Url
    )

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen
    $httpStatus = "not reachable"
    try {
        $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
        $httpStatus = "HTTP $($response.StatusCode)"
    }
    catch {
        $httpStatus = "not reachable"
    }

    [pscustomobject]@{
        Service = $Name
        Url = $Url
        Listening = $null -ne $connection
        ProcessId = if ($connection) { ($connection | Select-Object -First 1).OwningProcess } else { $null }
        Status = $httpStatus
    }
}

Get-PortStatus -Name "API" -Port 8000 -Url "http://127.0.0.1:8000/health"
Get-PortStatus -Name "Web" -Port 5173 -Url "http://127.0.0.1:5173/"
