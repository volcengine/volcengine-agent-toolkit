# Install or upgrade the ve CLI

Always run the latest release. This skill assumes the current `ve`: device-code `ve login`, `--output`/`--query`, `--force`, `--detail`, and double-dash system flags. There is no support path for older builds — upgrade instead.

**Minimum version (mandatory):** Before the first other `ve` command in a task — native OpenAPI calls, login, or product CLI delegation — run `ve version` and require **`ve >= 1.1.11`** (stable releases `1.1.11` or newer). If `ve` is missing, older than `1.1.11`, or its version cannot be verified, install or upgrade with one of the options below and run `ve version` again before continuing. If npm still installs an older version, the configured npm mirror may lag behind; use the CDN installer or GitHub Releases instead.

**Option 1: npm (preferred)**

```bash
npm i -g @volcengine/cli
```

**Option 2: CDN installer (no Node.js, or npm unreachable)**

```bash
curl -fsSL https://cloudcache.volccdn.com/ve/install.sh | sh
# or
wget -qO- https://cloudcache.volccdn.com/ve/install.sh | sh
```

The same script ships as `scripts/install_ve.sh`. It reads the latest version from the CDN, downloads the archive for the host's OS/CPU, verifies it against the published `SHA256SUMS`, installs to `/usr/local/bin` when writable (else `~/.local/bin`, never `sudo`), removes the macOS quarantine flag, and runs `ve skills update`. `--version <ver>`, `--install-dir <dir>`, `--dry-run` and the `VE_VERSION` / `VE_INSTALL_DIR` / `VOLCENGINE_CLI_DOWNLOAD_BASE_URL` / `VOLCENGINE_CLI_SKIP_SKILLS` variables are documented in its header. Windows: use npm or the release page.

**Option 3: GitHub Releases** — https://github.com/volcengine/volcengine-cli/releases

**Native OpenAPI capability checks:** `ve login --help` must list `--no-browser`, and `ve ecs DescribeInstances --help` must list `--output` under *System Flags*. If either is missing, upgrade with `npm i -g @volcengine/cli@latest` or rerun the CDN installer, then continue. These checks do not replace the minimum version requirement above.
