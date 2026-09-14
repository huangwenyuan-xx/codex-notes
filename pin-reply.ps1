[CmdletBinding()]
param(
    [string]$Text,
    [string]$TextBase64,
    [string]$File,
    [string]$Title = 'Pinned reply',
    [string]$Source = 'current Codex task',
    [ValidateRange(480, 10000)][int]$Width = 800,
    [ValidateRange(380, 10000)][int]$Height = 620
)
$ErrorActionPreference = 'Stop'
$ToolDir = $PSScriptRoot
$Python = Join-Path $ToolDir '.venv\Scripts\python.exe'
$PythonWindow = Join-Path $ToolDir '.venv\Scripts\pythonw.exe'
$Script = Join-Path $ToolDir 'pin_reply.py'
if (-not (Test-Path -LiteralPath $PythonWindow)) {
    throw 'Run setup.ps1 first to install Codex Notes.'
}
$InputCount = @('Text', 'TextBase64', 'File' | Where-Object { $PSBoundParameters.ContainsKey($_) }).Count
if ($InputCount -gt 1) { throw 'Use only one of -Text, -TextBase64, or -File.' }
$Content = ''
if ($PSBoundParameters.ContainsKey('File')) {
    $Content = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $File).Path, [Text.Encoding]::UTF8)
} elseif ($PSBoundParameters.ContainsKey('TextBase64')) {
    $Content = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextBase64))
} elseif ($PSBoundParameters.ContainsKey('Text')) {
    $Content = $Text
}
$RequestPath = Join-Path ([IO.Path]::GetTempPath()) ('codex-notes-' + [guid]::NewGuid().ToString('N') + '.json')
$Request = @{ id = [guid]::NewGuid().ToString('N'); text = $Content; title = $Title; source = $Source; width = $Width; height = $Height }
[IO.File]::WriteAllText($RequestPath, ($Request | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
$Started = $false
try {
    & $Python $Script --send --request $RequestPath
    if ($LASTEXITCODE -eq 0) {
        Write-Output 'Codex Notes received the request.'
        return
    }
    # Only paths enter the command line. Reply text and metadata stay in UTF-8 JSON.
    $Arguments = @(
        ('"' + $Script + '"')
        '--request'
        ('"' + $RequestPath + '"')
        '--consume-request'
    )
    $Process = Start-Process -FilePath $PythonWindow -ArgumentList $Arguments -WindowStyle Normal -PassThru
    $Started = $true
    for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
        if ($Process.HasExited -and $Process.ExitCode -ne 0) { throw 'Codex Notes failed to start. See startup-error.log in the notebook data folder.' }
        & $Python $Script --send
        if ($LASTEXITCODE -eq 0) { Write-Output 'Codex Notes is open.'; return }
    }
    throw 'Codex Notes did not become ready. See startup-error.log in the notebook data folder.'
} finally {
    if (-not $Started -and (Test-Path -LiteralPath $RequestPath)) { Remove-Item -LiteralPath $RequestPath }
}
