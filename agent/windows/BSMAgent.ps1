#requires -Version 7.4

[CmdletBinding()]
param(
    [string]$ConfigPath = "$PSScriptRoot\config.json",
    [switch]$Once,
    [switch]$DebugMode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-BsmLog {
    param(
        [ValidateSet('INFO', 'ERROR', 'DEBUG')]
        [string]$Level,
        [string]$Message
    )

    if ($Level -eq 'DEBUG' -and -not $DebugMode) {
        return
    }

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] [$Level] $Message"
}

function Get-BsmConfig {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Configuration file not found: $ConfigPath"
    }

    return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Send-BsmHeartbeat {
    param([pscustomobject]$Config)

    $uri = '{0}/api/v1/agents/{1}/heartbeat' -f $Config.serverUrl.TrimEnd('/'), $Config.agentId
    $headers = @{ Authorization = "Bearer $($Config.token)" }
    $body = @{
        hostname = [Environment]::MachineName
        agentVersion = '0.1.0-alpha'
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json

    Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body -ContentType 'application/json'
}

try {
    $config = Get-BsmConfig
    Write-BsmLog INFO "BSM Agent started for $([Environment]::MachineName)"

    do {
        try {
            Send-BsmHeartbeat -Config $config | Out-Null
            Write-BsmLog INFO 'Heartbeat sent successfully'
        }
        catch {
            Write-BsmLog ERROR "Heartbeat failed: $($_.Exception.Message)"
        }

        if (-not $Once) {
            Start-Sleep -Seconds ([int]$config.heartbeatIntervalSeconds)
        }
    } while (-not $Once)
}
catch {
    Write-BsmLog ERROR $_.Exception.Message
    exit 1
}
