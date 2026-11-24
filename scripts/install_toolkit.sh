#!/bin/sh
# Volcengine Agent Toolkit installer: GitHub first, CDN when GitHub is unreachable.
#
# When GitHub answers, the hosts install straight from the repository, exactly
# as the README describes. When it does not, or when an install from GitHub
# fails part-way, this script downloads the toolkit package published on the
# Volcengine CDN, verifies its SHA-256 against the release manifest, unpacks it
# to a persistent local directory, and installs from that directory instead.
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
#                            and workbuddy get the core skills copied into
#                            their user skill directory; any other name
#                            (cursor, qoder, opencode, trae, trae-cn, ...) is
#                            passed to `npx skills add --agent`, and `other`,
#                            or a name the skills CLI does not know, installs
#                            for every host it detects. A host whose own
#                            command is not on PATH is installed through the
#                            skills CLI too. Without --agent the script only
#                            prints the commands to run.
#   --source <auto|github|cdn>
#                            auto (default) probes GitHub; github and cdn skip
#                            the probe.
#   --dir <dir>              Local toolkit directory for the CDN path.
#   --version <ver>          Install this released version. Released versions
#                            exist only on the CDN, so this selects the CDN.
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

# Everything runs inside main(), called on the last line. With `curl | sh` the
# shell reads this script from stdin as it goes; a child process that also
# reads stdin would otherwise swallow the rest of the script.
main() {

DEFAULT_BASE_URL="https://cloudcache.volccdn.com/ve/skills"
DEFAULT_GITHUB_URL="https://github.com/volcengine/volcengine-agent-toolkit"
GITHUB_REPOSITORY="volcengine/volcengine-agent-toolkit"
MARKETPLACE="volcengine-skills"
CORE_PLUGIN="volcengine-core@volcengine-skills"
CORE_SKILLS="volcengine-cli volcengine-troubleshooting volcengine-knowledge-search volcengine-find-skills volcengine-feedback volcengine-cost"
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
# A failure that another download source cannot fix: a missing tool, a host
# directory that does not exist. Exit 4 tells the retry loop not to try the CDN.
die_local() { log "ERROR: $*"; exit 4; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
  cat >&2 <<'USAGE'
Usage: install_toolkit.sh [--agent <name>[,<name>]] [--source <auto|github|cdn>]
                          [--dir <dir>] [--version <ver>] [--dry-run]

  --agent <names>    Install the core skills for these hosts, comma separated:
                     claude, codex, trae-cli (core plugin), gemini (gemini skills
                     install), doubao-work, workbuddy (copied into the host's user
                     skill directory), any agent name the skills CLI accepts
                     (cursor, qoder, opencode, trae, trae-cn, ...), or other
  --source <mode>    auto probes GitHub (default); github or cdn skips the probe
  --dir <dir>        Local toolkit directory for the CDN path (env VOLCENGINE_TOOLKIT_DIR,
                     default ~/.volcengine/agent-toolkit)
  --version <ver>    Install this released version; selects the CDN source
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
# Hosts keep this path. A relative one would break as soon as the working
# directory changes, and "a/b" also reads like a GitHub owner/repo.
case "$toolkit_dir" in
  /*) : ;;
  *) toolkit_dir="$(pwd)/$toolkit_dir" ;;
esac

cleanup() {
  if [ -n "$tmp_dir" ] && [ -d "$tmp_dir" ]; then
    rm -rf "$tmp_dir"
  fi
  if [ -n "$staging_dir" ] && [ -d "$staging_dir" ]; then
    rm -rf "$staging_dir"
  fi
}
trap cleanup EXIT
# Without the exit, the script would carry on after cleanup removed its files.
trap 'cleanup; exit 130' INT TERM HUP

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
    *[!0-9A-Za-z.+-]*) return 1 ;;
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
# Download sources
# ---------------------------------------------------------------------------
# GitHub is preferred. The CDN package is used when GitHub does not answer, and
# again when an install from GitHub fails part-way: the probe only shows that
# the GitHub website loads, while the hosts go on to clone the repository.
tmp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t volcengine-toolkit)"
install_source="$GITHUB_REPOSITORY"
toolkit_version=""
toolkit_url=""
expected=""
cdn_ready=0

resolve_cdn_manifest() {
  if [ -n "$version" ]; then
    wanted="$(normalize_version "$version")" || die "Invalid version '$version' (expected e.g. 1.3.4)"
    manifest_url="$base_url/v$wanted/$MANIFEST_NAME"
  else
    manifest_url="$base_url/latest/$MANIFEST_NAME"
  fi

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
}

# Download, verify, unpack next to the target, then swap.
ensure_cdn_toolkit() {
  [ "$cdn_ready" -eq 0 ] || return 0
  installed_version=""
  if is_toolkit_dir "$toolkit_dir" && [ -f "$toolkit_dir/package.json" ]; then
    installed_version="$(json_string "$toolkit_dir/package.json" version)"
  fi

  if [ "$installed_version" = "$toolkit_version" ]; then
    log "Volcengine Agent Toolkit v$toolkit_version is already in $toolkit_dir."
  else
    # A clone of the repository has the same layout as an unpacked package.
    # Replacing it would delete its history and any uncommitted work.
    if [ -e "$toolkit_dir/.git" ]; then
      die "$toolkit_dir is a Git checkout, not an installed package. Pass --dir <dir> to use another location."
    fi
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
  cdn_ready=1
}

if [ -n "$version" ]; then
  case "$source_mode" in
    github) die "--version selects a released package, which only the CDN has. Drop --source github, or drop --version." ;;
    auto) source_mode="cdn" ;;
  esac
fi

source_forced=1
if [ "$source_mode" = "auto" ]; then
  source_forced=0
  if github_reachable; then
    source_mode="github"
  else
    log "GitHub is not reachable from this host; using the Volcengine CDN."
    source_mode="cdn"
  fi
fi

if [ "$source_mode" = "cdn" ]; then
  resolve_cdn_manifest
fi

if [ "$dry_run" -eq 1 ]; then
  printf 'SOURCE=%s\n' "$source_mode"
  printf 'VERSION=%s\n' "$toolkit_version"
  printf 'TOOLKIT_URL=%s\n' "$toolkit_url"
  printf 'TOOLKIT_DIR=%s\n' "$toolkit_dir"
  printf 'INSTALL_SOURCE=%s\n' "$install_source"
  exit 0
fi

if [ "$source_mode" = "cdn" ]; then
  ensure_cdn_toolkit
fi

# Hosts that are installed by copying files need the core skills on disk. From
# the CDN that is the toolkit directory; from GitHub it is the default branch's
# source archive, unpacked into the temporary directory.
core_skills_dir() {
  if [ "$source_mode" = "cdn" ]; then
    printf '%s' "$toolkit_dir/skills/core"
    return 0
  fi
  github_src="$tmp_dir/github-src"
  if [ ! -d "$github_src/skills/core" ]; then
    have tar || die "need tar to unpack the GitHub source archive"
    rm -rf "$github_src"
    mkdir -p "$github_src"
    github_archive="$tmp_dir/github-src.tar.gz"
    log "Downloading the toolkit source from GitHub ..."
    if have curl; then
      curl -fsSL --retry 2 --connect-timeout 10 --max-time 300 -o "$github_archive" "$github_url/archive/HEAD.tar.gz" \
        || die "Download failed: $github_url/archive/HEAD.tar.gz"
    elif have wget; then
      wget -q --timeout=30 --tries=3 -O "$github_archive" "$github_url/archive/HEAD.tar.gz" \
        || die "Download failed: $github_url/archive/HEAD.tar.gz"
    else
      die "need curl or wget to download $github_url/archive/HEAD.tar.gz"
    fi
    tar -xzf "$github_archive" -C "$github_src" --strip-components 1 \
      || die "Cannot unpack the GitHub source archive"
    [ -d "$github_src/skills/core" ] || die "The GitHub source archive has no skills/core directory"
  fi
  printf '%s' "$github_src/skills/core"
}

# ---------------------------------------------------------------------------
# Host registration
# ---------------------------------------------------------------------------
# Each host is asked afterwards whether it can see what was installed, so the
# caller gets a verified result from this one command. Results go to a file per
# host because each host is installed in a subshell (see the loop below).
record_verified() {
  # $1 = agent name, $2 = ok or the reason it failed
  printf '%s:%s' "$1" "$2" > "$verify_file"
  [ "$2" = "ok" ] || exit 3
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

# Copy the core skills into a host's own skill directory.
copy_core_skills() {
  # $1 = destination directory
  core_dir="$(core_skills_dir)" || exit 1
  for skill in $CORE_SKILLS; do
    [ -f "$core_dir/$skill/SKILL.md" ] || die "$skill is missing from the downloaded source"
  done
  for skill in $CORE_SKILLS; do
    staging="$(mktemp -d "$1/../.skill-install.XXXXXX")" \
      || die_local "Cannot prepare $skill installation in $1"
    if ! cp -R "$core_dir/$skill" "$staging/$skill"; then
      rm -rf "${staging:?}"
      die_local "Cannot copy $skill into $1"
    fi
    if [ ! -f "$staging/$skill/SKILL.md" ]; then
      rm -rf "${staging:?}"
      die "$skill is missing from the staged copy"
    fi
    if [ -e "$1/$skill" ] || [ -L "$1/$skill" ]; then
      mv "$1/$skill" "$staging/previous" || die_local "Cannot replace $skill in $1"
    fi
    if ! mv "$staging/$skill" "$1/$skill"; then
      if [ -e "$staging/previous" ] || [ -L "$staging/previous" ]; then
        mv "$staging/previous" "$1/$skill" || die_local "Cannot restore $skill from $staging/previous"
      fi
      rm -rf "${staging:?}"
      die_local "Cannot install $skill into $1"
    fi
    rm -rf "${staging:?}"
  done
}

install_with_skills_cli() {
  # $1 = agent name for the skills CLI, or "" to let it install for every host
  #      it detects plus the shared ~/.agents/skills directory
  # $2 = name to report in VERIFIED
  have npx || die_local "'npx' is not on PATH. Install Node.js, then rerun with --agent $2."
  skills_agent="$1"
  if [ -n "$skills_agent" ]; then
    skills_status=0
    # shellcheck disable=SC2086
    skills_output="$(npx --yes skills add "$install_source" --global --yes --copy --full-depth \
      --skill $CORE_SKILLS --agent "$skills_agent" 2>&1 </dev/null)" || skills_status=$?
    # The skills CLI prints a long report. It is shown only on failure, so
    # that the result lines at the end stay visible in a host's tool output.
    case "$skills_output" in
      *"Invalid agents"*)
        # A name the skills CLI does not know is not a failed install: fall
        # back to installing for every host it detects.
        log "The skills CLI does not know the agent '$skills_agent'; installing for every host it detects instead."
        skills_agent="" ;;
      *)
        if [ "$skills_status" -ne 0 ]; then
          log "$skills_output"
          die "npx skills add failed for agent $skills_agent"
        fi ;;
    esac
  fi
  if [ -z "$skills_agent" ]; then
    # shellcheck disable=SC2086
    if ! skills_output="$(npx --yes skills add "$install_source" --global --yes --copy --full-depth \
      --skill $CORE_SKILLS 2>&1 </dev/null)"; then
      log "$skills_output"
      die "npx skills add failed"
    fi
    skills_listing="$(npx --yes skills list --global 2>/dev/null </dev/null)"
  else
    skills_listing="$(npx --yes skills list --global --agent "$skills_agent" 2>/dev/null </dev/null)"
  fi
  log "$2: core skills installed through the skills CLI. Start a new session to load them."
  if printf '%s' "$skills_listing" | lists_core_skills; then
    record_verified "$2" ok
  else
    record_verified "$2" skills-not-listed
  fi
}

# A host whose own CLI is not on PATH is still served: desktop builds often
# ship without the command, and the host reads the same user skill directory.
install_for_claude() {
  if ! have claude; then
    log "'claude' is not on PATH; installing the core skills for Claude Code through the skills CLI."
    install_with_skills_cli claude-code claude
    return 0
  fi
  # Adding an already known marketplace repoints it at this source.
  claude plugin marketplace add "$install_source" >&2 </dev/null \
    || die "claude plugin marketplace add failed for $install_source"
  claude plugin install "$CORE_PLUGIN" >&2 </dev/null \
    || die "claude plugin install $CORE_PLUGIN failed"
  log "Claude Code: $CORE_PLUGIN installed. Run /reload-plugins in an open session, or start a new one."
  if claude plugin list 2>/dev/null </dev/null | grep -q "$CORE_PLUGIN"; then
    record_verified claude ok
  else
    record_verified claude plugin-not-listed
  fi
}

install_for_codex() {
  if ! have codex; then
    log "'codex' is not on PATH; installing the core skills for Codex through the skills CLI."
    install_with_skills_cli codex codex
    return 0
  fi
  # Codex refuses to add a marketplace name that is bound to another source, so
  # drop the old binding and add this one.
  if ! codex plugin marketplace add "$install_source" >&2 </dev/null; then
    codex plugin marketplace remove "$MARKETPLACE" >&2 </dev/null || true
    codex plugin marketplace add "$install_source" >&2 </dev/null \
      || die "codex plugin marketplace add failed for $install_source"
  fi
  # Codex copies the plugin into its own cache, so this also refreshes an upgrade.
  codex plugin add "$CORE_PLUGIN" >&2 </dev/null \
    || die "codex plugin add $CORE_PLUGIN failed"
  log "Codex: $CORE_PLUGIN installed. Start a new session to load it."
  if codex plugin list 2>/dev/null </dev/null | grep "$CORE_PLUGIN" | grep -v "not installed" | grep -q "installed"; then
    record_verified codex ok
  else
    record_verified codex plugin-not-listed
  fi
}

install_for_gemini() {
  if ! have gemini; then
    log "'gemini' is not on PATH; installing the core skills for Gemini CLI through the skills CLI."
    install_with_skills_cli gemini-cli gemini
    return 0
  fi
  for skill in $CORE_SKILLS; do
    if [ "$source_mode" = "cdn" ]; then
      # --path only applies to Git sources, so point at the skill directory.
      gemini skills install "$toolkit_dir/skills/core/$skill" --consent >&2 </dev/null \
        || die "gemini skills install failed for $skill"
    else
      gemini skills install "$github_url" --path "skills/core/$skill" --consent >&2 </dev/null \
        || die "gemini skills install failed for $skill"
    fi
  done
  log "Gemini CLI: core skills installed. Restart Gemini CLI to load them."
  if gemini skills list 2>&1 </dev/null | lists_core_skills; then
    record_verified gemini ok
  else
    record_verified gemini skills-not-listed
  fi
}

# Run a command under a pseudo-terminal and discard its output. Trae CLI
# silently refuses to uninstall a plugin or remove a marketplace when it has no
# terminal, which is the normal case when an agent runs this script.
with_tty() {
  if have script; then
    # BSD and macOS: script [-q] file command...
    script -q /dev/null "$@" >/dev/null 2>&1 </dev/null && return 0
    # util-linux: script -qec "command" file. The arguments passed here never
    # contain spaces, so joining them is safe.
    script -qec "$*" /dev/null >/dev/null 2>&1 </dev/null && return 0
  fi
  "$@" >/dev/null 2>&1 </dev/null
}

install_for_trae_cli() {
  trae_bin=""
  for candidate in coco traecli trae-agent; do
    if have "$candidate"; then
      trae_bin="$candidate"
      break
    fi
  done
  if [ -z "$trae_bin" ]; then
    log "Trae CLI (coco, traecli, or trae-agent) is not on PATH; installing the core skills for Trae through the skills CLI."
    install_with_skills_cli trae trae-cli
    return 0
  fi
  # Trae CLI names a marketplace after its directory unless told otherwise, and
  # keeps an existing name bound to its old source. It will not remove a
  # marketplace that still has a plugin installed from it, so drop the plugin
  # first, then the marketplace, then add this source.
  with_tty "$trae_bin" plugin uninstall volcengine-core || true
  with_tty "$trae_bin" plugin marketplace remove "$MARKETPLACE" || true
  trae_type="github"
  [ "$source_mode" != "cdn" ] || trae_type="local"
  "$trae_bin" plugin marketplace add "$install_source" --name "$MARKETPLACE" --type "$trae_type" >&2 </dev/null \
    || die "$trae_bin plugin marketplace add failed for $install_source. If the marketplace is still bound to another source, run '$trae_bin plugin uninstall volcengine-core' and '$trae_bin plugin marketplace remove $MARKETPLACE' in a terminal, then rerun."
  "$trae_bin" plugin install "$CORE_PLUGIN" --type marketplace --yes >&2 </dev/null \
    || die "$trae_bin plugin install $CORE_PLUGIN failed"
  log "Trae CLI: $CORE_PLUGIN installed. Start a new session to load it."
  if "$trae_bin" plugin list 2>/dev/null </dev/null | grep -q "volcengine-core"; then
    record_verified trae-cli ok
  else
    record_verified trae-cli plugin-not-listed
  fi
}

# Doubao keeps user skills inside each browser profile, a location no installer
# CLI knows about, so the core skills are copied there directly. The standalone
# DoubaoWork app and the work mode built into the Doubao app use different
# application directories and dot-directories; both are searched.
doubao_work_roots() {
  case "$(uname -s)" in
    Darwin)
      printf '%s\n' "${HOME:?HOME is not set}/Library/Application Support/DoubaoWork"
      printf '%s\n' "$HOME/Library/Application Support/Doubao" ;;
    MINGW*|MSYS*|CYGWIN*)
      for app in DoubaoWork Doubao; do
        [ -z "${LOCALAPPDATA:-}" ] || printf '%s\n' "$LOCALAPPDATA/$app/User Data"
        [ -z "${APPDATA:-}" ] || printf '%s\n' "$APPDATA/$app"
      done ;;
    *)
      printf '%s\n' "${XDG_CONFIG_HOME:-${HOME:?HOME is not set}/.config}/DoubaoWork"
      printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/Doubao" ;;
  esac
}

install_for_doubao_work() {
  installed_profiles=0
  doubao_roots="$(doubao_work_roots)"
  old_ifs="$IFS"
  IFS='
'
  for root in $doubao_roots; do
    for user_skills in "$root"/*/.doubaowork/agent_mode/workspace/.user_skills \
      "$root"/*/.doubao/agent_mode/workspace/.user_skills; do
      [ -d "$user_skills" ] || continue
      IFS="$old_ifs"
      copy_core_skills "$user_skills"
      legacy_skill="$user_skills/volcengine-billing-and-cost-management"
      if [ -e "$legacy_skill" ] || [ -L "$legacy_skill" ]; then
        backup_root="$user_skills/../.skill-migration-backups"
        mkdir -p "$backup_root" || die "Cannot prepare the legacy Skill backup"
        backup="$(mktemp -d "$backup_root/volcengine-billing-and-cost-management.XXXXXX")" \
          || die "Cannot create the legacy Skill backup"
        mv "$legacy_skill" "$backup/volcengine-billing-and-cost-management" \
          || die "Cannot migrate the legacy billing Skill"
        log "DoubaoWork: previous billing Skill backed up to $backup"
      fi
      IFS='
'
      installed_profiles=$((installed_profiles + 1))
      log "Doubao: core skills copied to $user_skills"
    done
  done
  IFS="$old_ifs"
  [ "$installed_profiles" -gt 0 ] \
    || die_local "No Doubao user skill directory found. Start one task in Doubao work mode so it creates its workspace, then rerun."
  log "Doubao: open a new task, or restart the app, to load the skills."
  record_verified doubao-work ok
}

# WorkBuddy reads user skills from ~/.workbuddy/skills, which the skills CLI
# does not know, so the core skills are copied there directly.
install_for_workbuddy() {
  workbuddy_home="${HOME:?HOME is not set}/.workbuddy"
  [ -d "$workbuddy_home" ] \
    || die_local "No WorkBuddy directory found at $workbuddy_home. Open WorkBuddy once so it creates it, then rerun."
  mkdir -p "$workbuddy_home/skills" || die_local "Cannot create $workbuddy_home/skills"
  copy_core_skills "$workbuddy_home/skills"
  log "WorkBuddy: core skills copied to $workbuddy_home/skills. Start a new task to load them."
  record_verified workbuddy ok
}

install_one() {
  case "$1" in
    claude|claude-code) install_for_claude ;;
    codex) install_for_codex ;;
    gemini|gemini-cli) install_for_gemini ;;
    trae-cli|coco) install_for_trae_cli ;;
    doubao-work|doubaowork) install_for_doubao_work ;;
    workbuddy) install_for_workbuddy ;;
    other) install_with_skills_cli "" other ;;
    *) install_with_skills_cli "$1" "$1" ;;
  esac
}

# Each host is installed in a subshell so that a failure can be retried from
# the CDN instead of ending the run. Exit 3 means the commands succeeded but
# the host does not list the install.
old_ifs="$IFS"
IFS=,
# shellcheck disable=SC2086
set -- $agent
IFS="$old_ifs"
host_index=0
for name in "$@"; do
  [ -n "$name" ] || continue
  host_index=$((host_index + 1))
  verify_file="$tmp_dir/verified.$host_index"
  status=0
  ( install_one "$name" ) || status=$?
  if [ "$status" -ne 0 ] && [ "$status" -ne 4 ] && [ "$source_mode" = "github" ] && [ "$source_forced" -eq 0 ]; then
    log "Installing for $name from GitHub did not complete; retrying from the Volcengine CDN."
    resolve_cdn_manifest
    ensure_cdn_toolkit
    source_mode="cdn"
    rm -f "$verify_file"
    status=0
    ( install_one "$name" ) || status=$?
  fi
  case "$status" in
    0|3) : ;;
    *) exit 1 ;;
  esac
done

# Report the hosts in the order they were given.
verified=""
slot=0
while [ "$slot" -lt "$host_index" ]; do
  slot=$((slot + 1))
  [ -f "$tmp_dir/verified.$slot" ] || continue
  verified="${verified:+$verified,}$(cat "$tmp_dir/verified.$slot")"
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

}

main "$@"
