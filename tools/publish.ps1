<#
.SYNOPSIS
    Verify, commit and publish this repository to GitHub.

.DESCRIPTION
    Runs the four checks that constitute the project's own quality gate, and
    refuses to publish if any of them fails.  Then creates the first commit
    and (if the GitHub CLI is available and authenticated) the remote
    repository.

    Requires git.  The GitHub CLI is optional -- without it the script stops
    after committing and prints the two remaining commands.

.EXAMPLE
    .\tools\publish.ps1 -RepoName gpower-rea -Public

.EXAMPLE
    .\tools\publish.ps1 -RepoName gpower-rea -Private -SkipChecks
#>
[CmdletBinding()]
param(
    [string]$RepoName = "gpower-rea",
    [switch]$Public,
    [switch]$Private,
    [switch]$SkipChecks,
    [string]$UserName,
    [string]$UserEmail
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Fail($message) {
    Write-Host ""
    Write-Host "PUBLISH ABORTED: $message" -ForegroundColor Red
    exit 1
}

function Step($label) {
    Write-Host ""
    Write-Host "== $label" -ForegroundColor Cyan
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "git is not on PATH. Install it with:  winget install --id Git.Git  then reopen the terminal."
}

# ---------------------------------------------------------------- the gate
if (-not $SkipChecks) {
    Step "submission rules (tools/compliance_check.py)"
    python tools/compliance_check.py
    if ($LASTEXITCODE -ne 0) { Fail "compliance check failed" }

    Step "reference vectors are not stale"
    python tools/make_vectors.py --check
    if ($LASTEXITCODE -ne 0) { Fail "public_vectors.csv is stale -- run: python tools/make_vectors.py" }

    Step "test suite"
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { Fail "tests failed" }

    Step "conformance gate"
    gpower selftest
    if ($LASTEXITCODE -ne 0) { Fail "gpower selftest failed" }
} else {
    Write-Host "-SkipChecks given: publishing without running the gate." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- git
Step "git repository"
if (-not (Test-Path ".git")) {
    git init -b main | Out-Null
    Write-Host "initialised a new repository on branch 'main'"
} else {
    Write-Host "using the existing repository"
}

if ($UserName)  { git config user.name  $UserName }
if ($UserEmail) { git config user.email $UserEmail }

$haveName = (git config user.name)  2>$null
$haveMail = (git config user.email) 2>$null
if (-not $haveName -or -not $haveMail) {
    Fail "git identity is not set. Re-run with -UserName 'Your Name' -UserEmail 'you@example.com'"
}

git add -A

# Belt and braces: never let a forbidden artefact reach a commit, even if
# .gitignore were edited.
$staged = git diff --cached --name-only
$forbidden = $staged | Where-Object {
    $_ -match '\.(exe|dll|dylib|so|msi|dmg|pkg|asm|lst|dis|idb|i64|ida|bpl|dcu|obj)$'
}
if ($forbidden) {
    Fail "refusing to commit forbidden artefact(s):`n  $($forbidden -join "`n  ")"
}

$count = ($staged | Measure-Object -Line).Lines
Write-Host "$count file(s) staged"

$message = @'
gpower-rea: clean-room engine, CLI, MCP server and agent for the G*Power t-test family

Behavioural reverse engineering of the G*Power 3.1 "t tests" family (all six
statistical tests, all five analysis types):

  * SPEC.md -- 12 findings, each labelled by how strongly it is established
    (derived / behavioural / open), each with an evidence file in docs/EVIDENCE
  * 36-row probe worksheet built around competing pre-registered predictions
  * clean-room engine, zero runtime dependencies, written from SPEC.md
  * CLI (solve / batch / curve / effect-size / selftest), MCP server (6 tools),
    natural-language agent -- all thin layers over one engine, CI-enforced
  * 401/401 exact sample-size agreement; independently re-derived with SciPy
    and a brute-force search; numerical accuracy arbitrated against mpmath
'@

if ((git rev-list --all --count) -eq 0) {
    git commit -q -m $message
    Write-Host "created the initial commit"
} else {
    git commit -q -m "Update project" 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "created a follow-up commit" }
    else { Write-Host "nothing new to commit" }
}

# ---------------------------------------------------------------- GitHub
Step "GitHub"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "The GitHub CLI is not installed, so the remote was not created." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Create an EMPTY repository named '$RepoName' on github.com, then run:"
    Write-Host "  git remote add origin https://github.com/<your-user>/$RepoName.git"
    Write-Host "  git push -u origin main"
    exit 0
}

gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "gh is installed but not authenticated. Run 'gh auth login', then re-run this script." -ForegroundColor Yellow
    exit 0
}

$visibility = if ($Private) { "--private" } else { "--public" }
if (-not $Public -and -not $Private) {
    Write-Host "neither -Public nor -Private given; defaulting to --public"
}

$existing = git remote get-url origin 2>$null
if ($existing) {
    Write-Host "origin already set to $existing -- pushing"
    git push -u origin main
} else {
    gh repo create $RepoName $visibility --source=. --remote=origin --push `
        --description "Clean-room engine, CLI, MCP server and AI agent for the G*Power t-test family"
}

Step "done"
$url = git remote get-url origin 2>$null
if ($url) {
    $url = $url -replace '\.git$', ''
    Write-Host "Repository: $url"
    Write-Host "Actions:    $url/actions"
    Write-Host ""
    Write-Host "Submit that link. See PUBLISH.md for the two remaining"
    Write-Host "attestations (GUI probes, two-session sign-off)."
}
