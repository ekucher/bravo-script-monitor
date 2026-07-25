#requires -Version 7.4

[CmdletBinding()]
param(
    [Parameter()]
    [string]$ConfigPath = "$PSScriptRoot\agent.json",

    [Parameter()]
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-AgentLog {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('INFO', 'ERROR', 'DEBUG')]
        [string]$Level,

        [Parameter(Mandatory)]
        [string]$Message
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] [$Level] $Message"
}

function Get-AgentConfig {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Configuration file not found: $Path"
    }

    $config = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($property in 'ApiUrl', 'AgentId', 'Token') {
        if ([string]::IsNullOrWhiteSpace([string]$config.$property)) {
            throw "Configuration property '$property' is required"
        }
    }
    return $config
}

function Invoke-AgentApi {
    param(
        [Parameter(Mandatory)][pscustomobject]$Config,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST', 'PUT')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [Parameter()][object]$Body
    )

    $headers = @{
        Authorization = "Bearer $($Config.Token)"
        'X-Agent-ID' = [string]$Config.AgentId
    }
    $parameters = @{
        Uri = "$($Config.ApiUrl.TrimEnd('/'))/api/v1/agents/self$Path"
        Method = $Method
        Headers = $headers
        TimeoutSec = 60
        ContentType = 'application/json; charset=utf-8'
    }
    if ($null -ne $Body) {
        $parameters.Body = $Body | ConvertTo-Json -Depth 20 -Compress
    }
    Invoke-RestMethod @parameters
}

function Send-Heartbeat {
    param([Parameter(Mandatory)][pscustomobject]$Config)

    $body = @{
        version = $Config.Version
        capabilities = @{
            powershell = $PSVersionTable.PSVersion.ToString()
            platform = $PSVersionTable.Platform
        }
    }
    $null = Invoke-AgentApi -Config $Config -Method POST -Path '/heartbeat' -Body $body
}

function Invoke-AgentJob {
    param(
        [Parameter(Mandatory)][pscustomobject]$Config,
        [Parameter(Mandatory)][pscustomobject]$Job
    )

    $startedAt = (Get-Date).ToUniversalTime().ToString('o')
    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) "bsm-$($Job.id).ps1"
    $stdoutFile = "$tempFile.stdout"
    $stderrFile = "$tempFile.stderr"

    try {
        $actualHash = [Convert]::ToHexString(
            [System.Security.Cryptography.SHA256]::HashData(
                [System.Text.Encoding]::UTF8.GetBytes([string]$Job.script)
            )
        ).ToLowerInvariant()
        if ($actualHash -ne [string]$Job.script_sha256) {
            throw 'Script SHA-256 verification failed'
        }

        Set-Content -LiteralPath $tempFile -Value ([string]$Job.script) -Encoding UTF8NoBOM
        $arguments = @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $tempFile)
        $process = Start-Process -FilePath (Get-Command pwsh).Source -ArgumentList $arguments `
            -Wait -PassThru -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile

        $result = @{
            status = $(if ($process.ExitCode -eq 0) { 'succeeded' } else { 'failed' })
            exit_code = $process.ExitCode
            stdout = $(if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw -Encoding UTF8 } else { '' })
            stderr = $(if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw -Encoding UTF8 } else { '' })
            started_at = $startedAt
            finished_at = (Get-Date).ToUniversalTime().ToString('o')
        }
    }
    catch {
        $result = @{
            status = 'failed'
            exit_code = -1
            stdout = ''
            stderr = $_.Exception.Message
            started_at = $startedAt
            finished_at = (Get-Date).ToUniversalTime().ToString('o')
        }
    }
    finally {
        Remove-Item -LiteralPath $tempFile, $stdoutFile, $stderrFile -Force -ErrorAction SilentlyContinue
    }

    $null = Invoke-AgentApi -Config $Config -Method POST -Path "/jobs/$($Job.id)/result" -Body $result
}

$config = Get-AgentConfig -Path $ConfigPath
$pollInterval = [Math]::Max(5, [int]$config.PollIntervalSeconds)

Write-AgentLog -Level INFO -Message "BRAVO Script Monitor Agent started; agent_id=$($config.AgentId)"
do {
    try {
        Send-Heartbeat -Config $config
        $job = Invoke-AgentApi -Config $config -Method POST -Path '/jobs/claim'
        if ($null -ne $job -and $null -ne $job.id) {
            Write-AgentLog -Level INFO -Message "Executing job $($job.id)"
            Invoke-AgentJob -Config $config -Job $job
        }
    }
    catch {
        Write-AgentLog -Level ERROR -Message $_.Exception.Message
    }

    if (-not $Once) {
        Start-Sleep -Seconds $pollInterval
    }
} while (-not $Once)
