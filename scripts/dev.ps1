<#
.SYNOPSIS
    Start the Finlume backend (Django) and web frontend (Vite) together for development.

.DESCRIPTION
    Checks prerequisites, refuses to start if a port is taken, then runs:
      backend  python manage.py runserver 127.0.0.1:<BackendPort>   (in backend/)
      web      vite --host 127.0.0.1 --port <WebPort> --strictPort  (in apps/web/)
    Output of both is shown with [api] / [web] prefixes and kept in .dev/logs/.
    Press Ctrl+C to stop both services, including their child processes.

    Before starting, it runs the read-only "manage.py dbstatus": the database must
    be reachable (PostgreSQL by default), and pending migrations are reported.

    It never installs packages, runs migrations, changes data, or starts Docker
    or the mobile app.

.PARAMETER BackendPort
    Port for Django (default 8000). Vite's /api proxy is pointed at it.

.PARAMETER WebPort
    Port for Vite (default 5173).

.PARAMETER CheckOnly
    Run the prerequisite and port checks, then exit without starting anything.

.PARAMETER Smoke
    Start both services, wait until they answer, then stop them and exit.
    Exit code 0 means everything started and shut down cleanly.

.PARAMETER ReadyTimeoutSeconds
    How long to wait for both services to answer (default 60).

.EXAMPLE
    .\scripts\dev.ps1

.EXAMPLE
    .\scripts\dev.ps1 -BackendPort 8001
#>
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)][int]$WebPort = 5173,
    [switch]$CheckOnly,
    [switch]$Smoke,
    [ValidateRange(5, 600)][int]$ReadyTimeoutSeconds = 60
)

# Native tools write harmless warnings to stderr; under "Stop" Windows
# PowerShell 5.1 would turn those into terminating errors. Results are judged
# by exit codes and explicit checks instead.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$WebDir = Join-Path $RepoRoot "apps\web"
$LogDir = Join-Path $RepoRoot ".dev\logs"
$BackendUrl = "http://127.0.0.1:$BackendPort"
$WebUrl = "http://127.0.0.1:$WebPort"
$HealthPath = "/api/v1/health/"

function Write-Step([string]$Message) { Write-Host "[dev] $Message" }
function Write-Good([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Green }
function Write-Caution([string]$Message) { Write-Host "[dev] WARNING: $Message" -ForegroundColor Yellow }
function Write-Problem([string]$Message) { Write-Host "[dev] ERROR: $Message" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

function Get-PortListener([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 0) { return $null }
        $ownerId = $listeners[0].OwningProcess
        $owner = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
        $name = if ($owner) { $owner.ProcessName } else { "an unknown process" }
        return "$name (PID $ownerId)"
    }
    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
    try { $probe.Start(); return $null } catch { return "another process" } finally { $probe.Stop() }
}

function Test-Prerequisites {
    $problems = New-Object System.Collections.Generic.List[string]
    $result = @{ Python = $null; Node = $null; ViteScript = $null }

    foreach ($required in @(
            @((Join-Path $BackendDir "manage.py"), "the Django project"),
            @((Join-Path $WebDir "package.json"), "the web app"),
            @((Join-Path $WebDir "vite.config.ts"), "the web app's Vite configuration"))) {
        if (-not (Test-Path -LiteralPath $required[0])) {
            $problems.Add("Missing $($required[0]) ($($required[1])). Run this script from a complete Finlume checkout.")
        }
    }

    # Python: the repository's .venv first, then an activated virtual environment.
    $candidates = @(Join-Path $RepoRoot ".venv\Scripts\python.exe")
    if ($env:VIRTUAL_ENV) { $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe") }
    $python = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $python) {
        $problems.Add("No Python virtual environment found at .venv. Create it and install the backend: " +
            "python -m venv .venv; .\.venv\Scripts\python.exe -m pip install --require-hashes -r backend\requirements\dev.txt")
    }
    else {
        $djangoVersion = & $python -c "import django, rest_framework; print(django.get_version())" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $problems.Add("Django is not installed in $python. Run: & '$python' -m pip install --require-hashes -r backend\requirements\dev.txt")
        }
        else {
            $result.Python = $python
            Write-Good "Python: $python (Django $djangoVersion)"
        }
    }

    # Node.js, matching apps/web/package.json engines (^22.13.0 || >=24.0.0).
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCommand) {
        $problems.Add("Node.js was not found on PATH. Install Node.js 22 LTS (22.13 or newer) or 24 LTS.")
    }
    else {
        $nodeVersion = (& $nodeCommand.Source --version).TrimStart("v")
        $parts = $nodeVersion.Split(".")
        $major = [int]$parts[0]; $minor = [int]$parts[1]
        if ($major -lt 22 -or ($major -eq 22 -and $minor -lt 13)) {
            $problems.Add("Node.js $nodeVersion is too old for apps/web; install 22.13+ or 24 LTS.")
        }
        else {
            if ($major -eq 23) { Write-Caution "Node.js $nodeVersion is not an LTS release; apps/web supports 22.13+ and 24+." }
            $result.Node = $nodeCommand.Source
            Write-Good "Node.js: v$nodeVersion"
        }
    }

    # Web dependencies must already be installed; this script never installs them.
    $viteScript = Join-Path $WebDir "node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $viteScript)) {
        $problems.Add("Web dependencies are not installed. Run: cd apps\web; npm ci")
    }
    else {
        $result.ViteScript = $viteScript
        $lock = Join-Path $WebDir "package-lock.json"
        $installed = Join-Path $WebDir "node_modules\.package-lock.json"
        if ((Test-Path -LiteralPath $lock) -and (Test-Path -LiteralPath $installed) -and
            (Get-Item -LiteralPath $lock).LastWriteTime -gt (Get-Item -LiteralPath $installed).LastWriteTime) {
            Write-Caution "apps/web/package-lock.json changed since the last install; run 'npm ci' in apps\web if the app fails to start."
        }
    }

    # Ports: report the owner instead of silently picking another port.
    if ($BackendPort -eq $WebPort) {
        $problems.Add("BackendPort and WebPort must differ (both are $BackendPort).")
    }
    foreach ($entry in @(@("Backend", $BackendPort, "-BackendPort"), @("Web", $WebPort, "-WebPort"))) {
        $owner = Get-PortListener $entry[1]
        if ($owner) {
            $problems.Add("Port $($entry[1]) ($($entry[0])) is already in use by $owner. " +
                "Stop that process (it may be an earlier Finlume server), or choose another port with $($entry[2]) <port>.")
        }
    }

    if (Test-Path -LiteralPath (Join-Path $RepoRoot ".env")) {
        Write-Step "Configuration: .env found and used by Django (values not shown)."
    }
    else {
        Write-Step "Configuration: no .env found. Development expects PostgreSQL settings from .env (copy .env.example)."
    }
    $settingsModule = if ($env:DJANGO_SETTINGS_MODULE) { $env:DJANGO_SETTINGS_MODULE } else { "config.settings.development" }
    Write-Step "Django settings: $settingsModule"
    if ($settingsModule -ne "config.settings.development") {
        Write-Caution "DJANGO_SETTINGS_MODULE is set to $settingsModule; this launcher is meant for config.settings.development."
    }

    if ($result.Python) { Test-Database $result.Python $problems }

    $result.Problems = $problems
    return $result
}

function Test-Database([string]$Python, $Problems) {
    # Read-only: shows the target, connects, and lists pending migrations.
    # It never migrates or writes (see backend/apps/core/management/commands/dbstatus.py).
    Push-Location -LiteralPath $BackendDir
    try {
        $output = @(& $Python manage.py dbstatus 2>&1 | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
        $code = $LASTEXITCODE
    }
    finally { Pop-Location }

    $details = @($output | Where-Object { $_ -match "^(Database|Connection|Migrations):" })
    $commandError = $output | Where-Object { $_ -match "^CommandError: " } | Select-Object -Last 1
    $commandError = if ($commandError) { $commandError -replace "^CommandError: ", "" } else { $null }

    switch ($code) {
        0 { foreach ($line in $details) { Write-Good $line } }
        3 {
            foreach ($line in $details) { Write-Good $line }
            Write-Caution "$commandError The launcher never migrates."
        }
        2 {
            foreach ($line in $details) { Write-Step $line }
            $Problems.Add("$commandError Start PostgreSQL (for the Docker option: 'docker compose up -d db' in the repository root), " +
                "or correct POSTGRES_HOST / POSTGRES_PORT in .env. See docs\development\LOCAL_SETUP.md.")
        }
        default {
            $reason = $output | Where-Object { $_ -match "ImproperlyConfigured: " } | Select-Object -Last 1
            $reason = if ($reason) { $reason -replace "^.*ImproperlyConfigured: ", "" } else { ($output | Select-Object -Last 1) }
            $Problems.Add("Database configuration: $reason")
        }
    }
    if ($details | Where-Object { $_ -match "^Database: SQLite" }) {
        Write-Caution "Using SQLite because FINLUME_DB_ENGINE=sqlite is set. Throwaway trials only: PostgreSQL is Finlume's database."
    }
}

# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

function Start-DevProcess {
    param([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory, [string]$Prefix, [string]$Color)
    $stdout = Join-Path $LogDir "$Name.stdout.log"
    $stderr = Join-Path $LogDir "$Name.stderr.log"
    foreach ($log in @($stdout, $stderr)) {
        if (Test-Path -LiteralPath $log) { Move-Item -LiteralPath $log -Destination ($log -replace "\.log$", ".previous.log") -Force }
    }
    # An empty stdin keeps Vite out of interactive (raw) mode, which would
    # otherwise swallow Ctrl+C before this script sees it.
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
        -NoNewWindow -PassThru -RedirectStandardInput $script:EmptyInput `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ErrorAction Stop
    $null = $process.Handle  # keep a handle so ExitCode stays available after exit
    $service = [pscustomobject]@{
        Name = $Name; Process = $process; Logs = @($stdout, $stderr); Prefix = $Prefix; Color = $Color
        Descendants = New-Object System.Collections.Generic.List[System.Diagnostics.Process]
    }
    foreach ($log in $service.Logs) {
        $script:LogReaders[$log] = @{ Position = 0L; Decoder = [System.Text.Encoding]::UTF8.GetDecoder(); Pending = ""; Prefix = $Prefix; Color = $Color }
    }
    return $service
}

function Show-NewLogOutput {
    foreach ($path in @($script:LogReaders.Keys)) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $state = $script:LogReaders[$path]
        $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $length = $stream.Length - $state.Position
            if ($length -le 0) { continue }
            $null = $stream.Seek($state.Position, [System.IO.SeekOrigin]::Begin)
            $bytes = New-Object byte[] $length
            $read = $stream.Read($bytes, 0, $length)
            $state.Position += $read
        }
        finally { $stream.Dispose() }
        $chars = New-Object char[] ($state.Decoder.GetCharCount($bytes, 0, $read))
        $null = $state.Decoder.GetChars($bytes, 0, $read, $chars, 0)
        $text = $state.Pending + (New-Object string (, $chars))
        $lines = $text -split "`n"
        $state.Pending = $lines[-1]  # an unfinished line waits for the next read
        for ($i = 0; $i -lt $lines.Count - 1; $i++) {
            $clean = $lines[$i].TrimEnd("`r")
            if ($clean.Trim().Length -gt 0) { Write-Host "$($state.Prefix) $clean" -ForegroundColor $state.Color }
        }
    }
}

function Get-ChildProcesses([int]$ParentId) {
    $all = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId -ErrorAction SilentlyContinue)
    $found = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($ParentId)
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        foreach ($candidate in $all) {
            if ($candidate.ParentProcessId -eq $current -and $candidate.ProcessId -ne $ParentId -and -not $found.Contains([int]$candidate.ProcessId)) {
                $found.Add([int]$candidate.ProcessId); $queue.Enqueue([int]$candidate.ProcessId)
            }
        }
    }
    return $found
}

function Save-Descendants($Service) {
    if ($Service.Process.HasExited) { return }
    foreach ($childId in Get-ChildProcesses $Service.Process.Id) {
        if ($Service.Descendants | Where-Object { $_.Id -eq $childId }) { continue }
        # Process objects hold a handle, so a recycled PID can never be killed by mistake.
        $child = Get-Process -Id $childId -ErrorAction SilentlyContinue
        if ($child) { $null = $child.Handle; $Service.Descendants.Add($child) }
    }
}

function Stop-DevProcess($Service) {
    Save-Descendants $Service
    if (-not $Service.Process.HasExited) {
        # Killing only the parent would orphan children such as Django's autoreloader.
        # Ctrl+C also reaches the children, so the process may exit before taskkill
        # runs; its "not found" message is expected and discarded.
        $null = & taskkill.exe /PID $Service.Process.Id /T /F 2>&1
    }
    foreach ($child in $Service.Descendants) {
        if (-not $child.HasExited) { try { $child.Kill() } catch { } }
    }
    $null = $Service.Process.WaitForExit(5000)
}

function Get-HttpStatus([string]$Url) {
    try {
        return [int](Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3).StatusCode
    }
    catch {
        $response = $_.Exception.Response
        if ($response) { return [int]$response.StatusCode }
        return 0
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

Write-Step "Finlume development launcher (repository: $RepoRoot)"
$prereqs = Test-Prerequisites
if ($prereqs.Problems.Count -gt 0) {
    foreach ($problem in $prereqs.Problems) { Write-Problem $problem }
    Write-Problem "Nothing was started."
    exit 1
}
if ($CheckOnly) {
    Write-Good "All checks passed. Backend would use $BackendUrl, web $WebUrl."
    exit 0
}

$null = New-Item -ItemType Directory -Force -Path $LogDir
$script:EmptyInput = Join-Path $LogDir "empty-stdin.txt"
[System.IO.File]::WriteAllText($script:EmptyInput, "")
$script:LogReaders = @{}
$services = @()
$exitCode = 0
$previousOutputEncoding = [Console]::OutputEncoding

# Child processes inherit these; the caller's session gets its values back afterwards.
$childEnvironment = @{
    PYTHONUNBUFFERED         = "1"            # show Django output immediately
    PYTHONIOENCODING         = "utf-8"
    FINLUME_API_PROXY_TARGET = $BackendUrl    # Vite's /api proxy -> this backend
}
$savedEnvironment = @{}
foreach ($key in $childEnvironment.Keys) {
    $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

try {
    try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
    foreach ($key in $childEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $childEnvironment[$key], "Process") }
    try {
        Write-Step "Starting backend: python manage.py runserver 127.0.0.1:$BackendPort"
        $services += Start-DevProcess -Name "backend" -FilePath $prereqs.Python `
            -Arguments @("manage.py", "runserver", "127.0.0.1:$BackendPort") -WorkingDirectory $BackendDir -Prefix "[api]" -Color "Cyan"
        Write-Step "Starting web: vite --host 127.0.0.1 --port $WebPort --strictPort"
        $services += Start-DevProcess -Name "web" -FilePath $prereqs.Node `
            -Arguments @("node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "$WebPort", "--strictPort") `
            -WorkingDirectory $WebDir -Prefix "[web]" -Color "Magenta"
    }
    finally {
        foreach ($key in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], "Process") }
    }

    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    $backendStatus = 0; $webStatus = 0; $ready = $false; $nextProbe = Get-Date
    while ($true) {
        Show-NewLogOutput

        $failed = $services | Where-Object { $_.Process.HasExited } | Select-Object -First 1
        if ($failed) {
            Start-Sleep -Milliseconds 300; Show-NewLogOutput
            Write-Problem "The $($failed.Name) process exited unexpectedly (exit code $($failed.Process.ExitCode)). Logs: $($failed.Logs -join ', ')"
            $exitCode = 1
            break
        }

        if (-not $ready -and (Get-Date) -ge $nextProbe) {
            $nextProbe = (Get-Date).AddSeconds(1)
            if ($backendStatus -notin 200, 503) { $backendStatus = Get-HttpStatus "$BackendUrl$HealthPath" }
            if ($webStatus -ne 200) { $webStatus = Get-HttpStatus "$WebUrl/" }
            if ($backendStatus -in 200, 503 -and $webStatus -eq 200) {
                $ready = $true
                foreach ($service in $services) { Save-Descendants $service }
                $proxyStatus = Get-HttpStatus "$WebUrl$HealthPath"
                Write-Host ""
                Write-Good "Finlume is running."
                Write-Good "  Web frontend:  $WebUrl"
                Write-Good "  Backend API:   $BackendUrl/api/v1/   (health: $BackendUrl$HealthPath)"
                Write-Good "  Django admin:  $BackendUrl/admin/"
                if ($backendStatus -eq 503) {
                    Write-Caution "The backend is up but cannot reach its database (health 503). Check PostgreSQL and the POSTGRES_* settings in .env."
                }
                if ($proxyStatus -notin 200, 503) {
                    Write-Caution "The web app's /api proxy did not reach the backend (HTTP $proxyStatus). Check FINLUME_API_PROXY_TARGET in apps\web\.env.local."
                }
                Write-Step "Logs: $LogDir"
                Write-Step "Press Ctrl+C to stop both services."
                Write-Host ""
                if ($Smoke) { Write-Step "Smoke test: services answered; shutting down."; break }
            }
            elseif ((Get-Date) -ge $deadline) {
                Write-Problem "Timed out after $ReadyTimeoutSeconds s waiting for the services (backend health: HTTP $backendStatus, web: HTTP $webStatus). See the output above and $LogDir."
                $exitCode = 1
                break
            }
        }
        Start-Sleep -Milliseconds 250
    }
}
catch {
    # Ctrl+C is not caught here (it stops the pipeline); the finally block still runs.
    Write-Problem "Could not start the services: $($_.Exception.Message)"
    $exitCode = 1
}
finally {
    # Runs on normal exit, on errors and when Ctrl+C stops the script.
    if ($services.Count -gt 0) {
        Write-Step "Stopping services..."
        foreach ($service in $services) { Stop-DevProcess $service }
        Show-NewLogOutput
        $stillBusy = @()
        foreach ($port in @($BackendPort, $WebPort)) {
            $owner = $null
            for ($attempt = 0; $attempt -lt 20; $attempt++) {
                $owner = Get-PortListener $port
                if (-not $owner) { break }
                Start-Sleep -Milliseconds 250
            }
            if ($owner) { $stillBusy += "port $port is still used by $owner" }
        }
        if ($stillBusy.Count -gt 0) {
            Write-Caution ("After shutdown, " + ($stillBusy -join "; ") + ". Stop it manually (taskkill /PID <pid> /T /F).")
            if ($exitCode -eq 0) { $exitCode = 1 }
        }
        else {
            Write-Good "Stopped. Ports $BackendPort and $WebPort are free. Logs kept in $LogDir."
        }
    }
    try { [Console]::OutputEncoding = $previousOutputEncoding } catch { }
}
exit $exitCode
