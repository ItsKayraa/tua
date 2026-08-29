$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:LOCALAPPDATA "Tua"

Write-Host "Installing Tua..."

# Remove old installation
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

# Create installation directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Copy entire project recursively
Get-ChildItem -Path $PSScriptRoot -Force |
    Where-Object {
        $_.Name -notin @(
            "install.ps1",
            "install.sh",
            ".git"
        )
    } |
    Copy-Item -Destination $InstallDir -Recurse -Force

# Create launcher
$Launcher = Join-Path $InstallDir "tua.cmd"

@"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tua.ps1" %*
"@ | Set-Content $Launcher -Encoding ASCII

# Add installation directory to User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ([string]::IsNullOrWhiteSpace($UserPath)) {
    $UserPath = $InstallDir
}
elseif (($UserPath -split ';') -notcontains $InstallDir) {
    $UserPath += ";$InstallDir"
}

[Environment]::SetEnvironmentVariable(
    "Path",
    $UserPath,
    "User"
)

# Update current PowerShell PATH
if (($env:Path -split ';') -notcontains $InstallDir) {
    $env:Path += ";$InstallDir"
}

Write-Host ""
Write-Host "Tua installed successfully!"
Write-Host ""
Write-Host "Installation:"
Write-Host "  $InstallDir"
Write-Host ""

# Verify important files
$Files = @(
    "tua.ps1",
    "tuac.py",
    "tua\__init__.py",
    "tua\cli.py"
)

foreach ($File in $Files) {
    $Path = Join-Path $InstallDir $File

    if (Test-Path $Path) {
        Write-Host "[OK] $File"
    }
    else {
        Write-Host "[MISSING] $File"
    }
}

Write-Host ""
Write-Host "Run:"
Write-Host "  tua"