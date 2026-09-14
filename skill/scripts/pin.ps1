[CmdletBinding()]
param([string]$File, [string]$Text, [string]$TextBase64, [string]$Title = 'Pinned reply', [string]$Source = 'current Codex task')
$ErrorActionPreference = 'Stop'
$ConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'config.json'
if (-not (Test-Path -LiteralPath $ConfigPath)) { throw 'Run install-skill.ps1 from the Codex Notes folder first.' }
$Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Launcher = Join-Path $Config.app_path 'pin-reply.ps1'
if (-not (Test-Path -LiteralPath $Launcher)) { throw 'Codex Notes moved or was removed. Run install-skill.ps1 from its new folder.' }
& $Launcher @PSBoundParameters
