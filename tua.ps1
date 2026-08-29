#!/usr/bin/env pwsh
# for windows

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EntryPoint = Join-Path $ScriptDir "tuac.py"

$PythonBin = $null
foreach ($candidate in @("python3", "python", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $PythonBin = $candidate
        break
    }
}

if (-not $PythonBin) {
    Write-Error "tua: couldn't find python3 (or python/py) on your PATH. tua needs a Python 3 interpreter to run its compiler."
    exit 1
}

if ($PythonBin -eq "py") {
    & py -3 $EntryPoint @args
} else {
    & $PythonBin $EntryPoint @args
}

exit $LASTEXITCODE
