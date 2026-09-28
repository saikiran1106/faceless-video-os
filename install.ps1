<#
Faceless Video OS installer for Windows 10/11 (PowerShell 5.1+).

Installs git, Python 3.12, ffmpeg and Node.js LTS with winget (when missing), then the
faceless CLI in .venv, Playwright + Chromium, faster-whisper, the Remotion composer and
its headless browser, channel.json/.env, and the skills for Claude Code and Codex.

  powershell -ExecutionPolicy Bypass -File install.ps1
  powershell -ExecutionPolicy Bypass -File install.ps1 -Minimal -Demo
  irm https://raw.githubusercontent.com/saikiran1106/faceless-video-os/main/install.ps1 | iex
#>
param(
  [switch]$Minimal,
  [switch]$NoBrowser,
  [switch]$NoLocalAsr,
  [switch]$NoSystem,
  [switch]$RecreateVenv,
  [switch]$Demo,
  [switch]$BrowserLogin,
  [string]$Dir = ""
)
$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/saikiran1106/faceless-video-os.git"
if ($Minimal) { $NoBrowser = $true; $NoLocalAsr = $true }
$Warnings = New-Object System.Collections.Generic.List[string]

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Green }
function Ok($m)   { Write-Host "    [ok] $m" }
function Warn($m) { Write-Host "    [!] $m" -ForegroundColor Yellow; $Warnings.Add($m) }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Winget-Install($id) {
  if ($NoSystem) { throw "Missing $id. Install it, or re-run without -NoSystem." }
  if (-not (Have winget)) { throw "winget is not available. Install '$id' manually (App Installer from the Microsoft Store provides winget)." }
  winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
  Refresh-Path
}
function Is-Repo($p) { (Test-Path "$p\pyproject.toml") -and (Test-Path "$p\faceless") -and (Test-Path "$p\composer") }

Step "Locating the repository"
$Root = $null
if ($PSScriptRoot -and (Is-Repo $PSScriptRoot)) { $Root = $PSScriptRoot }
elseif (Is-Repo (Get-Location).Path) { $Root = (Get-Location).Path }
else {
  if (-not (Have git)) { Winget-Install "Git.Git" }
  $Root = if ($Dir) { $Dir } else { Join-Path (Get-Location).Path "faceless-video-os" }
  if (-not (Is-Repo $Root)) { git clone --depth 1 $RepoUrl $Root }
}
Set-Location $Root
Ok "Repository: $Root"

Step "System tools (git, Python, ffmpeg, Node.js)"
if (-not (Have git)) { Winget-Install "Git.Git" }

function Find-Python {
  foreach ($v in "3.12", "3.11", "3.13", "3.10") {
    if (Have py) {
      $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
  }
  if (Have python) {
    $ok = & python -c "import sys; print(int((3,10) <= sys.version_info[:2] <= (3,13)))" 2>$null
    if ($ok -eq "1") { return (& python -c "import sys; print(sys.executable)").Trim() }
  }
  return $null
}
$Py = Find-Python
if (-not $Py) { Winget-Install "Python.Python.3.12"; $Py = Find-Python }
if (-not $Py) { throw "Python 3.10-3.13 not found. Install Python 3.12 from python.org and re-run." }
Ok "Python: $(& $Py --version)"

if (-not (Have ffmpeg)) { Winget-Install "Gyan.FFmpeg" }
if (-not (Have ffmpeg)) { throw "ffmpeg is still not on PATH. Open a new PowerShell window and re-run." }
Ok "ffmpeg found"

$nodeMajor = 0
if (Have node) { $nodeMajor = [int]((node -v).TrimStart("v").Split(".")[0]) }
if ($nodeMajor -lt 18) { Winget-Install "OpenJS.NodeJS.LTS" }
if (-not (Have npx)) { throw "Node.js/npx not on PATH. Open a new PowerShell window and re-run." }
Ok "Node.js: $(node -v)"

Step "Python environment and the faceless CLI"
$Venv = Join-Path $Root ".venv"
if ($RecreateVenv -and (Test-Path $Venv)) { Remove-Item -Recurse -Force $Venv }
$VPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VPy)) { & $Py -m venv $Venv }
& $VPy -m pip install --quiet --upgrade pip setuptools wheel
& $VPy -m pip install --quiet -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Ok "faceless CLI installed"

if (-not $NoLocalAsr) {
  & $VPy -m pip install --quiet -e ".[local-asr]"
  if ($LASTEXITCODE -eq 0) { Ok "faster-whisper installed (model downloads on first use)" } else { Warn "faster-whisper failed; transcription will need an API key" }
}
if (-not $NoBrowser) {
  Step "Browser automation (Claude Code image host)"
  & $VPy -m pip install --quiet -e ".[browser]"
  if ($LASTEXITCODE -eq 0) {
    & $VPy -m playwright install chromium
    if ($LASTEXITCODE -eq 0) { Ok "Playwright Chromium ready. Sign in once: faceless browser setup" } else { Warn "Chromium download failed; re-run later" }
  } else { Warn "Playwright failed to install; use the codex/api/manual image hosts" }
}

Step "Remotion composer"
Push-Location (Join-Path $Root "composer")
npm ci --no-audit --no-fund --loglevel=error
if ($LASTEXITCODE -ne 0) { npm install --no-audit --no-fund --loglevel=error }
npx --no-install remotion browser ensure | Out-Null
if ($LASTEXITCODE -eq 0) { Ok "Remotion headless browser ready" } else { Warn "Remotion browser will download on first render" }
Pop-Location

Step "Configuration and skills"
$Faceless = Join-Path $Venv "Scripts\faceless.exe"
& $Faceless setup | Out-Null
Ok "channel.json, .env and skills ready"
$scripts = Join-Path $Venv "Scripts"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$scripts*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
  Ok "Added $scripts to your user PATH (open a new terminal)"
}

Step "Verifying"
& $Faceless doctor | Out-Host
if ($Demo) { & $Faceless demo --format short | Out-Host }
if ($BrowserLogin -and -not $NoBrowser) { & $Faceless browser setup }

Write-Host "`nFaceless Video OS is installed." -ForegroundColor Green
if ($Warnings.Count) { Write-Host "Warnings:" -ForegroundColor Yellow; $Warnings | ForEach-Object { Write-Host "  - $_" } }
Write-Host @"

Next
  1. cd $Root
  2. faceless demo            # free offline test video
  3. Edit channel.json and (optionally) .env
  4. Open this folder in Claude Code or Codex and ask for a video.
  Docs: $Root\docs\README.md
"@
