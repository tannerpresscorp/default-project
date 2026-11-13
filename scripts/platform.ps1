#Requires -Version 5.1
<#
.SYNOPSIS
Build, run and deploy the agent platform from Windows PowerShell.

.DESCRIPTION
Mirrors the platform targets in the root Makefile without requiring make.
Docker Compose v2 is required for the local run commands; Helm is required for
the deployment commands. On Windows Server (where WSL2/Docker Desktop are not
supported) use a Linux VM as the Docker context; the wrapper prints VM-based
URLs automatically.

.PARAMETER Command
build         Build the platform container image.
build-web     Build the React web UI.
run           Start PostgreSQL/Redis, migrate, then run the API container.
run-worker    Start PostgreSQL/Redis, then run the Temporal worker container.
stop          Stop the API and worker containers.
down          Remove the local Compose stack (named volumes are kept).
logs          Follow API and worker logs.
helm-lint     Lint the gated Helm chart.
helm-template Render the chart locally (requires -Values).
deploy        Install or upgrade the chart (requires -Values and a cluster).

.EXAMPLE
.\scripts\platform.ps1 build

.EXAMPLE
.\scripts\platform.ps1 run

.EXAMPLE
.\scripts\platform.ps1 deploy -Values ..\deploy\agent-platform.yaml -KubeContext staging
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet(
        'build', 'build-web', 'run', 'run-worker', 'stop', 'down', 'logs',
        'helm-lint', 'helm-template', 'deploy'
    )]
    [string]$Command,

    [string]$ImageRepository = 'agent-platform',
    [string]$ImageTag = 'local',
    [string]$Release = 'agent-platform',
    [string]$Namespace = 'agent-platform',
    [string]$Values = $env:HELM_VALUES,
    [string]$KubeContext = $env:HELM_CONTEXT,
    [string]$Timeout = '10m'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $root 'infra/local/compose.yaml'
$chart = Join-Path $root 'infra/helm/agent-platform'
$image = "${ImageRepository}:${ImageTag}"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE"
    }
}

function Assert-LinuxContainers {
    $osType = (& docker info --format '{{.OSType}}' 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker is not running or unavailable.'
    }
    if ($osType.Trim() -ne 'linux') {
        throw "Docker is using $($osType.Trim()) containers. Switch to a Linux Docker context (for example a Hyper-V Linux VM); see docs/architecture/development.md."
    }
}

function Get-DockerHostAddress {
    # Returns the host of a remote Docker context (for example an SSH endpoint),
    # or $null when Docker runs on the local machine.
    $endpoint = (& docker context inspect --format '{{.Endpoints.docker.Host}}' 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $endpoint) { return $null }
    if ($endpoint -match '^(?:ssh|tcp)://(?:[^@/]+@)?(?<host>[^:/]+)') {
        return $Matches['host']
    }
    return $null
}

function Invoke-Compose {
    param([string[]]$ArgumentList = @())
    Assert-LinuxContainers
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose v2 is required for this command (docker compose).'
    }
    Invoke-Checked -FilePath 'docker' -ArgumentList (@('compose', '-f', $composeFile) + $ArgumentList)
}

function Invoke-Dependencies {
    Invoke-Compose -ArgumentList @('up', '-d', '--wait', 'postgres', 'redis')
}

function Invoke-MigrateInContainer {
    Invoke-Compose -ArgumentList @(
        '--profile', 'api', 'run', '--rm', '--no-deps', '--build',
        '-e', 'PLATFORM_MIGRATION_DATABASE_URL=postgresql+asyncpg://platform_migrator:local_migrator_only@postgres:5432/platform',
        'api', 'python', '-m', 'alembic', 'upgrade', 'head'
    )
}

function Invoke-Helm {
    param([string[]]$ArgumentList = @())
    Invoke-Checked -FilePath 'helm' -ArgumentList $ArgumentList
}

if ($Command -in @('run', 'run-worker')) {
    $env:PLATFORM_IMAGE = $image
}
if ($Command -eq 'run') {
    # The port is published on the Linux VM, so bind it on all VM interfaces.
    $env:PLATFORM_BIND_ADDRESS = '0.0.0.0'
}

Push-Location $root
try {
    switch ($Command) {
        'build' {
            Assert-LinuxContainers
            Invoke-Checked -FilePath 'docker' -ArgumentList @(
                'build', '-f', 'infra/docker/Dockerfile', '-t', $image, '.'
            )
        }
        'build-web' {
            Invoke-Checked -FilePath 'pnpm' -ArgumentList @('--filter', 'web', 'build')
        }
        'run' {
            Invoke-Dependencies
            Invoke-MigrateInContainer
            Invoke-Compose -ArgumentList @('--profile', 'api', 'up', '-d', '--build', '--wait', 'api')
            $hostAddress = Get-DockerHostAddress
            if (-not $hostAddress) { $hostAddress = '127.0.0.1' }
            Write-Host "API: http://${hostAddress}:8001 (liveness: /health/live)"
        }
        'run-worker' {
            Invoke-Dependencies
            Invoke-MigrateInContainer
            Invoke-Compose -ArgumentList @('--profile', 'worker', 'up', '-d', '--build', 'worker')
            Write-Host 'Worker started; it requires PLATFORM_TEMPORAL_ADDRESS to be reachable.'
        }
        'stop' {
            Invoke-Compose -ArgumentList @('--profile', 'api', '--profile', 'worker', 'stop', 'api', 'worker')
        }
        'down' {
            Invoke-Compose -ArgumentList @('--profile', 'api', '--profile', 'worker', 'down')
        }
        'logs' {
            Invoke-Compose -ArgumentList @('--profile', 'api', '--profile', 'worker', 'logs', '-f', 'api', 'worker')
        }
        'helm-lint' {
            $helmArgs = @('lint', '--strict', $chart)
            if ($Values) { $helmArgs += @('-f', $Values) }
            Invoke-Helm -ArgumentList $helmArgs
        }
        'helm-template' {
            if (-not $Values) {
                throw 'Values is required; see infra/helm/agent-platform/values.example.yaml.'
            }
            Invoke-Helm -ArgumentList @(
                'template', $Release, $chart,
                '--namespace', $Namespace,
                '-f', $Values,
                '--set', 'global.enabled=true',
                '--set-string', "global.image.repository=$ImageRepository",
                '--set-string', "global.image.tag=$ImageTag"
            )
        }
        'deploy' {
            if (-not $Values) {
                throw 'Values is required; see infra/helm/agent-platform/values.example.yaml.'
            }
            if ($ImageTag -eq 'local') {
                throw 'ImageTag=local is not deployable; set an immutable tag or digest.'
            }
            Invoke-Helm -ArgumentList @('lint', '--strict', $chart, '-f', $Values)
            $helmArgs = @(
                'upgrade', '--install', $Release, $chart,
                '--namespace', $Namespace, '--create-namespace',
                '-f', $Values,
                '--set', 'global.enabled=true',
                '--set-string', "global.image.repository=$ImageRepository",
                '--set-string', "global.image.tag=$ImageTag"
            )
            if ($KubeContext) { $helmArgs += @('--kube-context', $KubeContext) }
            $helmArgs += @('--rollback-on-failure', '--wait', '--timeout', $Timeout)
            Invoke-Helm -ArgumentList $helmArgs
        }
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    Pop-Location
}
