<#
.SYNOPSIS
  SmartOps demo control: preflight, up, reset, status, down, fix-docker.

.EXAMPLE
  .\demo.ps1 up          # checks, starts everything, warms models, prints READY
  .\demo.ps1 preflight   # explains anything that would ruin a demo
  .\demo.ps1 reset       # back to freshly seeded demo workspaces
  .\demo.ps1 up -Build   # rebuild images after code changes
  .\demo.ps1 backup      # database + evidence to sample-data\output\backups\<time>
  .\demo.ps1 restore     # latest backup (or: .\demo.ps1 restore <folder>)
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('up', 'preflight', 'reset', 'status', 'down', 'fix-docker', 'backup', 'restore')]
    [string]$Action = 'up',
    [Parameter(Position = 1)]
    [string]$From = '',
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot
$script:Problems = 0
$script:Warnings = 0
$ConsoleUrl = 'http://localhost:3000'
$ApiUrl = 'http://localhost:8000'
$OllamaUrl = 'http://127.0.0.1:11434'
$OllamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$Ports = @(3000, 8000, 8100, 8200, 8554, 8888, 8889, 9000, 9001, 9997, 1935)

function Write-Ok([string]$Text)   { Write-Host "  [ok]   $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "  [info] $Text" -ForegroundColor Gray }
function Write-Warn([string]$Text) { $script:Warnings++; Write-Host "  [warn] $Text" -ForegroundColor Yellow }
function Write-Bad([string]$Text, [string]$Fix) {
    $script:Problems++
    Write-Host "  [FAIL] $Text" -ForegroundColor Red
    if ($Fix) { Write-Host "         Fix: $Fix" -ForegroundColor Red }
}
function Write-Step([string]$Text) { Write-Host ''; Write-Host "== $Text" -ForegroundColor Cyan }

function Get-EnvValue([string]$Name, [string]$Default = '') {
    # Reads .env without printing it; secrets never reach the console.
    if (Test-Path '.env') {
        foreach ($line in Get-Content '.env') {
            if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$") {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    return $Default
}

function Invoke-WithTimeout([scriptblock]$Block, [int]$Seconds, [object[]]$Arguments = @()) {
    $job = Start-Job -ScriptBlock $Block -ArgumentList $Arguments
    if (Wait-Job $job -Timeout $Seconds) {
        $output = Receive-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force
        return $output
    }
    Remove-Job $job -Force
    return $null
}

function Test-Http([string]$Url, [int]$TimeoutSec = 5) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $response.StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

function Get-DockerEngineVersion {
    return Invoke-WithTimeout { docker version --format '{{.Server.Version}}' 2>$null } 25
}

function Test-StaleDockerSockets {
    $log = Join-Path $env:LOCALAPPDATA 'Docker\log\host\com.docker.backend.exe.log'
    if (-not (Test-Path $log)) { return $false }
    $tail = Get-Content $log -Tail 400 -ErrorAction SilentlyContinue
    return [bool]($tail | Select-String -SimpleMatch 'The file cannot be accessed by the system' | Select-Object -Last 1)
}

function Get-LanAddress {
    # The address a phone on the same Wi-Fi uses to reach this laptop.
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and
        $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|Loopback|VirtualBox|VMware' -and
        $_.PrefixOrigin -in @('Dhcp', 'Manual')
    }
    $preferred = $candidates | Where-Object { $_.InterfaceAlias -match 'Wi-?Fi|Wireless|WLAN' } | Select-Object -First 1
    if (-not $preferred) { $preferred = $candidates | Select-Object -First 1 }
    if ($preferred) { return $preferred.IPAddress }
    return $null
}

function Get-StreamManifest {
    $path = 'sample-data\streams.json'
    if (-not (Test-Path $path)) { return @() }
    return @((Get-Content $path -Raw | ConvertFrom-Json).streams)
}

# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
function Invoke-Preflight([switch]$StackExpected) {
    Write-Step 'Preflight'

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Bad 'Docker CLI not found.' 'Install Docker Desktop, then reopen PowerShell.'
        return
    }
    $engine = Get-DockerEngineVersion
    if ($engine) {
        Write-Ok "Docker engine $engine is running."
    } elseif (Test-StaleDockerSockets) {
        Write-Bad 'Docker Desktop is crash-looping on stale socket files (known Docker Desktop 4.76 issue).' '.\demo.ps1 fix-docker'
        return
    } elseif (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue) {
        Write-Bad 'Docker Desktop is open but its engine is not answering yet.' 'Wait 30 s and retry; if it persists, quit Docker Desktop from the tray and run .\demo.ps1 fix-docker.'
        return
    } else {
        Write-Bad 'Docker Desktop is not running.' 'Start Docker Desktop and wait until it says "Engine running".'
        return
    }

    $memBytes = Invoke-WithTimeout { docker info --format '{{.MemTotal}}' 2>$null } 20
    if ($memBytes) {
        $memGb = [math]::Round([double]$memBytes / 1GB, 1)
        if ($memGb -lt 3.5) { Write-Bad "Docker VM has only $memGb GB of memory." 'Set memory=4GB (or more) under [wsl2] in C:\Users\<you>\.wslconfig, then run: wsl --shutdown' }
        else { Write-Ok "Docker VM memory: $memGb GB (SmartOps uses about 1.2 GB)." }
    }

    $freeGb = [math]::Round((Get-PSDrive -Name C).Free / 1GB, 1)
    if ($freeGb -lt 10) { Write-Bad "Only $freeGb GB free on C:." 'Free at least 10 GB (Docker images, evidence clips).' }
    else { Write-Ok "Disk: $freeGb GB free on C:." }

    $ours = @()
    $running = Invoke-WithTimeout { docker ps --filter 'name=smartops-' --format '{{.Names}}' 2>$null } 20
    if ($running) { $ours = @($running) }
    foreach ($port in $Ports) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { continue }
        $owner = (Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        $dockerOwned = $owner -in @('com.docker.backend', 'wslrelay', 'vpnkit', 'docker-proxy')
        if (-not ($dockerOwned -and $ours.Count -gt 0)) {
            Write-Bad "Port $port is already used by '$owner'." "Stop that program or container, then retry."
        }
    }
    if ($script:Problems -eq 0) { Write-Ok 'Required ports are free or held by SmartOps.' }

    $provider = Get-EnvValue 'SMARTOPS_MODEL_PROVIDER' 'ollama'
    $vision = Get-EnvValue 'SMARTOPS_VISION_MODEL' 'qwen2.5vl:3b'
    if ($provider -eq 'ollama') {
        if (-not (Test-Path $OllamaExe)) {
            Write-Bad 'Native Ollama is not installed.' 'Install Ollama for Windows from ollama.com, then: ollama pull qwen2.5vl:3b'
        } else {
            try {
                $tags = Invoke-RestMethod "$OllamaUrl/api/tags" -TimeoutSec 5
                $names = @($tags.models | ForEach-Object { $_.name })
                if ($names -contains $vision) { Write-Ok "Ollama is running with $vision." }
                else { Write-Bad "Ollama is missing model $vision." "ollama pull $vision" }
            } catch {
                Write-Warn 'Ollama is installed but not running; "up" starts it.'
            }
        }
    } elseif ($provider -eq 'openrouter' -or $provider -eq 'openai-compatible') {
        if (Get-EnvValue 'SMARTOPS_MODEL_API_KEY') { Write-Ok "AI review uses hosted provider '$provider' (API key present)." }
        else { Write-Bad "SMARTOPS_MODEL_PROVIDER=$provider but SMARTOPS_MODEL_API_KEY is empty." 'Add the key to .env, or set SMARTOPS_MODEL_PROVIDER=ollama.' }
    } else {
        Write-Info "AI review provider: $provider."
    }

    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $gpu = (& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null | Select-Object -First 1)
        if ($gpu) { Write-Info "GPU visible: $gpu (the 4 GB VRAM cannot hold qwen2.5vl; Ollama runs it on CPU)." }
    } else {
        Write-Info 'No NVIDIA GPU visible; local AI review runs on CPU.'
    }

    $streams = @(Get-StreamManifest)
    if ($streams.Count -eq 0) { Write-Warn 'sample-data\streams.json lists no footage; only live cameras will produce incidents.' }
    foreach ($stream in $streams) {
        $file = Join-Path 'sample-data\input' $stream.file
        if (Test-Path -LiteralPath $file) { Write-Ok "Footage for '$($stream.path)': $($stream.file)" }
        else { Write-Bad "Footage missing for '$($stream.path)': $file" 'Copy the clip into sample-data\input or remove it from sample-data\streams.json.' }
    }

    if ($StackExpected) {
        try {
            $paths = Invoke-RestMethod 'http://127.0.0.1:9997/v3/paths/list' -TimeoutSec 5
            foreach ($stream in $streams) {
                $item = $paths.items | Where-Object { $_.name -eq $stream.path }
                if ($item -and $item.ready) { Write-Ok "mediamtx is publishing '$($stream.path)'." }
                else { Write-Bad "mediamtx is not publishing '$($stream.path)'." 'docker compose logs stream-publisher' }
            }
        } catch {
            Write-Bad 'mediamtx API is not reachable on 127.0.0.1:9997.' 'docker compose up -d mediamtx'
        }
    }
}

# ---------------------------------------------------------------------------
# helpers for up/reset
# ---------------------------------------------------------------------------
function Start-NativeOllama {
    try { Invoke-RestMethod "$OllamaUrl/api/version" -TimeoutSec 3 | Out-Null; return } catch { }
    Write-Info 'Starting native Ollama...'
    $env:OLLAMA_CONTEXT_LENGTH = '2048'
    $env:OLLAMA_NUM_PARALLEL = '1'
    $env:OLLAMA_MAX_LOADED_MODELS = '1'
    $env:OLLAMA_FLASH_ATTENTION = '1'
    $env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
    $logDir = Join-Path $PSScriptRoot 'sample-data\output'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    # Launch through cmd with shell-execute so Ollama inherits none of this
    # script's handles (an inherited output pipe kept the script from exiting).
    $log = Join-Path $logDir 'ollama-native.log'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "`"`"$OllamaExe`" serve > `"$log`" 2>&1`"" -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try { Invoke-RestMethod "$OllamaUrl/api/version" -TimeoutSec 2 | Out-Null; Write-Ok 'Ollama started.'; return } catch { }
    }
    Write-Warn 'Ollama did not answer within 30 s; incidents will show "AI review unavailable".'
}

function Get-LocalVisionModel {
    # The model native Ollama must serve: the primary when the provider is
    # ollama, otherwise the configured local fallback (if any).
    if ((Get-EnvValue 'SMARTOPS_MODEL_PROVIDER' 'ollama') -eq 'ollama') { return Get-EnvValue 'SMARTOPS_VISION_MODEL' 'qwen2.5vl:3b' }
    if ((Get-EnvValue 'SMARTOPS_MODEL_FALLBACK') -eq 'ollama') { return Get-EnvValue 'SMARTOPS_FALLBACK_VISION_MODEL' 'qwen2.5vl:3b' }
    return $null
}

function Invoke-ModelWarmup {
    $vision = Get-LocalVisionModel
    if (-not $vision) {
        Write-Info "Hosted provider '$(Get-EnvValue 'SMARTOPS_MODEL_PROVIDER')' with no local fallback: nothing to warm."
        return
    }
    try {
        $loaded = Invoke-RestMethod "$OllamaUrl/api/ps" -TimeoutSec 5
        if (@($loaded.models | Where-Object { $_.name -eq $vision }).Count -gt 0) { Write-Ok "$vision already loaded."; return }
    } catch { }
    Write-Info "Loading $vision (about 2 minutes on a cold start)..."
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        # Options must match the orchestrator's (LOAD_OPTIONS) or Ollama reloads on the first review.
        $body = @{ model = $vision; keep_alive = '60m'; prompt = ''; options = @{ num_ctx = 2048; num_batch = 32; num_thread = 4 } } | ConvertTo-Json
        Invoke-RestMethod "$OllamaUrl/api/generate" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 240 | Out-Null
        Write-Ok ("{0} warmed in {1:N0} s; it stays loaded for 60 minutes." -f $vision, $watch.Elapsed.TotalSeconds)
    } catch {
        Write-Warn "Could not warm ${vision}: $($_.Exception.Message). Incidents still fire; AI review will report unavailable."
    }
}

function Wait-ForUrl([string]$Url, [int]$Seconds, [string]$Name) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if ((Test-Http $Url 3) -eq 200) { Write-Ok "$Name is up."; return $true }
        Start-Sleep -Seconds 2
    }
    Write-Bad "$Name did not become healthy within $Seconds s." "docker compose logs --tail 80"
    return $false
}

function Wait-ForStreams([int]$Seconds) {
    $streams = @(Get-StreamManifest)
    if ($streams.Count -eq 0) { return }
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $paths = Invoke-RestMethod 'http://127.0.0.1:9997/v3/paths/list' -TimeoutSec 3
            $readyNames = @($paths.items | Where-Object { $_.ready } | ForEach-Object { $_.name })
            $missing = @($streams | Where-Object { $readyNames -notcontains $_.path })
            if ($missing.Count -eq 0) { Write-Ok "$($streams.Count) recorded stream(s) publishing."; return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    Write-Warn 'Not every recorded stream is publishing yet (first start prepares each clip once).'
}

# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
function Start-DockerIfNeeded {
    if (Get-DockerEngineVersion) { return }
    # Docker Desktop 4.76 leaves AF_UNIX socket files behind on every stop and
    # then crash-loops on the next start. Clearing them first is safe.
    $runDir = Join-Path $env:LOCALAPPDATA 'Docker\run'
    $stale = @(Get-ChildItem $runDir -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue).Count -gt 0
    if ($stale -or (Test-StaleDockerSockets)) {
        Write-Info 'Docker is not running and stale socket files are present; repairing before start.'
        Invoke-FixDocker
        return
    }
    Write-Info 'Starting Docker Desktop...'
    Start-Process -FilePath (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        if (Get-DockerEngineVersion) { Write-Ok 'Docker engine is running.'; return }
    }
}

function Invoke-Up {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    Start-DockerIfNeeded
    Invoke-Preflight
    if ($script:Problems -gt 0) {
        Write-Host ''
        Write-Host "Preflight found $($script:Problems) problem(s); fix them and run .\demo.ps1 up again." -ForegroundColor Red
        exit 1
    }
    Write-Step 'Starting'
    if (Get-LocalVisionModel) { Start-NativeOllama }
    $lan = Get-LanAddress
    if ($lan) { $env:SMARTOPS_INGEST_HOST = $lan; Write-Info "Phones on this network publish to $lan (RTMP 1935)." }
    else { Write-Warn 'No Wi-Fi/Ethernet address found; phone cameras cannot connect until the laptop is on a network.' }
    $composeArgs = @('compose', 'up', '-d', '--remove-orphans')
    if ($Build) { $composeArgs += '--build' }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) { Write-Bad 'docker compose up failed.' 'Read the error above; then: docker compose logs --tail 80'; exit 1 }
    # The publisher reads streams.json once at start; pick up an edited manifest.
    $manifestPath = Join-Path $PSScriptRoot 'sample-data\streams.json'
    $startedRaw = & docker inspect -f '{{.State.StartedAt}}' smartops-stream-publisher 2>$null
    if ($startedRaw -and (Test-Path $manifestPath)) {
        $started = [datetime]::Parse($startedRaw, [Globalization.CultureInfo]::InvariantCulture).ToUniversalTime()
        if ((Get-Item $manifestPath).LastWriteTimeUtc -gt $started) {
            Write-Info 'sample-data\streams.json changed since the publisher started; restarting it.'
            & docker compose restart stream-publisher | Out-Null
        }
    }
    # Migrations and the demo seed run inside the API's startup.
    if (-not (Wait-ForUrl "$ApiUrl/health" 120 'API (migrations + seed)')) { exit 1 }
    if (-not (Wait-ForUrl "$ConsoleUrl/login" 90 'Console')) { exit 1 }
    Wait-ForStreams 60
    Invoke-ModelWarmup
    Write-Host ''
    Write-Host ("READY -> {0}   ({1:N0} s)" -f $ConsoleUrl, $watch.Elapsed.TotalSeconds) -ForegroundColor Green
    Write-Host '  Sign in: operator@mall.demo / smartops-demo  (also admin@, viewer@; office: @smartops.local; campus: @campus.demo)'
    if ($script:Warnings -gt 0) { Write-Host "  $($script:Warnings) warning(s) above." -ForegroundColor Yellow }
}

function Invoke-Reset {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    Write-Step 'Resetting demo data'
    if (-not (Get-DockerEngineVersion)) { Write-Bad 'Docker is not running.' '.\demo.ps1 preflight'; exit 1 }
    & docker compose stop stream-processor notifier | Out-Null
    & docker compose exec -T api python -m app.reset_demo
    if ($LASTEXITCODE -ne 0) { Write-Bad 'Database reset failed.' 'docker compose logs api --tail 80'; exit 1 }
    & docker compose run --rm --no-deps --entrypoint sh stream-processor -c 'rm -rf /data/*' | Out-Null
    & docker compose exec -T redis redis-cli FLUSHDB | Out-Null
    & docker compose start stream-processor notifier | Out-Null
    Write-Ok 'Processor journals and realtime state cleared; pipeline restarted.'
    Write-Host ("Reset complete in {0:N0} s. Everyone is signed out; sign in again at {1}" -f $watch.Elapsed.TotalSeconds, $ConsoleUrl) -ForegroundColor Green
}

function Invoke-Status {
    Write-Step 'Containers'
    & docker compose ps --format 'table {{.Name}}\t{{.Status}}'
    Write-Step 'Streams'
    try {
        $paths = Invoke-RestMethod 'http://127.0.0.1:9997/v3/paths/list' -TimeoutSec 3
        foreach ($item in $paths.items) { Write-Info ("{0}: ready={1}, readers={2}" -f $item.name, $item.ready, @($item.readers).Count) }
    } catch { Write-Warn 'mediamtx API unreachable.' }
    try {
        $loaded = Invoke-RestMethod "$OllamaUrl/api/ps" -TimeoutSec 3
        $names = @($loaded.models | ForEach-Object { $_.name }) -join ', '
        Write-Info ("Ollama loaded models: {0}" -f $(if ($names) { $names } else { 'none' }))
    } catch { Write-Info 'Ollama not running.' }
}

function Invoke-FixDocker {
    Write-Step 'Repairing Docker Desktop stale sockets'
    Write-Info 'Stopping Docker Desktop...'
    Get-Process 'Docker Desktop', 'com.docker.backend', 'com.docker.build', 'docker-ai' -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 3
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    foreach ($dir in @((Join-Path $env:LOCALAPPDATA 'Docker\run'), (Join-Path $env:LOCALAPPDATA 'docker-secrets-engine'))) {
        if (Test-Path $dir) {
            Rename-Item -Path $dir -NewName ("{0}.stale-{1}" -f (Split-Path $dir -Leaf), $stamp)
            Write-Ok "Moved aside $dir (Docker recreates it; volumes are untouched)."
        }
    }
    Start-Process -FilePath (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        $version = Get-DockerEngineVersion
        if ($version) { Write-Ok "Docker engine $version is running."; return }
    }
    Write-Bad 'Docker did not come back within 3 minutes.' 'Open Docker Desktop and read its error. Do NOT choose "Reset to factory defaults" (it deletes all volumes).'
}

function Invoke-Backup {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    Write-Step 'Backing up database and evidence'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dir = Join-Path $PSScriptRoot "sample-data\output\backups\$stamp"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $db = Get-EnvValue 'POSTGRES_DB' 'smartops'
    $user = Get-EnvValue 'POSTGRES_USER' 'smartops'
    & docker compose exec -T postgres pg_dump -U $user -d $db -Fc -f /tmp/smartops.dump
    if ($LASTEXITCODE -ne 0) { Write-Bad 'pg_dump failed.' 'docker compose logs postgres --tail 50'; exit 1 }
    & docker compose cp postgres:/tmp/smartops.dump (Join-Path $dir 'database.dump') | Out-Null
    & docker compose exec -T postgres rm -f /tmp/smartops.dump | Out-Null
    # Evidence objects: copy the MinIO volume while MinIO is stopped (consistent).
    & docker compose stop minio | Out-Null
    & docker compose run --rm --no-deps -v smartops_minio_data:/minio:ro -v "${dir}:/backup" --entrypoint tar postgres -czf /backup/evidence.tgz -C /minio .
    $tarCode = $LASTEXITCODE
    & docker compose start minio | Out-Null
    if ($tarCode -ne 0) { Write-Bad 'Evidence archive failed.' ''; exit 1 }
    $size = (Get-ChildItem $dir | Measure-Object Length -Sum).Sum / 1MB
    Write-Ok ("Backup written to {0} ({1:N1} MB) in {2:N0} s" -f $dir, $size, $watch.Elapsed.TotalSeconds)
}

function Invoke-Restore([string]$From) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    if (-not $From) {
        $latest = Get-ChildItem (Join-Path $PSScriptRoot 'sample-data\output\backups') -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName 'database.dump') } | Sort-Object Name | Select-Object -Last 1
        if (-not $latest) { Write-Bad 'No backup found.' '.\demo.ps1 backup'; exit 1 }
        $From = $latest.FullName
    }
    $From = (Resolve-Path $From).Path
    foreach ($file in 'database.dump', 'evidence.tgz') {
        if (-not (Test-Path (Join-Path $From $file))) { Write-Bad "Backup is missing $file." ''; exit 1 }
    }
    Write-Step "Restoring $From"
    $db = Get-EnvValue 'POSTGRES_DB' 'smartops'
    $user = Get-EnvValue 'POSTGRES_USER' 'smartops'
    & docker compose stop stream-processor notifier api minio | Out-Null
    & docker compose cp (Join-Path $From 'database.dump') postgres:/tmp/restore.dump | Out-Null
    & docker compose exec -T postgres pg_restore -U $user -d $db --clean --if-exists --no-owner /tmp/restore.dump
    $restoreCode = $LASTEXITCODE
    & docker compose exec -T postgres rm -f /tmp/restore.dump | Out-Null
    & docker compose run --rm --no-deps -v smartops_minio_data:/minio -v "${From}:/backup:ro" --entrypoint sh postgres -c 'find /minio -mindepth 1 -delete && tar -xzf /backup/evidence.tgz -C /minio'
    $tarCode = $LASTEXITCODE
    & docker compose run --rm --no-deps --entrypoint sh stream-processor -c 'rm -rf /data/*' | Out-Null
    & docker compose exec -T redis redis-cli FLUSHDB | Out-Null
    & docker compose start minio api notifier stream-processor | Out-Null
    if ($restoreCode -ne 0 -or $tarCode -ne 0) { Write-Bad 'Restore reported errors (see above).' ''; exit 1 }
    Write-Ok ("Restored in {0:N0} s. Everyone is signed out." -f $watch.Elapsed.TotalSeconds)
}

switch ($Action) {
    'preflight' {
        $running = Invoke-WithTimeout { docker ps --filter 'name=smartops-api' --format '{{.Names}}' 2>$null } 20
        Invoke-Preflight -StackExpected:([bool]$running)
        Write-Host ''
        if ($script:Problems -gt 0) { Write-Host "$($script:Problems) problem(s) would affect the demo." -ForegroundColor Red; exit 1 }
        Write-Host 'Preflight passed.' -ForegroundColor Green
    }
    'up' { Invoke-Up }
    'reset' { Invoke-Reset }
    'status' { Invoke-Status }
    'down' { & docker compose down }
    'fix-docker' { Invoke-FixDocker }
    'backup' { Invoke-Backup }
    'restore' { Invoke-Restore $From }
}
