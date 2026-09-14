[CmdletBinding()]
param([switch]$SkipSkill)
$ErrorActionPreference = 'Stop'
$Venv = Join-Path $PSScriptRoot '.venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $Venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $Venv
    } else { throw 'Install Python 3.10 or later, then run setup.ps1 again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python environment.' }
}
& $Python -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or later is required.' }
& $Python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Python (Join-Path $PSScriptRoot 'pin_reply.py') --check
if ($LASTEXITCODE -ne 0) { throw 'Runtime check failed. Install Microsoft Edge WebView2 Runtime and try again.' }
if (-not $SkipSkill) { & (Join-Path $PSScriptRoot 'install-skill.ps1') }
Write-Output 'Ready. Run .\pin-reply.ps1 to open Codex Notes.'
