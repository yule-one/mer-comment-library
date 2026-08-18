param(
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "scripts\local_refresh_worker.ps1"
if (-not (Test-Path -LiteralPath $ScriptPath)) {
  throw "Local comment worker script was not found: $ScriptPath"
}

if ($Foreground) {
  & $ScriptPath
  exit $LASTEXITCODE
}

$PowerShellExe = (Get-Process -Id $PID).Path
Start-Process -FilePath $PowerShellExe `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$ScriptPath`"") `
  -WorkingDirectory $PSScriptRoot `
  -WindowStyle Hidden

Write-Host "Local comment worker started. It will poll the GitHub queue while this PC is running."
Write-Host "Log: $env:LOCALAPPDATA\MerCommentLibraryWorker\worker.log"
