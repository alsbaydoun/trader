param(
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ApiDir = Join-Path $RepoRoot "services\api"
$WebDir = Join-Path $RepoRoot "apps\web"
$DataDir = Join-Path $RepoRoot "data"
$RuntimeDir = Join-Path $DataDir "runtime"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Test-PortListening {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Ensure-ApiEnvironment {
    $venvPython = Join-Path $ApiDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        $python = Get-Command py -ErrorAction SilentlyContinue
        if ($python) {
            & py -3 -m venv (Join-Path $ApiDir ".venv")
        }
        else {
            & python -m venv (Join-Path $ApiDir ".venv")
        }
    }

    if (-not (Test-Path $venvPython)) {
        throw "Could not create the API Python environment."
    }

    & $venvPython -m pip install -r (Join-Path $ApiDir "requirements.txt") | Out-Null
    return $venvPython
}

function Ensure-WebEnvironment {
    $nodeModules = Join-Path $WebDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        & npm.cmd install --prefix $WebDir
    }
}

function Start-Api {
    param([string]$PythonPath)

    if (Test-PortListening 8000) {
        Write-Host "API already running on http://127.0.0.1:8000"
        return
    }

    $outLog = Join-Path $RuntimeDir "api.out.log"
    $errLog = Join-Path $RuntimeDir "api.err.log"
    Start-Process `
        -FilePath $PythonPath `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $ApiDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog | Out-Null
}

function Start-Web {
    if (Test-PortListening 5173) {
        Write-Host "Web already running on http://127.0.0.1:5173"
        return
    }

    $outLog = Join-Path $RuntimeDir "web.out.log"
    $errLog = Join-Path $RuntimeDir "web.err.log"
    $env:VITE_API_URL = "http://127.0.0.1:8000"
    Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory $WebDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog | Out-Null
}

$pythonPath = Ensure-ApiEnvironment
Ensure-WebEnvironment
Start-Api -PythonPath $pythonPath
Start-Web

$apiReady = Wait-ForHttp -Url "http://127.0.0.1:8000/health" -TimeoutSeconds 45
$webReady = Wait-ForHttp -Url "http://127.0.0.1:5173/" -TimeoutSeconds 45

if (-not $apiReady -or -not $webReady) {
    Write-Warning "Trader started, but one service did not become ready yet. Check logs in $RuntimeDir."
    exit 1
}

Write-Host "Trader is running."
Write-Host "Web: http://127.0.0.1:5173/"
Write-Host "API: http://127.0.0.1:8000/health"
Write-Host "Logs: $RuntimeDir"

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:5173/"
}
