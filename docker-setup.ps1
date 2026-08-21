# CharchaNotes Docker setup for Windows PowerShell
[CmdletBinding()]
param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Install and start Docker Desktop, then run this script again."
}

try {
    docker compose version | Out-Null
} catch {
    throw "Docker Compose v2 is required. Update Docker Desktop and try again."
}

$envFile = Join-Path $PSScriptRoot ".env"
$exampleFile = Join-Path $PSScriptRoot ".env.example"

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $exampleFile -Destination $envFile
}

$secureToken = Read-Host "Enter your Hugging Face token" -AsSecureString
$tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $hfToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr)
}

if ([string]::IsNullOrWhiteSpace($hfToken)) {
    throw "A Hugging Face token is required for Whisper and pyannote model setup."
}

$envLines = if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile
} else {
    @()
}
$envLines = @($envLines | Where-Object { $_ -notmatch "^HF_TOKEN=" })
Set-Content -LiteralPath $envFile -Value ($envLines + "HF_TOKEN=$hfToken")

Write-Host "Building CharchaNotes containers..." -ForegroundColor Cyan
if (-not $NoBuild) {
    docker compose build
}

Write-Host "Starting CharchaNotes..." -ForegroundColor Cyan
docker compose up -d
docker compose ps

Write-Host ""
Write-Host "Web UI:    http://localhost:5173"
Write-Host "API docs:  http://localhost:8000/docs"
Write-Host "llama.cpp: http://localhost:8080"
Write-Host ""
Write-Host "Watch logs with: docker compose logs -f"
