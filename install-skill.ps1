[CmdletBinding()]
param([string]$CodexDirectory)
$ErrorActionPreference = 'Stop'
if (-not $CodexDirectory) {
    $CodexDirectory = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
}
$SkillDir = Join-Path $CodexDirectory 'skills\pin-reply'
if (Test-Path -LiteralPath $SkillDir) {
    $Backup = Join-Path $CodexDirectory ('skill-backups\pin-reply-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Backup) | Out-Null
    Copy-Item -LiteralPath $SkillDir -Destination $Backup -Recurse
    Write-Output "Existing skill backed up to $Backup"
}
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'skill\SKILL.md') -Destination $SkillDir -Force
New-Item -ItemType Directory -Force -Path (Join-Path $SkillDir 'scripts') | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'skill\scripts\pin.ps1') -Destination (Join-Path $SkillDir 'scripts') -Force
$Config = @{ app_path = $PSScriptRoot; schema_version = 1 } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $SkillDir 'config.json'), $Config, [Text.UTF8Encoding]::new($false))
Write-Output 'Installed pin-reply skill. Start a new Codex conversation to use it.'
