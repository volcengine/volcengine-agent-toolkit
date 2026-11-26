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
#                            doubao-work and workbuddy get the core skills
#                            copied into their user skill directory; any other
#                            name (cursor, qoder, opencode, trae, trae-cn, ...)
#                            is passed to `npx skills add --agent`, and `other`,
#                            or a name the skills CLI does not know, installs
#                            for every host it detects. A host whose own
#                            command is not on PATH is installed through the
#                            skills CLI too. Without -Agent the script only
#                            prints the commands to run.
#   -Source <auto|github|cdn>  auto (default) probes GitHub.
#   -Dir <dir>               Local toolkit directory for the CDN path.
#   -Version <ver>           Install this released version. Released versions
#                            exist only on the CDN, so this selects the CDN.
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
# A failure that another download source cannot fix: a missing tool, a host
# directory that does not exist. Its exception type tells the retry loop not to
# try the CDN, which would bury the real error under an unrelated one.
function Stop-InstallLocal([string]$Message) {
    throw [System.InvalidOperationException]::new("ERROR: $Message")
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
    if ($text -match '^[0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.+-]*$') { return $text }
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
# Download sources
# ---------------------------------------------------------------------------
# GitHub is preferred. The CDN package is used when GitHub does not answer, and
# again when an install from GitHub fails part-way: the probe only shows that
# the GitHub website loads, while the hosts go on to clone the repository.
# Everything the install functions read and change lives in one object. A
# plain variable would not do: under `irm | iex` there is no script scope, so a
# function could not assign back to it.
$state = @{
    Source = $Source
    InstallSource = $GithubRepository
    ToolkitVersion = ''
    ToolkitUrl = ''
    ExpectedHash = ''
    CdnReady = $false
    StagingDir = $null
    Verified = @{}
    Current = ''
}
if ($Version) {
    if ($state.Source -eq 'github') {
        Stop-Install '-Version selects a released package, which only the CDN has. Drop -Source github, or drop -Version.'
    }
    if ($state.Source -eq 'auto') { $state.Source = 'cdn' }
}
$sourceForced = ($state.Source -ne 'auto')
if ($state.Source -eq 'auto') {
    if (Test-GithubReachable) {
        $state.Source = 'github'
    } else {
        Write-Log 'GitHub is not reachable from this host; using the Volcengine CDN.'
        $state.Source = 'cdn'
    }
}

$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("volcengine-toolkit-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

function Resolve-CdnManifest {
    if ($Version) {
        $wanted = ConvertTo-ToolkitVersion $Version
        if (-not $wanted) { Stop-Install "Invalid version '$Version' (expected e.g. 1.3.4)" }
        $manifestUrl = Join-Base $baseUrl "v$wanted/$ManifestName"
    } else {
        $manifestUrl = Join-Base $baseUrl "latest/$ManifestName"
    }
    $manifestPath = Join-Path $tempDir $ManifestName
    if (-not (Get-RemoteFile $manifestUrl $manifestPath)) {
        Stop-Install "Cannot read $manifestUrl. Check the network, or pass -Version <ver>."
    }
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Stop-Install "Malformed manifest at $manifestUrl"
    }
    $manifestVersion = if ($manifest.PSObject.Properties['version']) { [string]$manifest.version } else { '' }
    $resolvedVersion = ConvertTo-ToolkitVersion $manifestVersion
    if (-not $resolvedVersion) { Stop-Install "Unexpected version in ${manifestUrl}: '$manifestVersion'" }
    # Under strict mode a missing property throws a raw error with no ERROR: prefix.
    $toolkitNode = if ($manifest.PSObject.Properties['toolkit']) { $manifest.toolkit } else { $null }
    $url = if ($toolkitNode -and $toolkitNode.PSObject.Properties['url']) { [string]$toolkitNode.url } else { '' }
    $hash = if ($toolkitNode -and $toolkitNode.PSObject.Properties['sha256']) { ([string]$toolkitNode.sha256).ToLowerInvariant() } else { '' }
    if (-not $url) { Stop-Install "No toolkit url in $manifestUrl" }
    if ($hash -notmatch '^[0-9a-f]{64}$') {
        Stop-Install "No usable sha256 in $manifestUrl. Refusing to install an unverified package."
    }
    # A manifest built without --cdn-base-url names the archive relative to itself.
    if ($url -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://' -and -not [IO.Path]::IsPathRooted($url)) {
        $url = Join-Base $baseUrl "v$resolvedVersion/$url"
    }
    $state.ToolkitVersion = $resolvedVersion
    $state.ToolkitUrl = $url
    $state.ExpectedHash = $hash
    $state.InstallSource = $toolkitDir
}

# Download, verify, unpack next to the target, then swap.
function Initialize-CdnToolkit {
    if ($state.CdnReady) { return }
    $installedVersion = ''
    $packageJson = Join-Path $toolkitDir 'package.json'
    if ((Test-ToolkitDir $toolkitDir) -and (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
        try {
            $installedVersion = [string](Get-Content -LiteralPath $packageJson -Raw -Encoding UTF8 | ConvertFrom-Json).version
        } catch { }
    }

    if ($installedVersion -eq $state.ToolkitVersion) {
        Write-Log "Volcengine Agent Toolkit v$($state.ToolkitVersion) is already in $toolkitDir."
    } else {
        # A clone of the repository has the same layout as an unpacked package.
        # Replacing it would delete its history and any uncommitted work.
        if (Test-Path -LiteralPath (Join-Path $toolkitDir '.git')) {
            Stop-Install "$toolkitDir is a Git checkout, not an installed package. Pass -Dir <dir> to use another location."
        }
        if ((Test-Path -LiteralPath $toolkitDir) -and -not (Test-ToolkitDir $toolkitDir)) {
            # Never replace a directory this installer did not create.
            $isEmptyDir = (Test-Path -LiteralPath $toolkitDir -PathType Container) -and
                -not (Get-ChildItem -LiteralPath $toolkitDir -Force | Select-Object -First 1)
            if (-not $isEmptyDir) {
                Stop-Install "$toolkitDir exists and is not a Volcengine toolkit directory. Pass -Dir <dir> to use another location."
            }
        }

        $archivePath = Join-Path $tempDir $ArchiveName
        Write-Log "Downloading Volcengine Agent Toolkit v$($state.ToolkitVersion) ..."
        if (-not (Get-RemoteFile $state.ToolkitUrl $archivePath)) { Stop-Install "Download failed: $($state.ToolkitUrl)" }
        $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $state.ExpectedHash) {
            Stop-Install "Checksum mismatch for ${ArchiveName}: expected $($state.ExpectedHash), got $actualHash. The download may have been tampered with."
        }
        Write-Log 'Checksum OK.'

        $parentDir = Split-Path -Parent $toolkitDir
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        # Unpack beside the target so the final step is a rename on one volume.
        # A broken download must never replace a working toolkit.
        $state.StagingDir = "$toolkitDir.install.$PID"
        if (Test-Path -LiteralPath $state.StagingDir) { Remove-Item -LiteralPath $state.StagingDir -Recurse -Force }
        New-Item -ItemType Directory -Path $state.StagingDir -Force | Out-Null
        Expand-Toolkit $archivePath $state.StagingDir
        if (-not (Test-ToolkitDir $state.StagingDir)) {
            Stop-Install "$ArchiveName does not contain the expected toolkit layout. Existing install left untouched."
        }

        $previousDir = $null
        if (Test-Path -LiteralPath $toolkitDir) {
            $previousDir = "$toolkitDir.previous.$PID"
            if (Test-Path -LiteralPath $previousDir) { Remove-Item -LiteralPath $previousDir -Recurse -Force }
            Move-Item -LiteralPath $toolkitDir -Destination $previousDir
        }
        try {
            Move-Item -LiteralPath $state.StagingDir -Destination $toolkitDir
        } catch {
            if ($previousDir) { Move-Item -LiteralPath $previousDir -Destination $toolkitDir }
            Stop-Install "Cannot move the toolkit into $toolkitDir. Existing install left untouched."
        }
        $state.StagingDir = $null
        if ($previousDir) { Remove-Item -LiteralPath $previousDir -Recurse -Force }
        Write-Log "Volcengine Agent Toolkit v$($state.ToolkitVersion) unpacked to $toolkitDir"
    }
    $state.CdnReady = $true
}

try {
    if ($state.Source -eq 'cdn') { Resolve-CdnManifest }

    if ($DryRun) {
        Write-Output "SOURCE=$($state.Source)"
        Write-Output "VERSION=$($state.ToolkitVersion)"
        Write-Output "TOOLKIT_URL=$($state.ToolkitUrl)"
        Write-Output "TOOLKIT_DIR=$toolkitDir"
        Write-Output "INSTALL_SOURCE=$($state.InstallSource)"
        return
    }

    if ($state.Source -eq 'cdn') { Initialize-CdnToolkit }

    # Hosts that are installed by copying files need the core skills on disk.
    # From the CDN that is the toolkit directory; from GitHub it is the default
    # branch's source archive, unpacked into the temporary directory.
    function Get-CoreSkillsDir {
        if ($state.Source -eq 'cdn') {
            return (Join-Path (Join-Path $toolkitDir 'skills') 'core')
        }
        $githubSrc = Join-Path $tempDir 'github-src'
        $existing = Get-ChildItem -LiteralPath $githubSrc -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $existing) {
            $githubArchive = Join-Path $tempDir 'github-src.zip'
            Write-Log 'Downloading the toolkit source from GitHub ...'
            try {
                Invoke-WebRequest -Uri "$githubUrl/archive/HEAD.zip" -OutFile $githubArchive -UseBasicParsing -TimeoutSec 300 | Out-Null
            } catch {
                Stop-Install "Download failed: $githubUrl/archive/HEAD.zip"
            }
            New-Item -ItemType Directory -Path $githubSrc -Force | Out-Null
            Expand-Archive -LiteralPath $githubArchive -DestinationPath $githubSrc -Force
            $existing = Get-ChildItem -LiteralPath $githubSrc -Directory | Select-Object -First 1
        }
        $coreDir = if ($existing) { Join-Path (Join-Path $existing.FullName 'skills') 'core' } else { '' }
        if (-not $coreDir -or -not (Test-Path -LiteralPath $coreDir -PathType Container)) {
            Stop-Install 'The GitHub source archive has no skills/core directory'
        }
        return $coreDir
    }

    # -----------------------------------------------------------------------
    # Host registration
    # -----------------------------------------------------------------------
    # Each host is asked afterwards whether it can see what was installed, so
    # the caller gets a verified result from this one command.
    function Set-Verified([string]$Name, [bool]$Ok, [string]$Reason) {
        # Keyed by the name the caller passed, so results come out in that order.
        $state.Verified[$state.Current] = if ($Ok) { "${Name}:ok" } else { "${Name}:$Reason" }
        # Thrown so that the caller can retry from the CDN; see the loop below.
        if (-not $Ok) { throw "NOT-LISTED: $Name" }
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

    # Copy the core skills into a host's own skill directory.
    function Copy-CoreSkills([string]$Destination) {
        $coreDir = Get-CoreSkillsDir
        foreach ($skill in $CoreSkills) {
            if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $coreDir $skill) 'SKILL.md') -PathType Leaf)) {
                Stop-Install "$skill is missing from the downloaded source"
            }
        }
        foreach ($skill in $CoreSkills) {
            $target = Join-Path $Destination $skill
            $staging = Join-Path (Split-Path -Parent $Destination) ('.skill-install.' + [Guid]::NewGuid().ToString('N'))
            $previous = Join-Path $staging 'previous'
            $installedSkill = $false
            try {
                New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null
                $stagedSkill = Join-Path $staging $skill
                Copy-Item -LiteralPath (Join-Path $coreDir $skill) -Destination $stagedSkill -Recurse -Force -ErrorAction Stop
                if (-not (Test-Path -LiteralPath (Join-Path $stagedSkill 'SKILL.md') -PathType Leaf)) {
                    throw "$skill is missing from the staged copy"
                }
                if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $previous -ErrorAction Stop }
                try {
                    Move-Item -LiteralPath $stagedSkill -Destination $target -ErrorAction Stop
                    $installedSkill = $true
                } catch {
                    if (Test-Path -LiteralPath $previous) { Move-Item -LiteralPath $previous -Destination $target -ErrorAction Stop }
                    throw
                }
            } catch {
                $failureMessage = "Cannot install $skill into ${Destination}: $_"
                if (-not $installedSkill -and (Test-Path -LiteralPath $previous)) {
                    $failureMessage += ". Previous Skill preserved at $previous"
                }
                Stop-InstallLocal $failureMessage
            } finally {
                if ((Test-Path -LiteralPath $staging) -and ($installedSkill -or -not (Test-Path -LiteralPath $previous))) {
                    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
        }
        foreach ($skill in $CoreSkills) {
            if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $Destination $skill) 'SKILL.md') -PathType Leaf)) {
                Stop-Install "$skill is missing from $Destination after the copy"
            }
        }
    }

    # $SkillsAgent is the agent name for the skills CLI, or '' to let it install
    # for every host it detects plus the shared ~/.agents/skills directory.
    function Install-WithSkillsCli([string]$SkillsAgent, [string]$Label) {
        if (-not (Test-Command 'npx')) { Stop-InstallLocal "'npx' is not on PATH. Install Node.js, then rerun with -Agent $Label." }
        # On Windows, prefer npx.cmd: the npx.ps1 shim can be blocked by the execution policy.
        $npx = if ($OnWindows -and (Test-Command 'npx.cmd')) { 'npx.cmd' } else { 'npx' }
        $addArguments = @('--yes', 'skills', 'add', $state.InstallSource, '--global', '--yes', '--copy', '--full-depth', '--skill') + $CoreSkills
        if ($SkillsAgent) {
            # The skills CLI prints a long report. It is shown only on failure,
            # so that the result lines at the end stay visible in a host's tool output.
            $added = Invoke-NativeCommand $npx ($addArguments + @('--agent', $SkillsAgent))
            if (($added.Output -join "`n").Contains('Invalid agents')) {
                # A name the skills CLI does not know is not a failed install:
                # fall back to installing for every host it detects.
                Write-Log "The skills CLI does not know the agent '$SkillsAgent'; installing for every host it detects instead."
                $SkillsAgent = ''
            } elseif ($added.ExitCode -ne 0) {
                $added.Output | ForEach-Object { Write-Log $_ }
                Stop-Install "npx skills add failed for agent $SkillsAgent"
            }
        }
        if (-not $SkillsAgent) {
            $added = Invoke-NativeCommand $npx $addArguments
            if ($added.ExitCode -ne 0) {
                $added.Output | ForEach-Object { Write-Log $_ }
                Stop-Install 'npx skills add failed'
            }
            $listing = Get-HostOutput $npx @('--yes', 'skills', 'list', '--global')
        } else {
            $listing = Get-HostOutput $npx @('--yes', 'skills', 'list', '--global', '--agent', $SkillsAgent)
        }
        Write-Log "${Label}: core skills installed through the skills CLI. Start a new session to load them."
        Set-Verified $Label (Test-ListsCoreSkills $listing) 'skills-not-listed'
    }

    # A host whose own CLI is not on PATH is still served: desktop builds often
    # ship without the command, and the host reads the same user skill directory.
    function Install-ForClaude {
        if (-not (Test-Command 'claude')) {
            Write-Log "'claude' is not on PATH; installing the core skills for Claude Code through the skills CLI."
            Install-WithSkillsCli 'claude-code' 'claude'
            return
        }
        # Adding an already known marketplace repoints it at this source.
        Invoke-Host "claude plugin marketplace add $($state.InstallSource)" 'claude' @('plugin', 'marketplace', 'add', $state.InstallSource)
        Invoke-Host "claude plugin install $CorePlugin" 'claude' @('plugin', 'install', $CorePlugin)
        Write-Log "Claude Code: $CorePlugin installed. Run /reload-plugins in an open session, or start a new one."
        Set-Verified 'claude' ((Get-HostOutput 'claude' @('plugin', 'list')).Contains($CorePlugin)) 'plugin-not-listed'
    }

    function Install-ForCodex {
        if (-not (Test-Command 'codex')) {
            Write-Log "'codex' is not on PATH; installing the core skills for Codex through the skills CLI."
            Install-WithSkillsCli 'codex' 'codex'
            return
        }
        # Codex refuses a marketplace name that is bound to another source, so
        # drop the old binding and add this one.
        $added = Invoke-NativeCommand 'codex' @('plugin', 'marketplace', 'add', $state.InstallSource) -Log
        if ($added.ExitCode -ne 0) {
            Invoke-NativeCommand 'codex' @('plugin', 'marketplace', 'remove', $Marketplace) | Out-Null
            Invoke-Host "codex plugin marketplace add $($state.InstallSource)" 'codex' @('plugin', 'marketplace', 'add', $state.InstallSource)
        }
        # Codex copies the plugin into its own cache, so this also refreshes an upgrade.
        Invoke-Host "codex plugin add $CorePlugin" 'codex' @('plugin', 'add', $CorePlugin)
        Write-Log "Codex: $CorePlugin installed. Start a new session to load it."
        $codexLine = (Get-HostOutput 'codex' @('plugin', 'list')) -split "`n" | Where-Object { $_.Contains($CorePlugin) } | Select-Object -First 1
        Set-Verified 'codex' ([bool]($codexLine -and $codexLine.Contains('installed') -and -not $codexLine.Contains('not installed'))) 'plugin-not-listed'
    }

    function Install-ForGemini {
        if (-not (Test-Command 'gemini')) {
            Write-Log "'gemini' is not on PATH; installing the core skills for Gemini CLI through the skills CLI."
            Install-WithSkillsCli 'gemini-cli' 'gemini'
            return
        }
        foreach ($skill in $CoreSkills) {
            if ($state.Source -eq 'cdn') {
                # --path only applies to Git sources, so point at the skill directory.
                $skillDir = Join-Path (Join-Path (Join-Path $toolkitDir 'skills') 'core') $skill
                Invoke-Host "gemini skills install $skill" 'gemini' @('skills', 'install', $skillDir, '--consent')
            } else {
                Invoke-Host "gemini skills install $skill" 'gemini' @('skills', 'install', $githubUrl, '--path', "skills/core/$skill", '--consent')
            }
        }
        Write-Log 'Gemini CLI: core skills installed. Restart Gemini CLI to load them.'
        Set-Verified 'gemini' (Test-ListsCoreSkills (Get-HostOutput 'gemini' @('skills', 'list'))) 'skills-not-listed'
    }

    function Install-ForTraeCli {
        $traeBin = @('coco', 'traecli', 'trae-agent') | Where-Object { Test-Command $_ } | Select-Object -First 1
        if (-not $traeBin) {
            Write-Log 'Trae CLI (coco, traecli, or trae-agent) is not on PATH; installing the core skills for Trae through the skills CLI.'
            Install-WithSkillsCli 'trae' 'trae-cli'
            return
        }
        # Trae CLI names a marketplace after its directory unless told otherwise, and
        # keeps an existing name bound to its old source, so rebind it explicitly.
        # It will not remove a marketplace that still has a plugin installed
        # from it, so drop the plugin first.
        Invoke-NativeCommand $traeBin @('plugin', 'uninstall', 'volcengine-core') | Out-Null
        Invoke-NativeCommand $traeBin @('plugin', 'marketplace', 'remove', $Marketplace) | Out-Null
        $type = if ($state.Source -eq 'cdn') { 'local' } else { 'github' }
        $added = Invoke-NativeCommand $traeBin @('plugin', 'marketplace', 'add', $state.InstallSource, '--name', $Marketplace, '--type', $type) -Log
        if ($added.ExitCode -ne 0) {
            Stop-Install "$traeBin plugin marketplace add failed for $($state.InstallSource). If the marketplace is still bound to another source, run '$traeBin plugin uninstall volcengine-core' and '$traeBin plugin marketplace remove $Marketplace' in a terminal, then rerun."
        }
        Invoke-Host "$traeBin plugin install $CorePlugin" $traeBin @('plugin', 'install', $CorePlugin, '--type', 'marketplace', '--yes')
        Write-Log "Trae CLI: $CorePlugin installed. Start a new session to load it."
        Set-Verified 'trae-cli' ((Get-HostOutput $traeBin @('plugin', 'list')).Contains('volcengine-core')) 'plugin-not-listed'
    }

    # Doubao keeps user skills inside each browser profile, a location no
    # installer CLI knows about, so the core skills are copied there directly.
    # The standalone DoubaoWork app and the work mode built into the Doubao app
    # use different application directories and dot-directories; both are searched.
    function Get-DoubaoWorkRoots {
        foreach ($app in @('DoubaoWork', 'Doubao')) {
            if ($OnWindows) {
                if ($env:LOCALAPPDATA) { Join-Path (Join-Path $env:LOCALAPPDATA $app) 'User Data' }
                if ($env:APPDATA) { Join-Path $env:APPDATA $app }
            } elseif (Test-Path -LiteralPath (Join-Path $HOME 'Library/Application Support')) {
                Join-Path $HOME "Library/Application Support/$app"
            } else {
                $configHome = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME '.config' }
                Join-Path $configHome $app
            }
        }
    }

    function Install-ForDoubaoWork {
        $installedProfiles = 0
        foreach ($root in @(Get-DoubaoWorkRoots)) {
            if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
            foreach ($profileDir in Get-ChildItem -LiteralPath $root -Directory -Force) {
                foreach ($dotDir in @('.doubaowork', '.doubao')) {
                    $userSkills = Join-Path $profileDir.FullName "$dotDir/agent_mode/workspace/.user_skills"
                    if (-not (Test-Path -LiteralPath $userSkills -PathType Container)) { continue }
                    Copy-CoreSkills $userSkills
                    $legacySkill = Join-Path $userSkills 'volcengine-cost'
                    if (Test-Path -LiteralPath $legacySkill) {
                        try {
                            $backupRoot = Join-Path (Split-Path -Parent $userSkills) '.skill-migration-backups'
                            $backup = Join-Path $backupRoot ('volcengine-cost.' + [Guid]::NewGuid().ToString('N'))
                            New-Item -ItemType Directory -Path $backup -Force -ErrorAction Stop | Out-Null
                            Move-Item -LiteralPath $legacySkill -Destination (Join-Path $backup 'volcengine-cost') -ErrorAction Stop
                            Write-Log "DoubaoWork: previous billing Skill backed up to $backup"
                        } catch {
                            Stop-Install "Cannot migrate the legacy billing Skill: $_"
                        }
                    }
                    $installedProfiles++
                    Write-Log "Doubao: core skills copied to $userSkills"
                }
            }
        }
        if ($installedProfiles -eq 0) {
            Stop-InstallLocal 'No Doubao user skill directory found. Start one task in Doubao work mode so it creates its workspace, then rerun.'
        }
        Write-Log 'Doubao: open a new task, or restart the app, to load the skills.'
        Set-Verified 'doubao-work' $true ''
    }

    # WorkBuddy reads user skills from ~/.workbuddy/skills, which the skills CLI
    # does not know, so the core skills are copied there directly.
    function Install-ForWorkBuddy {
        $workbuddyHome = Join-Path $HOME '.workbuddy'
        if (-not (Test-Path -LiteralPath $workbuddyHome -PathType Container)) {
            Stop-InstallLocal "No WorkBuddy directory found at $workbuddyHome. Open WorkBuddy once so it creates it, then rerun."
        }
        $workbuddySkills = Join-Path $workbuddyHome 'skills'
        New-Item -ItemType Directory -Path $workbuddySkills -Force | Out-Null
        Copy-CoreSkills $workbuddySkills
        Write-Log "WorkBuddy: core skills copied to $workbuddySkills. Start a new task to load them."
        Set-Verified 'workbuddy' $true ''
    }

    function Install-One([string]$Name) {
        switch -Regex ($Name) {
            '^(claude|claude-code)$' { Install-ForClaude; break }
            '^codex$' { Install-ForCodex; break }
            '^(gemini|gemini-cli)$' { Install-ForGemini; break }
            '^(trae-cli|coco)$' { Install-ForTraeCli; break }
            '^(doubao-work|doubaowork)$' { Install-ForDoubaoWork; break }
            '^workbuddy$' { Install-ForWorkBuddy; break }
            '^other$' { Install-WithSkillsCli '' 'other'; break }
            default { Install-WithSkillsCli $Name $Name }
        }
    }

    # A failed install from GitHub is retried from the CDN instead of ending the run.
    foreach ($name in $agents) {
        $state.Current = $name
        try {
            Install-One $name
        } catch {
            $failure = $_
            $isLocal = $failure.Exception -is [System.InvalidOperationException]
            if ($state.Source -eq 'github' -and -not $sourceForced -and -not $isLocal) {
                Write-Log "$($failure.Exception.Message)"
                Write-Log "Installing for $name from GitHub did not complete; retrying from the Volcengine CDN."
                Resolve-CdnManifest
                Initialize-CdnToolkit
                $state.Source = 'cdn'
                $state.Verified.Remove($name)
                try {
                    Install-One $name
                } catch {
                    if (-not "$($_.Exception.Message)".StartsWith('NOT-LISTED:')) { throw }
                }
            } elseif (-not "$($failure.Exception.Message)".StartsWith('NOT-LISTED:')) {
                throw
            }
        }
    }

    $verifiedList = @($agents | ForEach-Object { $state.Verified[$_] } | Where-Object { $_ })
    Write-Output "SOURCE=$($state.Source)"
    Write-Output "VERSION=$($state.ToolkitVersion)"
    Write-Output "TOOLKIT_DIR=$toolkitDir"
    Write-Output "INSTALL_SOURCE=$($state.InstallSource)"
    Write-Output "AGENT=$($agents -join ',')"
    Write-Output "VERIFIED=$($verifiedList -join ',')"
    # A host that cannot see the install is a failed install, whatever the
    # exit codes above said.
    foreach ($entry in $verifiedList) {
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
        Write-Log "    claude plugin marketplace add `"$($state.InstallSource)`""
        Write-Log "    claude plugin install $CorePlugin"
        Write-Log ''
        Write-Log '  Codex:'
        Write-Log "    codex plugin marketplace add `"$($state.InstallSource)`""
        Write-Log "    codex plugin add $CorePlugin"
        Write-Log ''
        Write-Log '  Other hosts (skills CLI; add --agent <name> to target one host):'
        Write-Log "    npx skills add `"$($state.InstallSource)`" --global --yes --copy --full-depth --skill $($CoreSkills -join ' ')"
        Write-Log ''
        Write-Log 'Or rerun this installer with -Agent <name>[,<name>], for example -Agent claude,codex.'
    }
} finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
    if ($state.StagingDir -and (Test-Path -LiteralPath $state.StagingDir)) { Remove-Item -LiteralPath $state.StagingDir -Recurse -Force -ErrorAction SilentlyContinue }
}
} catch {
    # Run as a file: report and set the exit code. Run as a script block or
    # through iex there is no file and `exit` would close the user's shell, so
    # rethrow instead: the caller sees a failed command, and the message still
    # starts with ERROR:.
    if ($PSCommandPath) {
        Write-Log "$($_.Exception.Message)"
        exit 1
    }
    throw
}
