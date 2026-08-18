param(
  [switch]$Once,
  [ValidateRange(5, 3600)]
  [int]$PollSeconds = 15,
  [string]$Repository = "yule-one/mer-comment-library"
)

$ErrorActionPreference = "Stop"
$WorkerHome = Join-Path $env:LOCALAPPDATA "MerCommentLibraryWorker"
$WorkerRepo = Join-Path $WorkerHome "repository"
$LogPath = Join-Path $WorkerHome "worker.log"
$SourceRepository = Split-Path -Parent $PSScriptRoot
$PromptRelativePath = ".github\codex\prompts\manual-refresh.md"
$QueueLabel = "mer-local-refresh"
$MutexName = "Local\MerCommentLibraryRefreshWorker"

function Write-WorkerLog([string]$Message) {
  $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  try {
    [IO.File]::AppendAllText($LogPath, "$line`r`n", [Text.UTF8Encoding]::new($false))
  } catch {
    Write-Warning "Worker log write failed: $($_.Exception.Message)"
  }
}

function Invoke-Native([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory = $WorkerHome) {
  Push-Location $WorkingDirectory
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Find-CodexBinary {
  $binRoot = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\bin"
  $candidate = Get-ChildItem -LiteralPath $binRoot -Recurse -Filter codex.exe -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
  if (-not $candidate) {
    throw "Local Codex executable was not found. Install Codex and sign in first."
  }
  return $candidate
}

function Invoke-LocalCodex([string]$CodexPath, [string]$PromptPath, [string]$SelectionPath, [string]$SchemaPath) {
  $stdoutPath = Join-Path $WorkerHome "codex.stdout.log"
  $stderrPath = Join-Path $WorkerHome "codex.stderr.log"
  $arguments = @(
    "exec",
    "-C", "`"$WorkerRepo`"",
    "--sandbox", "read-only",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--output-schema", "`"$SchemaPath`"",
    "--output-last-message", "`"$SelectionPath`"",
    "-"
  )
  $process = Start-Process -FilePath $CodexPath `
    -ArgumentList $arguments `
    -WorkingDirectory $WorkerRepo `
    -WindowStyle Hidden `
    -RedirectStandardInput $PromptPath `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -Wait `
    -PassThru
  if ($process.ExitCode -ne 0) {
    throw "Local Codex failed with exit code $($process.ExitCode). See $stderrPath"
  }
}

function Initialize-WorkerRepository {
  if (-not (Test-Path -LiteralPath (Join-Path $WorkerRepo ".git"))) {
    Invoke-Native "git" @("clone", "https://github.com/$Repository.git", $WorkerRepo)
  }
}

function Reset-WorkerRepository {
  $resolvedHome = [IO.Path]::GetFullPath($WorkerHome).TrimEnd('\') + '\'
  $resolvedRepo = [IO.Path]::GetFullPath($WorkerRepo).TrimEnd('\') + '\'
  if (-not $resolvedRepo.StartsWith($resolvedHome, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Dedicated worker directory validation failed: $resolvedRepo"
  }
  # This is a dedicated disposable clone. Clear only tracked leftovers from a
  # failed job, then fast-forward instead of force-moving the branch ref.
  Invoke-Native "git" @("restore", "--source=HEAD", "--staged", "--worktree", "--", ".") $WorkerRepo
  Invoke-Native "git" @("fetch", "origin", "main") $WorkerRepo
  Invoke-Native "git" @("merge", "--ff-only", "origin/main") $WorkerRepo
}

function Get-QueuedIssue {
  $raw = & gh issue list --repo $Repository --label $QueueLabel --state open --limit 50 --json number,title,author
  if ($LASTEXITCODE -ne 0) { throw "Could not read the GitHub work queue." }
  $issues = @($raw | ConvertFrom-Json)
  foreach ($issue in $issues) {
    if ($issue.author.login -notin @("app/github-actions", "github-actions[bot]")) { continue }
    if ($issue.title -match '^\[mer-local-refresh\] ([0-9]{8,20})$') {
      return [PSCustomObject]@{ Number = [int]$issue.number; LogNo = $Matches[1] }
    }
  }
  return $null
}

function Set-IssueComment([int]$IssueNumber, [string]$Message) {
  & gh issue comment $IssueNumber --repo $Repository --body $Message | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-WorkerLog "Issue #$IssueNumber comment failed." }
}

function Close-QueueIssue([int]$IssueNumber, [string]$Message) {
  & gh issue close $IssueNumber --repo $Repository --comment $Message | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Could not close issue #$IssueNumber." }
}

function Sync-SourceRepository {
  if (-not (Test-Path -LiteralPath (Join-Path $SourceRepository ".git"))) { return }
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    & git -C $SourceRepository pull --ff-only origin main 2>$null | Out-Null
    $pullExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousPreference
  }
  if ($pullExitCode -eq 0) {
    Write-WorkerLog "Main workspace fast-forwarded after publish."
  } else {
    Write-WorkerLog "Main workspace was not fast-forwarded; local edits were preserved."
  }
}

function Process-QueueIssue($Issue, [string]$CodexPath) {
  Write-WorkerLog "Starting issue #$($Issue.Number), logNo $($Issue.LogNo)."
  Set-IssueComment $Issue.Number "The local PC accepted this job and started comment collection and AI curation."
  Reset-WorkerRepository

  Invoke-Native "python" @("scripts/fetch_naver_comments.py", $Issue.LogNo) $WorkerRepo
  $contextPath = Join-Path $WorkerRepo ".manual-refresh-comments.json"
  $context = Get-Content -LiteralPath $contextPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ([int]$context.new_comment_count -eq 0) {
    Close-QueueIssue $Issue.Number "No new public comments were found, so no report or state file was changed."
    Write-WorkerLog "Issue #$($Issue.Number): no new comments."
    return
  }

  $promptPath = Join-Path $WorkerRepo $PromptRelativePath
  $schemaPath = Join-Path $WorkerRepo ".github\codex\schemas\manual-refresh-selection.json"
  $selectionPath = Join-Path $WorkerHome "selection.json"
  Remove-Item -LiteralPath $selectionPath -Force -ErrorAction SilentlyContinue
  Invoke-LocalCodex $CodexPath $promptPath $selectionPath $schemaPath

  Invoke-Native "python" @("scripts/apply_manual_report.py", $selectionPath) $WorkerRepo
  Invoke-Native "python" @("scripts/validate_manual_refresh.py", $Issue.LogNo) $WorkerRepo
  $state = Get-Content -LiteralPath (Join-Path $WorkerRepo ".mer-curation-state.json") -Raw -Encoding UTF8 | ConvertFrom-Json
  $post = $state.posts.PSObject.Properties[$Issue.LogNo].Value
  Invoke-Native "git" @("add", "--", ".mer-curation-state.json", $post.report_md, $post.report_html) $WorkerRepo
  & git -C $WorkerRepo diff --cached --quiet
  $hasChanges = $LASTEXITCODE -ne 0
  if ($hasChanges) {
    Invoke-Native "git" @("config", "user.name", "Mer local refresh worker") $WorkerRepo
    Invoke-Native "git" @("config", "user.email", "yule-one@users.noreply.github.com") $WorkerRepo
    Invoke-Native "git" @("commit", "-m", "Manual Mer comment refresh $($Issue.LogNo)") $WorkerRepo
    Invoke-Native "git" @("push", "origin", "HEAD:main") $WorkerRepo
    Sync-SourceRepository
    Close-QueueIssue $Issue.Number "Local AI curation finished and the reports were published to main. Streamlit will refresh shortly."
  } else {
    Close-QueueIssue $Issue.Number "New comments were checked, but no report-worthy thread was selected. Comment ID state was updated."
  }
  Write-WorkerLog "Completed issue #$($Issue.Number)."
}

New-Item -ItemType Directory -Path $WorkerHome -Force | Out-Null
$mutex = [Threading.Mutex]::new($false, $MutexName)
if (-not $mutex.WaitOne(0)) {
  throw "The local comment refresh worker is already running."
}

try {
  $codex = Find-CodexBinary
  Invoke-Native $codex @("login", "status")
  Invoke-Native "gh" @("auth", "status")
  Initialize-WorkerRepository
  Write-WorkerLog "Worker started. Poll interval: $PollSeconds seconds."
  do {
    $issue = $null
    try {
      $issue = Get-QueuedIssue
      if ($issue) {
        Process-QueueIssue $issue $codex
      }
    } catch {
      Write-WorkerLog "ERROR: $($_.Exception.Message)"
      if ($issue) {
        Set-IssueComment $issue.Number "The local worker encountered an error. Check the PC worker log; the queued job will be retried."
      }
    }
    if (-not $Once) { Start-Sleep -Seconds $PollSeconds }
  } while (-not $Once)
} finally {
  $mutex.ReleaseMutex()
  $mutex.Dispose()
}
