param(
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "scripts\local_refresh_worker.ps1"
if (-not (Test-Path -LiteralPath $ScriptPath)) {
  throw "로컬 댓글 실행기 스크립트를 찾지 못했습니다: $ScriptPath"
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

Write-Host "로컬 댓글 실행기를 시작했습니다. PC가 켜져 있는 동안 GitHub 작업 큐를 확인합니다."
Write-Host "로그: $env:LOCALAPPDATA\MerCommentLibraryWorker\worker.log"
