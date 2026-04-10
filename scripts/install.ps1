# See licence: https://github.com/FranBarInstance/memento-context
# Memento Context Installation Script for Windows
# Usage: Invoke-WebRequest -Uri "https://raw.githubusercontent.com/FranBarInstance/memento-context/main/scripts/install.ps1" -OutFile install.ps1; .\install.ps1

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/FranBarInstance/memento-context.git"
$InstallDir = Join-Path $env:USERPROFILE ".memento-context-src"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "    Installing Memento Context Server      " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# 1. Ensure git is installed
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Error: git is required but not installed." -ForegroundColor Red
    exit 1
}

# 2. Clone or update repository
if (-not (Test-Path $InstallDir)) {
    Write-Host "=> Cloning repository..." -ForegroundColor Yellow
    git clone --quiet $RepoUrl $InstallDir
} else {
    Write-Host "=> Updating existing repository..." -ForegroundColor Yellow
    Set-Location $InstallDir
    git pull --quiet
}

Set-Location $InstallDir

# 3. Install via Pipx or Pip
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host "=> Installing via pipx (Isolated Environment)..." -ForegroundColor Yellow
    pipx install .
} elseif (Get-Command pip -ErrorAction SilentlyContinue) {
    Write-Host "=> Warning: pipx not found. Falling back to standard pip..." -ForegroundColor Yellow
    pip install --user .
} else {
    Write-Host "Error: Python pip or pipx is required to install Memento Context." -ForegroundColor Red
    exit 1
}

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!              " -ForegroundColor Green
Write-Host "  You can now use the command:        " -ForegroundColor Green
Write-Host "  memento-context                          " -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
