#!/bin/sh
# Volcengine Agent Toolkit installer: GitHub first, CDN when GitHub is unreachable.
#
# When GitHub answers, the hosts install straight from the repository, exactly
# as the README describes. When it does not, this script downloads the toolkit
# package published on the Volcengine CDN, verifies its SHA-256 against the
# release manifest, unpacks it to a persistent local directory, and installs
# from that directory instead.
#
#   curl -fsSL https://cloudcache.volccdn.com/ve/skills/install.sh | sh
#   curl -fsSL https://cloudcache.volccdn.com/ve/skills/install.sh | sh -s -- --agent claude
#
# Runs on macOS, Linux, WSL and Git Bash with a POSIX sh. On Windows
# PowerShell use install.ps1 from the same location; both take the same
# options and print the same result lines.
#
# Options:
#   --agent <name>[,<name>]  Also install the core skills for these hosts.
#                            claude and codex get the core plugin from the
#                            marketplace, and so does trae-cli (Trae CLI);
#                            gemini uses `gemini skills install`; doubao-work
#                            copies the core skills into the DoubaoWork user
#                            skill directory; any other name (cursor, opencode,
#                            trae, trae-cn, ...) is passed to
#                            `npx skills add --agent`. Without --agent the
#                            script only prints the commands to run.
#   --source <auto|github|cdn>
#                            auto (default) probes GitHub; github and cdn skip
#                            the probe.
#   --dir <dir>              Local toolkit directory for the CDN path.
#   --version <ver>          Download this version instead of the CDN "latest".
#   --dry-run                Print the resolved SOURCE/VERSION/TOOLKIT_URL/TOOLKIT_DIR
#                            and exit without changing anything.
#
# Environment:
#   VOLCENGINE_TOOLKIT_BASE_URL    Base URL of the release files
#                                  (default https://cloudcache.volccdn.com/ve/skills).
#                                  A value without a scheme is read as a local
#                                  directory, which is how the tests run offline.
#   VOLCENGINE_TOOLKIT_DIR         Same as --dir (default ~/.volcengine/agent-toolkit).
#   VOLCENGINE_TOOLKIT_GITHUB_URL  URL probed to decide whether GitHub is reachable.
#
# Layout expected under the base URL:
#   latest/toolkit-manifest.json   -> {"version", "toolkit": {"url", "sha256", ...}}
#   v<ver>/toolkit-manifest.json
#   v<ver>/volcengine-agent-toolkit.zip
#
# The local directory must persist: Claude Code loads the plugin in place from
# it, and Codex keeps it as the marketplace root. Rerun this script to upgrade.

set -eu

DEFAULT_BASE_URL="https://cloudcache.volccdn.com/ve/skills"
DEFAULT_GITHUB_URL="https://github.com/volcengine/volcengine-agent-toolkit"
GITHUB_REPOSITORY="volcengine/volcengine-agent-toolkit"
MARKETPLACE="volcengine-skills"
CORE_PLUGIN="volcengine-core@volcengine-skills"
CORE_SKILLS="volcengine-cli volcengine-troubleshooting volcengine-knowledge-search volcengine-find-skills volcengine-feedback volcengine-billing-and-cost-management"
MANIFEST_NAME="toolkit-manifest.json"
ARCHIVE_NAME="volcengine-agent-toolkit.zip"

base_url="${VOLCENGINE_TOOLKIT_BASE_URL:-$DEFAULT_BASE_URL}"
github_url="${VOLCENGINE_TOOLKIT_GITHUB_URL:-$DEFAULT_GITHUB_URL}"
toolkit_dir="${VOLCENGINE_TOOLKIT_DIR:-}"
agent=""
source_mode="auto"
version=""
dry_run=0
tmp_dir=""
staging_dir=""
verified=""

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
  cat >&2 <<'USAGE'
Usage: install_toolkit.sh [--agent <name>[,<name>]] [--source <auto|github|cdn>]
                          [--dir <dir>] [--version <ver>] [--dry-run]

  --agent <names>    Install the core skills for these hosts, comma separated:
                     claude, codex, trae-cli (core plugin), gemini (gemini skills
                     install), doubao-work (DoubaoWork user skills), or any agent
                     name the skills CLI accepts (cursor, opencode, trae, trae-cn, ...)
  --source <mode>    auto probes GitHub (default); github or cdn skips the probe
  --dir <dir>        Local toolkit directory for the CDN path (env VOLCENGINE_TOOLKIT_DIR,
                     default ~/.volcengine/agent-toolkit)
  --version <ver>    Download this version instead of the CDN "latest"
  --dry-run          Print SOURCE/VERSION/TOOLKIT_URL/TOOLKIT_DIR and exit

Env: VOLCENGINE_TOOLKIT_BASE_URL (default https://cloudcache.volccdn.com/ve/skills),
     VOLCENGINE_TOOLKIT_GITHUB_URL (URL probed for GitHub reachability).
USAGE
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --agent)
      [ $# -ge 2 ] || die "--agent needs a value"
      agent="$2"; shift 2 ;;
    --agent=*) agent="${1#--agent=}"; shift ;;
    --source)
      [ $# -ge 2 ] || die "--source needs a value"
      source_mode="$2"; shift 2 ;;
    --source=*) source_mode="${1#--source=}"; shift ;;
    --dir)
      [ $# -ge 2 ] || die "--dir needs a value"
      toolkit_dir="$2"; shift 2 ;;
    --dir=*) toolkit_dir="${1#--dir=}"; shift ;;
    --version)
      [ $# -ge 2 ] || die "--version needs a value"
      version="$2"; shift 2 ;;
    --version=*) version="${1#--version=}"; shift ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage 0 ;;
    *) log "Unknown option: $1"; usage 2 ;;
  esac
done

case "$agent" in
  *[!A-Za-z0-9,_-]*) die "Invalid --agent '$agent' (expected names such as claude,codex)" ;;
esac
case "$source_mode" in
  auto|github|cdn) : ;;
  *) die "Unsupported --source '$source_mode' (expected auto, github, or cdn)" ;;
esac

# Strip trailing slashes so "$base_url/latest" never doubles a slash.
base_url="$(printf '%s' "$base_url" | sed 's:/*$::')"
[ -n "$base_url" ] || die "VOLCENGINE_TOOLKIT_BASE_URL is empty"
if [ -z "$toolkit_dir" ]; then
  toolkit_dir="${HOME:?HOME is not set}/.volcengine/agent-toolkit"
fi
toolkit_dir="$(printf '%s' "$toolkit_dir" | sed 's:/*$::')"
[ -n "$toolkit_dir" ] || die "The toolkit directory cannot be the filesystem root"

cleanup() {
  if [ -n "$tmp_dir" ] && [ -d "$tmp_dir" ]; then
    rm -rf "$tmp_dir"
  fi
  if [ -n "$staging_dir" ] && [ -d "$staging_dir" ]; then
    rm -rf "$staging_dir"
  fi
}
trap cleanup EXIT INT TERM HUP

# ---------------------------------------------------------------------------
# Transport: HTTP(S) via curl or wget; a local directory when the base URL has
# no scheme. Downloads are bounded so a stalled connection fails instead of
# hanging.
# ---------------------------------------------------------------------------
is_local_base() {
  case "$base_url" in
    *://*) return 1 ;;
    *) return 0 ;;
  esac
}

fetch_to_file() {
  # $1 = URL or local path, $2 = destination file
  if is_local_base; then
    [ -f "$1" ] || return 1
    cp "$1" "$2"
  elif have curl; then
    curl -fsSL --retry 2 --connect-timeout 10 --max-time 300 -o "$2" "$1"
  elif have wget; then
    wget -q --timeout=30 --tries=3 -O "$2" "$1"
  else
    die "need curl or wget to download $1"
  fi
}

# GitHub often stalls rather than refuses, so the probe is short and bounded.
github_reachable() {
  if have curl; then
    curl -fsS -o /dev/null --connect-timeout 5 --max-time 10 -I "$github_url" 2>/dev/null
  elif have wget; then
    wget -q --timeout=10 --tries=1 --spider "$github_url" 2>/dev/null
  else
    return 1
  fi
}

normalize_version() {
  v="$(printf '%s' "$1" | tr -d '[:space:]')"
  v="${v#v}"
  case "$v" in
    [0-9]*.[0-9]*.[0-9]*) printf '%s' "$v" ;;
    *) return 1 ;;
  esac
}

# Read one string field from a manifest. The release manifests are written one
# key per line, and each of these keys appears once.
json_string() {
  # $1 = file, $2 = key
  sed -n 's/^[[:space:]]*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*$/\1/p' "$1" | sed -n '1p'
}

sha256_file() {
  if have sha256sum; then
    sha256sum "$1" | awk '{print $1}'
  elif have shasum; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif have openssl; then
    openssl dgst -sha256 "$1" | awk '{print $NF}'
  else
    die "need sha256sum, shasum, or openssl to verify the download"
  fi
}

extract_archive() {
  # $1 = zip path, $2 = destination dir. The Python fallback restores the
  # executable bits that unzip applies on its own.
  if have unzip; then
    unzip -o -q "$1" -d "$2"
  elif have python3; then
    python3 - "$1" "$2" <<'PY'
import os
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    for info in archive.infolist():
        path = archive.extract(info, sys.argv[2])
        mode = (info.external_attr >> 16) & 0o777
        if mode and not info.is_dir():
            os.chmod(path, mode)
PY
  else
    die "need unzip or python3 to extract $1"
  fi
}

is_toolkit_dir() {
  [ -f "$1/.claude-plugin/marketplace.json" ] && [ -d "$1/plugins/volcengine-core/skills" ]
}

# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------
# DoubaoWork is installed by copying from the local toolkit directory, so it
# always needs the CDN package, whether or not GitHub answers.
case ",$agent," in
  *,doubao-work,*|*,doubaowork,*)
    [ "$source_mode" != "auto" ] || source_mode="cdn" ;;
esac

if [ "$source_mode" = "auto" ]; then
  if github_reachable; then
    source_mode="github"
  else
    log "GitHub is not reachable from this host; using the Volcengine CDN."
    source_mode="cdn"
  fi
fi

install_source="$GITHUB_REPOSITORY"
toolkit_version=""
toolkit_url=""

if [ "$source_mode" = "cdn" ]; then
  if [ -n "$version" ]; then
    wanted="$(normalize_version "$version")" || die "Invalid version '$version' (expected e.g. 1.3.4)"
    manifest_url="$base_url/v$wanted/$MANIFEST_NAME"
  else
    manifest_url="$base_url/latest/$MANIFEST_NAME"
  fi

  tmp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t volcengine-toolkit)"
  manifest_path="$tmp_dir/$MANIFEST_NAME"
  fetch_to_file "$manifest_url" "$manifest_path" \
    || die "Cannot read $manifest_url. Check the network, or pass --version <ver>."

  manifest_version="$(json_string "$manifest_path" version)"
  toolkit_version="$(normalize_version "$manifest_version")" \
    || die "Unexpected version in $manifest_url: '$manifest_version'"
  toolkit_url="$(json_string "$manifest_path" url)"
  expected="$(json_string "$manifest_path" sha256 | tr 'A-F' 'a-f')"
  [ -n "$toolkit_url" ] || die "No toolkit url in $manifest_url"
  case "$expected" in
    *[!0-9a-f]*|"") die "No usable sha256 in $manifest_url. Refusing to install an unverified package." ;;
  esac
  [ "${#expected}" -eq 64 ] || die "No usable sha256 in $manifest_url. Refusing to install an unverified package."
  # A manifest built without --cdn-base-url names the archive relative to itself.
  case "$toolkit_url" in
    *://*|/*) : ;;
    *) toolkit_url="$base_url/v$toolkit_version/$toolkit_url" ;;
  esac
  install_source="$toolkit_dir"
fi

if [ "$dry_run" -eq 1 ]; then
  printf 'SOURCE=%s\n' "$source_mode"
  printf 'VERSION=%s\n' "$toolkit_version"
  printf 'TOOLKIT_URL=%s\n' "$toolkit_url"
  printf 'TOOLKIT_DIR=%s\n' "$toolkit_dir"
  printf 'INSTALL_SOURCE=%s\n' "$install_source"
  exit 0
fi

# ---------------------------------------------------------------------------
# CDN path: download, verify, unpack next to the target, then swap.
# ---------------------------------------------------------------------------
if [ "$source_mode" = "cdn" ]; then
  installed_version=""
  if is_toolkit_dir "$toolkit_dir" && [ -f "$toolkit_dir/package.json" ]; then
    installed_version="$(json_string "$toolkit_dir/package.json" version)"
  fi

  if [ "$installed_version" = "$toolkit_version" ]; then
    log "Volcengine Agent Toolkit v$toolkit_version is already in $toolkit_dir."
  else
    if [ -e "$toolkit_dir" ] && ! is_toolkit_dir "$toolkit_dir"; then
      # Never replace a directory this installer did not create.
      if [ ! -d "$toolkit_dir" ] || [ -n "$(ls -A "$toolkit_dir" 2>/dev/null)" ]; then
        die "$toolkit_dir exists and is not a Volcengine toolkit directory. Pass --dir <dir> to use another location."
      fi
    fi

    archive_path="$tmp_dir/$ARCHIVE_NAME"
    log "Downloading Volcengine Agent Toolkit v$toolkit_version ..."
    fetch_to_file "$toolkit_url" "$archive_path" || die "Download failed: $toolkit_url"
    actual="$(sha256_file "$archive_path")"
    if [ "$expected" != "$actual" ]; then
      die "Checksum mismatch for $ARCHIVE_NAME: expected $expected, got $actual. The download may have been tampered with."
    fi
    log "Checksum OK."

    parent_dir="$(dirname "$toolkit_dir")"
    mkdir -p "$parent_dir" || die "Cannot create $parent_dir (pass --dir <dir> for a writable location)"
    # Unpack beside the target so the final step is a rename on one filesystem.
    # A broken download must never replace a working toolkit.
    staging_dir="$toolkit_dir.install.$$"
    rm -rf "$staging_dir"
    mkdir -p "$staging_dir"
    extract_archive "$archive_path" "$staging_dir"
    is_toolkit_dir "$staging_dir" || die "$ARCHIVE_NAME does not contain the expected toolkit layout. Existing install left untouched."

    previous_dir=""
    if [ -e "$toolkit_dir" ]; then
      previous_dir="$toolkit_dir.previous.$$"
      rm -rf "$previous_dir"
      mv "$toolkit_dir" "$previous_dir"
    fi
    if ! mv "$staging_dir" "$toolkit_dir"; then
      [ -z "$previous_dir" ] || mv "$previous_dir" "$toolkit_dir"
      die "Cannot move the toolkit into $toolkit_dir. Existing install left untouched."
    fi
    staging_dir=""
    [ -z "$previous_dir" ] || rm -rf "$previous_dir"
    log "Volcengine Agent Toolkit v$toolkit_version unpacked to $toolkit_dir"
  fi
fi

# ---------------------------------------------------------------------------
# Host registration
# ---------------------------------------------------------------------------
# Each host is asked afterwards whether it can see what was installed, so the
# caller gets a verified result from this one command.
record_verified() {
  # $1 = agent name, $2 = ok or the reason it failed
  verified="${verified:+$verified,}$1:$2"
}

# Succeeds when every core skill name appears in the text on stdin.
lists_core_skills() {
  listing="$(cat)"
  for skill in $CORE_SKILLS; do
    case "$listing" in
      *"$skill"*) : ;;
      *) return 1 ;;
    esac
  done
}

install_for_claude() {
  have claude || die "'claude' is not on PATH. Install Claude Code, then rerun with --agent claude."
  # Adding an already known marketplace repoints it at this source.
  claude plugin marketplace add "$install_source" >&2 \
    || die "claude plugin marketplace add failed for $install_source"
  claude plugin install "$CORE_PLUGIN" >&2 \
    || die "claude plugin install $CORE_PLUGIN failed"
  if claude plugin list 2>/dev/null | grep -q "$CORE_PLUGIN"; then
    record_verified claude ok
  else
    record_verified claude plugin-not-listed
  fi
  log "Claude Code: $CORE_PLUGIN installed. Run /reload-plugins in an open session, or start a new one."
}

install_for_codex() {
  have codex || die "'codex' is not on PATH. Install Codex, then rerun with --agent codex."
  # Codex refuses to add a marketplace name that is bound to another source, so
  # drop the old binding and add this one.
  if ! codex plugin marketplace add "$install_source" >&2; then
    codex plugin marketplace remove "$MARKETPLACE" >&2 || true
    codex plugin marketplace add "$install_source" >&2 \
      || die "codex plugin marketplace add failed for $install_source"
  fi
  # Codex copies the plugin into its own cache, so this also refreshes an upgrade.
  codex plugin add "$CORE_PLUGIN" >&2 \
    || die "codex plugin add $CORE_PLUGIN failed"
  if codex plugin list 2>/dev/null | grep "$CORE_PLUGIN" | grep -q "installed"; then
    record_verified codex ok
  else
    record_verified codex plugin-not-listed
  fi
  log "Codex: $CORE_PLUGIN installed. Start a new session to load it."
}

install_for_gemini() {
  have gemini || die "'gemini' is not on PATH. Install Gemini CLI, then rerun with --agent gemini."
  for skill in $CORE_SKILLS; do
    if [ "$source_mode" = "cdn" ]; then
      # --path only applies to Git sources, so point at the skill directory.
      gemini skills install "$toolkit_dir/skills/core/$skill" --consent >&2 \
        || die "gemini skills install failed for $skill"
    else
      gemini skills install "$github_url" --path "skills/core/$skill" --consent >&2 \
        || die "gemini skills install failed for $skill"
    fi
  done
  if gemini skills list 2>&1 | lists_core_skills; then
    record_verified gemini ok
  else
    record_verified gemini skills-not-listed
  fi
  log "Gemini CLI: core skills installed. Restart Gemini CLI to load them."
}

install_for_trae_cli() {
  trae_bin=""
  for candidate in coco traecli trae-agent; do
    if have "$candidate"; then
      trae_bin="$candidate"
      break
    fi
  done
  [ -n "$trae_bin" ] || die "Trae CLI (coco, traecli, or trae-agent) is not on PATH. Install it, then rerun with --agent trae-cli."
  # Trae CLI names a marketplace after its directory unless told otherwise, and
  # keeps an existing name bound to its old source, so rebind it explicitly.
  "$trae_bin" plugin marketplace remove "$MARKETPLACE" >/dev/null 2>&1 || true
  if [ "$source_mode" = "cdn" ]; then
    "$trae_bin" plugin marketplace add "$install_source" --name "$MARKETPLACE" --type local >&2 \
      || die "$trae_bin plugin marketplace add failed for $install_source"
  else
    "$trae_bin" plugin marketplace add "$install_source" --name "$MARKETPLACE" --type github >&2 \
      || die "$trae_bin plugin marketplace add failed for $install_source"
  fi
  "$trae_bin" plugin install "$CORE_PLUGIN" --type marketplace --yes >&2 \
    || die "$trae_bin plugin install $CORE_PLUGIN failed"
  if "$trae_bin" plugin list 2>/dev/null | grep -q "volcengine-core"; then
    record_verified trae-cli ok
  else
    record_verified trae-cli plugin-not-listed
  fi
  log "Trae CLI: $CORE_PLUGIN installed. Start a new session to load it."
}

# DoubaoWork keeps user skills inside each browser profile, a location no
# installer CLI knows about, so the core skills are copied there directly.
doubao_work_roots() {
  case "$(uname -s)" in
    Darwin) printf '%s\n' "${HOME:?HOME is not set}/Library/Application Support/DoubaoWork" ;;
    MINGW*|MSYS*|CYGWIN*)
      [ -z "${LOCALAPPDATA:-}" ] || printf '%s\n' "$LOCALAPPDATA/DoubaoWork/User Data"
      [ -z "${APPDATA:-}" ] || printf '%s\n' "$APPDATA/DoubaoWork" ;;
    *) printf '%s\n' "${XDG_CONFIG_HOME:-${HOME:?HOME is not set}/.config}/DoubaoWork" ;;
  esac
}

install_for_doubao_work() {
  [ "$source_mode" = "cdn" ] || die "--agent doubao-work installs from the local toolkit directory; rerun without --source github."
  installed_profiles=0
  doubao_roots="$(doubao_work_roots)"
  old_ifs="$IFS"
  IFS='
'
  for root in $doubao_roots; do
    for user_skills in "$root"/*/.doubaowork/agent_mode/workspace/.user_skills; do
      [ -d "$user_skills" ] || continue
      IFS="$old_ifs"
      for skill in $CORE_SKILLS; do
        rm -rf "${user_skills:?}/$skill"
        cp -R "$toolkit_dir/skills/core/$skill" "$user_skills/$skill" \
          || die "Cannot copy $skill into $user_skills"
        [ -f "$user_skills/$skill/SKILL.md" ] || die "$skill is missing from $user_skills after the copy"
      done
      IFS='
'
      installed_profiles=$((installed_profiles + 1))
      log "DoubaoWork: core skills copied to $user_skills"
    done
  done
  IFS="$old_ifs"
  [ "$installed_profiles" -gt 0 ] \
    || die "No DoubaoWork user skill directory found. Open DoubaoWork once so it creates its workspace, then rerun."
  record_verified doubao-work ok
  log "DoubaoWork: restart the app or open a new task to load the skills."
}

install_with_skills_cli() {
  # $1 = agent name understood by the skills CLI
  have npx || die "'npx' is not on PATH. Install Node.js, then rerun with --agent $1."
  # shellcheck disable=SC2086
  npx --yes skills add "$install_source" --global --yes --copy --full-depth \
    --skill $CORE_SKILLS --agent "$1" >&2 \
    || die "npx skills add failed for agent $1"
  if npx --yes skills list --global --agent "$1" 2>/dev/null | lists_core_skills; then
    record_verified "$1" ok
  else
    record_verified "$1" skills-not-listed
  fi
  log "$1: core skills installed through the skills CLI. Start a new session to load them."
}

old_ifs="$IFS"
IFS=,
# shellcheck disable=SC2086
set -- $agent
IFS="$old_ifs"
for name in "$@"; do
  case "$name" in
    "") : ;;
    claude|claude-code) install_for_claude ;;
    codex) install_for_codex ;;
    gemini|gemini-cli) install_for_gemini ;;
    trae-cli|coco) install_for_trae_cli ;;
    doubao-work|doubaowork) install_for_doubao_work ;;
    *) install_with_skills_cli "$name" ;;
  esac
done

printf 'SOURCE=%s\n' "$source_mode"
printf 'VERSION=%s\n' "$toolkit_version"
printf 'TOOLKIT_DIR=%s\n' "$toolkit_dir"
printf 'INSTALL_SOURCE=%s\n' "$install_source"
printf 'AGENT=%s\n' "$agent"
printf 'VERIFIED=%s\n' "$verified"

if [ -z "$agent" ]; then
  cat >&2 <<NEXT

Install the core plugin for your host:

  Claude Code:
    claude plugin marketplace add "$install_source"
    claude plugin install $CORE_PLUGIN

  Codex:
    codex plugin marketplace add "$install_source"
    codex plugin add $CORE_PLUGIN

  Other hosts (skills CLI; add --agent <name> to target one host):
    npx skills add "$install_source" --global --yes --copy --full-depth \\
      --skill $CORE_SKILLS

Or rerun this installer with --agent <name>[,<name>], for example --agent claude,codex.
NEXT
fi

# A host that cannot see the install is a failed install, whatever the exit
# codes above said.
for entry in $(printf '%s' "$verified" | tr ',' ' '); do
  case "$entry" in
    *:ok) : ;;
    *) die "Installed, but ${entry%%:*} does not list the core skills (${entry#*:}). Check that host's own install state." ;;
  esac
done
