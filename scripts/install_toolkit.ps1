# Volcengine Agent Toolkit installer for PowerShell: GitHub first, CDN when
# GitHub is unreachable. It mirrors install_toolkit.sh: same options, same
# environment variables, same KEY=VALUE result lines.
#
#   irm https://cloudcache.volccdn.com/ve/skills/install.ps1 | iex
#   & ([scriptblock]::Create((irm https://cloudcache.volccdn.com/ve/skills/install.ps1))) -Agent claude,codex
#
# Parameters:
#   -Agent <name>[,<name>]   Also install the core skills for these hosts.
#                            claude, codex and trae-cli get the core plugin from
#                            the marketplace; gemini uses `gemini skills install`;
#                            doubao-work copies the core skills into the
#                            DoubaoWork user skill directory; any other name
#                            (cursor, opencode, trae, trae-cn, ...) is passed to
#                            `npx skills add --agent`. Without -Agent the script
#                            only prints the commands to run.
#   -Source <auto|github|cdn>  auto (default) probes GitHub.
#   -Dir <dir>               Local toolkit directory for the CDN path.
#   -Version <ver>           Download this version instead of the CDN "latest".
#   -DryRun                  Print the resolved values and exit.
#
# Environment: VOLCENGINE_TOOLKIT_BASE_URL, VOLCENGINE_TOOLKIT_DIR,
# VOLCENGINE_TOOLKIT_GITHUB_URL (see install_toolkit.sh).
#
# Works on Windows PowerShell 5.1 and PowerShell 7+. The local directory must
# persist: hosts keep reading the marketplace from it. Rerun to upgrade.

[CmdletBinding()]
param(
    [string[]]$Agent = @(),
    [ValidateSet('auto', 'github', 'cdn')]
    [string]$Source = 'auto',
    [string]$Dir = '',
    [string]$Version = '',
    [switch]$DryRun
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$DefaultBaseUrl = 'https://cloudcache.volccdn.com/ve/skills'
$DefaultGithubUrl = 'https://github.com/volcengine/volcengine-agent-toolkit'
$GithubRepository = 'volcengine/volcengine-agent-toolkit'
$Marketplace = 'volcengine-skills'
$CorePlugin = 'volcengine-core@volcengine-skills'
$CoreSkills = @(
    'volcengine-cli',
    'volcengine-troubleshooting',
    'volcengine-knowledge-search',
    'volcengine-find-skills',
    'volcengine-feedback',
    'volcengine-billing-and-cost-management'
)
$ManifestName = 'toolkit-manifest.json'
$ArchiveName = 'volcengine-agent-toolkit.zip'
$OnWindows = ($env:OS -eq 'Windows_NT')

function Write-Log([string]$Message) { [Console]::Error.WriteLine($Message) }
function Stop-Install([string]$Message) {
    # throw, not exit: under `irm | iex` an exit would close the user's shell.
    # The catch at the end of the script reports it and sets the exit code.
    throw "ERROR: $Message"
}
function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

try {
$baseUrl = if ($env:VOLCENGINE_TOOLKIT_BASE_URL) { $env:VOLCENGINE_TOOLKIT_BASE_URL } else { $DefaultBaseUrl }
$baseUrl = $baseUrl.TrimEnd('/', '\')
if (-not $baseUrl) { Stop-Install 'VOLCENGINE_TOOLKIT_BASE_URL is empty' }
$githubUrl = if ($env:VOLCENGINE_TOOLKIT_GITHUB_URL) { $env:VOLCENGINE_TOOLKIT_GITHUB_URL } else { $DefaultGithubUrl }
if (-not $Dir) { $Dir = $env:VOLCENGINE_TOOLKIT_DIR }
if (-not $Dir) { $Dir = Join-Path (Join-Path $HOME '.volcengine') 'agent-toolkit' }
$toolkitDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Dir)

# "-Agent a,b" arrives as an array; "-Agent 'a,b'" as one string. Accept both.
$agents = @($Agent | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($name in $agents) {
    if ($name -notmatch '^[A-Za-z0-9_-]+$') { Stop-Install "Invalid -Agent '$name' (expected names such as claude,codex)" }
}

# Windows PowerShell 5.1 does not negotiate TLS 1.2 on its own.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

$isLocalBase = ($baseUrl -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://')

function Join-Base([string]$Base, [string]$Relative) {
    if ($isLocalBase) { return (Join-Path $Base $Relative) }
    return "$Base/$Relative"
}

function Get-RemoteFile([string]$From, [string]$To) {
    if ($isLocalBase) {
        if (-not (Test-Path -LiteralPath $From -PathType Leaf)) { return $false }
        Copy-Item -LiteralPath $From -Destination $To -Force
        return $true
    }
    try {
        Invoke-WebRequest -Uri $From -OutFile $To -UseBasicParsing -TimeoutSec 300 | Out-Null
        return $true
    } catch {
        return $false
    }
}

# GitHub often stalls rather than refuses, so the probe is short and bounded.
function Test-GithubReachable {
    try {
        Invoke-WebRequest -Uri $githubUrl -Method Head -UseBasicParsing -TimeoutSec 10 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function ConvertTo-ToolkitVersion([string]$Value) {
    $text = ($Value -replace '\s', '')
    if ($text.StartsWith('v')) { $text = $text.Substring(1) }
    if ($text -match '^[0-9]+\.[0-9]+\.[0-9]+') { return $text }
    return $null
}

function Test-ToolkitDir([string]$Path) {
    return (Test-Path -LiteralPath (Join-Path $Path '.claude-plugin/marketplace.json') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Path 'plugins/volcengine-core/skills') -PathType Container)
}

function Expand-Toolkit([string]$Archive, [string]$Destination) {
    # Off Windows, unzip keeps the executable bits that Expand-Archive drops.
    if (-not $OnWindows -and (Test-Command 'unzip')) {
        $result = Invoke-NativeCommand 'unzip' @('-o', '-q', $Archive, '-d', $Destination) -Log
        if ($result.ExitCode -ne 0) { Stop-Install "unzip failed for $Archive" }
        return
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force
}

# Every native program is run through this function. Windows PowerShell 5.1
# wraps each stderr line captured by 2>&1 in an error record, and under
# $ErrorActionPreference = 'Stop' the first such line ends the script even when
# the program exits 0. npm, claude and codex all write progress and warnings to
# stderr, so the preference is lowered for the call (the assignment is local to
# this function) and only the exit code decides success.
function Invoke-NativeCommand([string]$Command, [string[]]$Arguments, [switch]$Log) {
    $ErrorActionPreference = 'Continue'
    $lines = @(& $Command @Arguments 2>&1 | ForEach-Object {
        $line = "$_"
        if ($Log) { Write-Log $line }
        $line
    })
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $lines }
}

function Invoke-Host([string]$Description, [string]$Command, [string[]]$Arguments) {
    # Host CLIs are native programs (often .cmd shims on Windows); their output
    # is progress for the user, not part of this script's result lines.
    $result = Invoke-NativeCommand $Command $Arguments -Log
    if ($result.ExitCode -ne 0) { Stop-Install "$Description failed" }
}

# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------
# DoubaoWork is installed by copying from the local toolkit directory, so it
# always needs the CDN package, whether or not GitHub answers.
if ($Source -eq 'auto' -and ($agents | Where-Object { $_ -match '^(doubao-work|doubaowork)$' })) {
    $Source = 'cdn'
}

if ($Source -eq 'auto') {
    if (Test-GithubReachable) {
        $Source = 'github'
    } else {
        Write-Log 'GitHub is not reachable from this host; using the Volcengine CDN.'
        $Source = 'cdn'
    }
}

$installSource = $GithubRepository
$toolkitVersion = ''
$toolkitUrl = ''
$expectedHash = ''
$tempDir = $null
$stagingDir = $null

try {
    if ($Source -eq 'cdn') {
        if ($Version) {
            $wanted = ConvertTo-ToolkitVersion $Version
            if (-not $wanted) { Stop-Install "Invalid version '$Version' (expected e.g. 1.3.4)" }
            $manifestUrl = Join-Base $baseUrl "v$wanted/$ManifestName"
        } else {
            $manifestUrl = Join-Base $baseUrl "latest/$ManifestName"
        }

        $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("volcengine-toolkit-" + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        $manifestPath = Join-Path $tempDir $ManifestName
        if (-not (Get-RemoteFile $manifestUrl $manifestPath)) {
            Stop-Install "Cannot read $manifestUrl. Check the network, or pass -Version <ver>."
        }
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            Stop-Install "Malformed manifest at $manifestUrl"
        }
        $toolkitVersion = ConvertTo-ToolkitVersion ([string]$manifest.version)
        if (-not $toolkitVersion) { Stop-Install "Unexpected version in ${manifestUrl}: '$($manifest.version)'" }
        $toolkitUrl = [string]$manifest.toolkit.url
        $expectedHash = ([string]$manifest.toolkit.sha256).ToLowerInvariant()
        if (-not $toolkitUrl) { Stop-Install "No toolkit url in $manifestUrl" }
        if ($expectedHash -notmatch '^[0-9a-f]{64}$') {
            Stop-Install "No usable sha256 in $manifestUrl. Refusing to install an unverified package."
        }
        # A manifest built without --cdn-base-url names the archive relative to itself.
        if ($toolkitUrl -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://' -and -not [IO.Path]::IsPathRooted($toolkitUrl)) {
            $toolkitUrl = Join-Base $baseUrl "v$toolkitVersion/$toolkitUrl"
        }
        $installSource = $toolkitDir
    }

    if ($DryRun) {
        Write-Output "SOURCE=$Source"
        Write-Output "VERSION=$toolkitVersion"
        Write-Output "TOOLKIT_URL=$toolkitUrl"
        Write-Output "TOOLKIT_DIR=$toolkitDir"
        Write-Output "INSTALL_SOURCE=$installSource"
        return
    }

    # -----------------------------------------------------------------------
    # CDN path: download, verify, unpack next to the target, then swap.
    # -----------------------------------------------------------------------
    if ($Source -eq 'cdn') {
        $installedVersion = ''
        $packageJson = Join-Path $toolkitDir 'package.json'
        if ((Test-ToolkitDir $toolkitDir) -and (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
            try {
                $installedVersion = [string](Get-Content -LiteralPath $packageJson -Raw -Encoding UTF8 | ConvertFrom-Json).version
            } catch { }
        }

        if ($installedVersion -eq $toolkitVersion) {
            Write-Log "Volcengine Agent Toolkit v$toolkitVersion is already in $toolkitDir."
        } else {
            if ((Test-Path -LiteralPath $toolkitDir) -and -not (Test-ToolkitDir $toolkitDir)) {
                # Never replace a directory this installer did not create.
                $isEmptyDir = (Test-Path -LiteralPath $toolkitDir -PathType Container) -and
                    -not (Get-ChildItem -LiteralPath $toolkitDir -Force | Select-Object -First 1)
                if (-not $isEmptyDir) {
                    Stop-Install "$toolkitDir exists and is not a Volcengine toolkit directory. Pass -Dir <dir> to use another location."
                }
            }

            $archivePath = Join-Path $tempDir $ArchiveName
            Write-Log "Downloading Volcengine Agent Toolkit v$toolkitVersion ..."
            if (-not (Get-RemoteFile $toolkitUrl $archivePath)) { Stop-Install "Download failed: $toolkitUrl" }
            $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -ne $expectedHash) {
                Stop-Install "Checksum mismatch for ${ArchiveName}: expected $expectedHash, got $actualHash. The download may have been tampered with."
            }
            Write-Log 'Checksum OK.'

            $parentDir = Split-Path -Parent $toolkitDir
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            # Unpack beside the target so the final step is a rename on one volume.
            # A broken download must never replace a working toolkit.
            $stagingDir = "$toolkitDir.install.$PID"
            if (Test-Path -LiteralPath $stagingDir) { Remove-Item -LiteralPath $stagingDir -Recurse -Force }
            New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
            Expand-Toolkit $archivePath $stagingDir
            if (-not (Test-ToolkitDir $stagingDir)) {
                Stop-Install "$ArchiveName does not contain the expected toolkit layout. Existing install left untouched."
            }

            $previousDir = $null
            if (Test-Path -LiteralPath $toolkitDir) {
                $previousDir = "$toolkitDir.previous.$PID"
                if (Test-Path -LiteralPath $previousDir) { Remove-Item -LiteralPath $previousDir -Recurse -Force }
                Move-Item -LiteralPath $toolkitDir -Destination $previousDir
            }
            try {
                Move-Item -LiteralPath $stagingDir -Destination $toolkitDir
            } catch {
                if ($previousDir) { Move-Item -LiteralPath $previousDir -Destination $toolkitDir }
                Stop-Install "Cannot move the toolkit into $toolkitDir. Existing install left untouched."
            }
            $stagingDir = $null
            if ($previousDir) { Remove-Item -LiteralPath $previousDir -Recurse -Force }
            Write-Log "Volcengine Agent Toolkit v$toolkitVersion unpacked to $toolkitDir"
        }
    }

    # -----------------------------------------------------------------------
    # Host registration
    # -----------------------------------------------------------------------
    # Each host is asked afterwards whether it can see what was installed, so
    # the caller gets a verified result from this one command.
    $script:verified = @()
    function Add-Verified([string]$Name, [bool]$Ok, [string]$Reason) {
        $script:verified += if ($Ok) { "${Name}:ok" } else { "${Name}:$Reason" }
    }
    function Test-ListsCoreSkills([string]$Listing) {
        foreach ($skill in $CoreSkills) {
            if (-not $Listing.Contains($skill)) { return $false }
        }
        return $true
    }
    function Get-HostOutput([string]$Command, [string[]]$Arguments) {
        return ((Invoke-NativeCommand $Command $Arguments).Output -join "`n")
    }

    function Install-ForClaude {
        if (-not (Test-Command 'claude')) { Stop-Install "'claude' is not on PATH. Install Claude Code, then rerun with -Agent claude." }
        # Adding an already known marketplace repoints it at this source.
        Invoke-Host "claude plugin marketplace add $installSource" 'claude' @('plugin', 'marketplace', 'add', $installSource)
        Invoke-Host "claude plugin install $CorePlugin" 'claude' @('plugin', 'install', $CorePlugin)
        Add-Verified 'claude' ((Get-HostOutput 'claude' @('plugin', 'list')).Contains($CorePlugin)) 'plugin-not-listed'
        Write-Log "Claude Code: $CorePlugin installed. Run /reload-plugins in an open session, or start a new one."
    }

    function Install-ForCodex {
        if (-not (Test-Command 'codex')) { Stop-Install "'codex' is not on PATH. Install Codex, then rerun with -Agent codex." }
        # Codex refuses a marketplace name that is bound to another source, so
        # drop the old binding and add this one.
        $added = Invoke-NativeCommand 'codex' @('plugin', 'marketplace', 'add', $installSource) -Log
        if ($added.ExitCode -ne 0) {
            Invoke-NativeCommand 'codex' @('plugin', 'marketplace', 'remove', $Marketplace) | Out-Null
            Invoke-Host "codex plugin marketplace add $installSource" 'codex' @('plugin', 'marketplace', 'add', $installSource)
        }
        # Codex copies the plugin into its own cache, so this also refreshes an upgrade.
        Invoke-Host "codex plugin add $CorePlugin" 'codex' @('plugin', 'add', $CorePlugin)
        $codexLine = (Get-HostOutput 'codex' @('plugin', 'list')) -split "`n" | Where-Object { $_.Contains($CorePlugin) } | Select-Object -First 1
        Add-Verified 'codex' ([bool]($codexLine -and $codexLine.Contains('installed'))) 'plugin-not-listed'
        Write-Log "Codex: $CorePlugin installed. Start a new session to load it."
    }

    function Install-ForGemini {
        if (-not (Test-Command 'gemini')) { Stop-Install "'gemini' is not on PATH. Install Gemini CLI, then rerun with -Agent gemini." }
        foreach ($skill in $CoreSkills) {
            if ($Source -eq 'cdn') {
                # --path only applies to Git sources, so point at the skill directory.
                $skillDir = Join-Path (Join-Path (Join-Path $toolkitDir 'skills') 'core') $skill
                Invoke-Host "gemini skills install $skill" 'gemini' @('skills', 'install', $skillDir, '--consent')
            } else {
                Invoke-Host "gemini skills install $skill" 'gemini' @('skills', 'install', $githubUrl, '--path', "skills/core/$skill", '--consent')
            }
        }
        Add-Verified 'gemini' (Test-ListsCoreSkills (Get-HostOutput 'gemini' @('skills', 'list'))) 'skills-not-listed'
        Write-Log 'Gemini CLI: core skills installed. Restart Gemini CLI to load them.'
    }

    function Install-ForTraeCli {
        $traeBin = @('coco', 'traecli', 'trae-agent') | Where-Object { Test-Command $_ } | Select-Object -First 1
        if (-not $traeBin) { Stop-Install 'Trae CLI (coco, traecli, or trae-agent) is not on PATH. Install it, then rerun with -Agent trae-cli.' }
        # Trae CLI names a marketplace after its directory unless told otherwise, and
        # keeps an existing name bound to its old source, so rebind it explicitly.
        Invoke-NativeCommand $traeBin @('plugin', 'marketplace', 'remove', $Marketplace) | Out-Null
        $type = if ($Source -eq 'cdn') { 'local' } else { 'github' }
        Invoke-Host "$traeBin plugin marketplace add $installSource" $traeBin @('plugin', 'marketplace', 'add', $installSource, '--name', $Marketplace, '--type', $type)
        Invoke-Host "$traeBin plugin install $CorePlugin" $traeBin @('plugin', 'install', $CorePlugin, '--type', 'marketplace', '--yes')
        Add-Verified 'trae-cli' ((Get-HostOutput $traeBin @('plugin', 'list')).Contains('volcengine-core')) 'plugin-not-listed'
        Write-Log "Trae CLI: $CorePlugin installed. Start a new session to load it."
    }

    # DoubaoWork keeps user skills inside each browser profile, a location no
    # installer CLI knows about, so the core skills are copied there directly.
    function Get-DoubaoWorkRoots {
        if ($OnWindows) {
            if ($env:LOCALAPPDATA) { Join-Path (Join-Path $env:LOCALAPPDATA 'DoubaoWork') 'User Data' }
            if ($env:APPDATA) { Join-Path $env:APPDATA 'DoubaoWork' }
        } elseif (Test-Path -LiteralPath (Join-Path $HOME 'Library/Application Support')) {
            Join-Path $HOME 'Library/Application Support/DoubaoWork'
        } else {
            $configHome = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME '.config' }
            Join-Path $configHome 'DoubaoWork'
        }
    }

    function Install-ForDoubaoWork {
        if ($Source -ne 'cdn') { Stop-Install '-Agent doubao-work installs from the local toolkit directory; rerun without -Source github.' }
        $installedProfiles = 0
        foreach ($root in @(Get-DoubaoWorkRoots)) {
            if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
            foreach ($profileDir in Get-ChildItem -LiteralPath $root -Directory -Force) {
                $userSkills = Join-Path $profileDir.FullName '.doubaowork/agent_mode/workspace/.user_skills'
                if (-not (Test-Path -LiteralPath $userSkills -PathType Container)) { continue }
                foreach ($skill in $CoreSkills) {
                    $target = Join-Path $userSkills $skill
                    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
                    Copy-Item -LiteralPath (Join-Path (Join-Path (Join-Path $toolkitDir 'skills') 'core') $skill) -Destination $target -Recurse -Force
                }
                foreach ($skill in $CoreSkills) {
                    if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $userSkills $skill) 'SKILL.md') -PathType Leaf)) {
                        Stop-Install "$skill is missing from $userSkills after the copy"
                    }
                }
                $installedProfiles++
                Write-Log "DoubaoWork: core skills copied to $userSkills"
            }
        }
        if ($installedProfiles -eq 0) {
            Stop-Install 'No DoubaoWork user skill directory found. Open DoubaoWork once so it creates its workspace, then rerun.'
        }
        Add-Verified 'doubao-work' $true ''
        Write-Log 'DoubaoWork: restart the app or open a new task to load the skills.'
    }

    function Install-WithSkillsCli([string]$Name) {
        if (-not (Test-Command 'npx')) { Stop-Install "'npx' is not on PATH. Install Node.js, then rerun with -Agent $Name." }
        $arguments = @('--yes', 'skills', 'add', $installSource, '--global', '--yes', '--copy', '--full-depth', '--skill') +
            $CoreSkills + @('--agent', $Name)
        Invoke-Host "npx skills add for agent $Name" 'npx' $arguments
        Add-Verified $Name (Test-ListsCoreSkills (Get-HostOutput 'npx' @('--yes', 'skills', 'list', '--global', '--agent', $Name))) 'skills-not-listed'
        Write-Log "${Name}: core skills installed through the skills CLI. Start a new session to load them."
    }

    foreach ($name in $agents) {
        switch -Regex ($name) {
            '^(claude|claude-code)$' { Install-ForClaude; break }
            '^codex$' { Install-ForCodex; break }
            '^(gemini|gemini-cli)$' { Install-ForGemini; break }
            '^(trae-cli|coco)$' { Install-ForTraeCli; break }
            '^(doubao-work|doubaowork)$' { Install-ForDoubaoWork; break }
            default { Install-WithSkillsCli $name }
        }
    }

    Write-Output "SOURCE=$Source"
    Write-Output "VERSION=$toolkitVersion"
    Write-Output "TOOLKIT_DIR=$toolkitDir"
    Write-Output "INSTALL_SOURCE=$installSource"
    Write-Output "AGENT=$($agents -join ',')"
    Write-Output "VERIFIED=$($script:verified -join ',')"
    # A host that cannot see the install is a failed install, whatever the
    # exit codes above said.
    foreach ($entry in $script:verified) {
        if (-not $entry.EndsWith(':ok')) {
            $hostName, $reason = $entry -split ':', 2
            Stop-Install "Installed, but $hostName does not list the core skills ($reason). Check that host's own install state."
        }
    }

    if ($agents.Count -eq 0) {
        Write-Log ''
        Write-Log 'Install the core plugin for your host:'
        Write-Log ''
        Write-Log '  Claude Code:'
        Write-Log "    claude plugin marketplace add `"$installSource`""
        Write-Log "    claude plugin install $CorePlugin"
        Write-Log ''
        Write-Log '  Codex:'
        Write-Log "    codex plugin marketplace add `"$installSource`""
        Write-Log "    codex plugin add $CorePlugin"
        Write-Log ''
        Write-Log '  Other hosts (skills CLI; add --agent <name> to target one host):'
        Write-Log "    npx skills add `"$installSource`" --global --yes --copy --full-depth --skill $($CoreSkills -join ' ')"
        Write-Log ''
        Write-Log 'Or rerun this installer with -Agent <name>[,<name>], for example -Agent claude,codex.'
    }
} finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
    if ($stagingDir -and (Test-Path -LiteralPath $stagingDir)) { Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue }
}
} catch {
    Write-Log "$($_.Exception.Message)"
    # Only a script file may set the process exit code; piped code must return.
    if ($PSCommandPath) { exit 1 }
}
