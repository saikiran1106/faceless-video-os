#!/usr/bin/env bash
# Faceless Video OS installer for macOS and Linux (Windows: install.ps1).
#
# One command installs everything the pipeline needs:
#   system:  git, Python 3.10-3.13, ffmpeg, Node.js 18+, Chromium runtime libraries (Linux)
#   python:  the `faceless` CLI in .venv, Playwright + Chromium (Claude Code image host),
#            faster-whisper (free offline transcription)
#   node:    Remotion composer dependencies + Remotion's headless browser
#   config:  channel.json, .env, projects/, skills mirrored for Claude Code and Codex,
#            `faceless` on your PATH
#
# Safe to re-run: every step checks before it installs.
#
#   ./install.sh                     # from a clone
#   curl -fsSL https://raw.githubusercontent.com/saikiran1106/faceless-video-os/main/install.sh | bash
set -Eeuo pipefail

REPO_URL="https://github.com/saikiran1106/faceless-video-os.git"
REPO_NAME="faceless-video-os"
MIN_NODE_MAJOR=18

# ----------------------------------------------------------------- options --
WITH_BROWSER=1
WITH_LOCAL_ASR=1
WITH_SYSTEM=1
RUN_DEMO=0
BROWSER_LOGIN=0
LINK_CLI=1
ASSUME_YES=0
RECREATE_VENV=0
CLONE_DIR=""

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --minimal         core only: CLI + Remotion (skips the browser image host and local transcription)
  --no-browser      skip Playwright/Chromium (the Claude Code image host)
  --no-local-asr    skip faster-whisper (free offline transcription)
  --no-system       never install system packages; fail with instructions if one is missing
  --recreate-venv   delete and rebuild .venv
  --no-link         don't put `faceless` on your PATH
  --demo            render the free offline demo video at the end
  --browser-login   open the ChatGPT sign-in window at the end (Claude Code image host)
  --dir PATH        where to clone when run outside a checkout (default: ./faceless-video-os)
  -y, --yes         answer yes to every prompt (non-interactive)
  -h, --help        show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --minimal) WITH_BROWSER=0; WITH_LOCAL_ASR=0 ;;
    --no-browser) WITH_BROWSER=0 ;;
    --no-local-asr) WITH_LOCAL_ASR=0 ;;
    --no-system) WITH_SYSTEM=0 ;;
    --recreate-venv) RECREATE_VENV=1 ;;
    --no-link) LINK_CLI=0 ;;
    --demo) RUN_DEMO=1 ;;
    --browser-login) BROWSER_LOGIN=1 ;;
    --dir) CLONE_DIR="${2:?--dir needs a path}"; shift ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

# ------------------------------------------------------------------ output --
if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; DIM=""; RESET=""
fi
CURRENT_STEP="starting"
WARNINGS=()
step() { CURRENT_STEP="$1"; printf '\n%s==>%s %s%s%s\n' "$GREEN" "$RESET" "$BOLD" "$1" "$RESET"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s✔%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '    %s!%s %s\n' "$YELLOW" "$RESET" "$*"; WARNINGS+=("$*"); }
die()  { printf '\n%s✘ %s%s\n' "$RED" "$*" "$RESET" >&2; exit 1; }
trap 'printf "\n%s✘ Install failed during: %s (line %s)%s\n  Re-run ./install.sh once the problem is fixed; finished steps are skipped.\n" "$RED" "$CURRENT_STEP" "$LINENO" "$RESET" >&2' ERR

have() { command -v "$1" >/dev/null 2>&1; }

confirm() {  # confirm "question" -> 0 for yes
  [[ $ASSUME_YES -eq 1 ]] && return 0
  if [[ ! -t 0 ]] && [[ ! -r /dev/tty ]]; then return 0; fi
  local reply
  read -r -p "    $1 [Y/n] " reply </dev/tty || reply="y"
  [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

SUDO=""
if [[ $EUID -ne 0 ]] && have sudo; then SUDO="sudo"; fi

# ---------------------------------------------------------------- platform --
OS="$(uname -s)"
PKG=""
case "$OS" in
  Darwin) PKG="brew" ;;
  Linux)
    if have apt-get; then PKG="apt"
    elif have dnf; then PKG="dnf"
    elif have pacman; then PKG="pacman"
    elif have zypper; then PKG="zypper"
    fi ;;
  *) die "Unsupported OS: $OS. On Windows run install.ps1 in PowerShell." ;;
esac

APT_UPDATED=0
pkg_install() {  # pkg_install <package>...  (names for the detected manager)
  [[ $WITH_SYSTEM -eq 1 ]] || die "Missing system package(s): $*. Install them, or re-run without --no-system."
  case "$PKG" in
    brew) brew install "$@" ;;
    apt)
      if [[ $APT_UPDATED -eq 0 ]]; then $SUDO apt-get update -y; APT_UPDATED=1; fi
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" ;;
    dnf) $SUDO dnf install -y "$@" ;;
    pacman) $SUDO pacman -S --needed --noconfirm "$@" ;;
    zypper) $SUDO zypper --non-interactive install "$@" ;;
    *) die "No supported package manager found. Install manually: $*" ;;
  esac
}

ensure_homebrew() {
  [[ "$OS" == "Darwin" ]] || return 0
  if have brew; then return 0; fi
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$candidate" ]]; then eval "$("$candidate" shellenv)"; return 0; fi
  done
  [[ $WITH_SYSTEM -eq 1 ]] || die "Homebrew is required on macOS to install ffmpeg/Node/Python. See https://brew.sh"
  confirm "Homebrew is not installed. Install it now (it will ask for your password)?" || die "Homebrew is required. See https://brew.sh"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$candidate" ]] && eval "$("$candidate" shellenv)"
  done
  have brew || die "Homebrew installed but not on PATH; open a new terminal and re-run."
}

# -------------------------------------------------------------- 1. the repo --
step "Locating the repository"
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
is_repo() { [[ -f "$1/pyproject.toml" && -d "$1/faceless" && -d "$1/composer" ]]; }
if [[ -n "$SCRIPT_DIR" ]] && is_repo "$SCRIPT_DIR"; then
  ROOT="$SCRIPT_DIR"
elif is_repo "$PWD"; then
  ROOT="$PWD"
else
  ensure_homebrew
  have git || pkg_install git
  ROOT="${CLONE_DIR:-$PWD/$REPO_NAME}"
  if is_repo "$ROOT"; then
    info "Using existing checkout at $ROOT"
  else
    info "Cloning $REPO_URL into $ROOT"
    git clone --depth 1 "$REPO_URL" "$ROOT"
  fi
fi
cd "$ROOT"
ok "Repository: $ROOT"

# ------------------------------------------------------- 2. system packages --
step "System tools (git, Python, ffmpeg, Node.js)"
ensure_homebrew
have git || pkg_install git
have curl || pkg_install curl

python_ok() {  # python_ok <exe> -> 0 when 3.10 <= version <= 3.13
  "$1" -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)' >/dev/null 2>&1
}
find_python() {
  local c
  for c in python3.12 python3.11 python3.13 python3.10 python3; do
    if have "$c" && python_ok "$(command -v "$c")"; then command -v "$c"; return 0; fi
  done
  return 1
}
PY="$(find_python || true)"
if [[ -z "$PY" ]]; then
  info "No Python 3.10-3.13 found (3.14+ lacks wheels for some dependencies); installing Python 3.12"
  case "$PKG" in
    brew) pkg_install python@3.12 ;;
    apt) pkg_install python3 python3-venv python3-pip ;;
    dnf) pkg_install python3.12 || pkg_install python3 ;;
    pacman) pkg_install python ;;
    zypper) pkg_install python312 || pkg_install python3 ;;
  esac
  hash -r
  PY="$(find_python || true)"
  [[ -n "$PY" ]] || die "Could not find Python 3.10-3.13 after installing. Install Python 3.12 from python.org and re-run."
fi
if [[ "$PKG" == "apt" ]] && ! "$PY" -c "import ensurepip, venv" >/dev/null 2>&1; then
  pkg_install "python3-venv" "python$("$PY" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')-venv" || true
fi
ok "Python: $("$PY" --version) ($PY)"

if ! have ffmpeg || ! have ffprobe; then
  case "$PKG" in
    dnf) pkg_install ffmpeg || pkg_install ffmpeg-free ;;
    *) pkg_install ffmpeg ;;
  esac
fi
ok "ffmpeg: $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

node_major() { node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || echo 0; }
load_nvm() { export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"; [[ -s "$NVM_DIR/nvm.sh" ]] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 || true; }
load_nvm
if ! have node || [[ "$(node_major)" -lt $MIN_NODE_MAJOR ]]; then
  case "$PKG" in
    brew) pkg_install node ;;
    pacman) pkg_install nodejs npm ;;
    *) : ;;  # distro Node is often too old; use nvm below
  esac
  hash -r
  if ! have node || [[ "$(node_major)" -lt $MIN_NODE_MAJOR ]]; then
    info "Installing Node.js LTS with nvm (user-level, no sudo)"
    if [[ ! -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | PROFILE=/dev/null bash
    fi
    load_nvm
    nvm install --lts >/dev/null
    nvm alias default 'lts/*' >/dev/null
    warn "Node was installed with nvm. New terminals need nvm loaded (the nvm installer adds it to your shell profile)."
  fi
fi
have npx || die "npx not found after installing Node.js"
ok "Node.js: $(node -v)"

if [[ "$OS" == "Linux" && $WITH_SYSTEM -eq 1 ]]; then
  step "Chromium runtime libraries (needed by Remotion and Playwright on Linux)"
  case "$PKG" in
    apt)
      pkg_install libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libgbm1 libxrandr2 libxkbcommon0 \
        libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 libcups2 fonts-noto-core fonts-noto-color-emoji
      pkg_install libasound2t64 2>/dev/null || pkg_install libasound2 ;;
    dnf) pkg_install nss atk at-spi2-atk cups-libs libdrm libxkbcommon libXcomposite libXdamage libXrandr mesa-libgbm pango alsa-lib google-noto-sans-fonts ;;
    pacman) pkg_install nss atk at-spi2-core libcups libdrm libxkbcommon libxcomposite libxdamage libxrandr mesa pango alsa-lib noto-fonts ;;
    zypper) pkg_install mozilla-nss libatk-1_0-0 libgbm1 libxkbcommon0 libXcomposite1 libXdamage1 libXrandr2 pango alsa ;;
  esac
  ok "Runtime libraries present"
fi

# ------------------------------------------------------------ 3. python env --
step "Python environment and the faceless CLI"
VENV="$ROOT/.venv"
if [[ -d "$VENV" && $RECREATE_VENV -eq 1 ]]; then rm -rf "$VENV"; fi
if [[ -x "$VENV/bin/python" ]] && ! python_ok "$VENV/bin/python"; then
  info "Existing .venv uses $("$VENV/bin/python" --version); rebuilding it with $("$PY" --version)"
  rm -rf "$VENV"
fi
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
"$VPY" -m pip install --quiet --upgrade pip setuptools wheel
"$VPY" -m pip install --quiet -e ".[dev]"
ok "faceless CLI installed ($("$VPY" --version))"

if [[ $WITH_LOCAL_ASR -eq 1 ]]; then
  if "$VPY" -m pip install --quiet -e ".[local-asr]"; then
    ok "Free offline transcription (faster-whisper) installed; its model downloads on first use"
  else
    warn "faster-whisper failed to install; transcription will need an ElevenLabs or OpenAI key"
  fi
fi

if [[ $WITH_BROWSER -eq 1 ]]; then
  step "Browser automation (Claude Code image host: ChatGPT via Playwright)"
  if "$VPY" -m pip install --quiet -e ".[browser]"; then
    if [[ "$OS" == "Linux" && $WITH_SYSTEM -eq 1 ]]; then
      $SUDO "$VPY" -m playwright install-deps chromium || warn "playwright install-deps failed; Chromium may miss system libraries"
    fi
    if "$VPY" -m playwright install chromium; then
      ok "Playwright Chromium ready. Sign in once with: faceless browser setup"
    else
      warn "Playwright Chromium download failed; re-run ./install.sh later"
    fi
  else
    warn "Playwright failed to install; the claude-code image host is unavailable (codex/api/manual still work)"
  fi
fi

# ---------------------------------------------------------------- 4. remotion --
step "Remotion composer"
pushd "$ROOT/composer" >/dev/null
if [[ -f package-lock.json ]]; then
  npm ci --no-audit --no-fund --loglevel=error || npm install --no-audit --no-fund --loglevel=error
else
  npm install --no-audit --no-fund --loglevel=error
fi
ok "Node dependencies installed"
if npx --no-install remotion browser ensure >/dev/null 2>&1; then
  ok "Remotion headless browser ready"
else
  warn "Could not pre-download Remotion's browser; it will download on the first render"
fi
if npx --no-install tsc --noEmit; then ok "Composer type-checks"; else warn "Composer type-check failed"; fi
popd >/dev/null

# ------------------------------------------------------------- 5. configure --
step "Configuration and skills"
"$VENV/bin/faceless" setup >/dev/null
[[ -f channel.json ]] && ok "channel.json (edit your channel name, voice, colours, CTAs)"
[[ -f .env ]] && ok ".env (add ELEVENLABS_API_KEY / OPENAI_API_KEY if you have them; both optional)"
ok "Skills synced to .claude/skills (Claude Code) and .agents/skills (Codex)"

if [[ $LINK_CLI -eq 1 ]]; then
  BIN_DIR="$HOME/.local/bin"
  mkdir -p "$BIN_DIR"
  ln -sf "$VENV/bin/faceless" "$BIN_DIR/faceless"
  ok "Linked $BIN_DIR/faceless"
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
      RC="$HOME/.bashrc"; [[ "${SHELL:-}" == */zsh ]] && RC="$HOME/.zshrc"
      if grep -qs 'faceless-video-os PATH' "$RC"; then
        info "$BIN_DIR is added to PATH by $RC (open a new terminal)"
      elif confirm "Add $BIN_DIR to your PATH in $RC?"; then
        printf '\n# faceless-video-os PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RC"
        ok "Added to $RC (open a new terminal, or: source $RC)"
      else
        warn "Add $BIN_DIR to PATH yourself, or run $VENV/bin/faceless"
      fi ;;
  esac
fi

# ---------------------------------------------------------------- 6. verify --
step "Verifying"
DOCTOR_OUT="$(mktemp -t faceless-doctor.XXXXXX)"
if "$VENV/bin/faceless" doctor >"$DOCTOR_OUT" 2>&1; then
  ok "faceless doctor passed"
else
  warn "faceless doctor reported problems; run: faceless doctor"
fi
"$VPY" - "$DOCTOR_OUT" <<'PY' || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for name, items in d.get("capabilities", {}).items():
    print(f"    {name:<14} {', '.join(items)}")
for c in d.get("checks", []):
    print(f"    ! {c['check']}: {c.get('fix', c['detail'])}")
PY
rm -f "$DOCTOR_OUT"

if [[ $RUN_DEMO -eq 1 ]]; then
  step "Rendering the offline demo"
  "$VENV/bin/faceless" demo --format short >/dev/null && ok "Demo: $ROOT/projects/demo-short/08-compose/renders/demo-short_youtube.mp4"
fi

if [[ $BROWSER_LOGIN -eq 1 && $WITH_BROWSER -eq 1 ]]; then
  step "ChatGPT sign-in for the Claude Code image host"
  info "A browser window will open. Sign in to ChatGPT yourself (including any MFA), then close it."
  "$VENV/bin/faceless" browser setup || warn "Sign-in did not complete; run: faceless browser setup"
fi

trap - ERR
printf '\n%s%sFaceless Video OS is installed.%s\n' "$BOLD" "$GREEN" "$RESET"
if [[ ${#WARNINGS[@]} -gt 0 ]]; then
  printf '%sWarnings:%s\n' "$YELLOW" "$RESET"
  for w in "${WARNINGS[@]}"; do printf '  - %s\n' "$w"; done
fi
cat <<EOF

${BOLD}Next${RESET}
  1. cd $ROOT
  2. faceless demo                 ${DIM}# free offline test video, no keys${RESET}
  3. Edit channel.json and (optionally) .env
  4. Open this folder in Claude Code or Codex and say:
       "Make a 60-second Short about <topic>"   or
       "Here is my voiceover: <path>. Turn it into a video."
  Claude Code image host: faceless browser setup   ${DIM}# one-time ChatGPT sign-in${RESET}
  Docs: $ROOT/docs/README.md
EOF
