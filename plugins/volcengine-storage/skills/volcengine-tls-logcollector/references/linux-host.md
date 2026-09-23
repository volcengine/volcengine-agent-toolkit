# Install LogCollector on a Linux host

Official guide: [Install LogCollector on a host](https://www.volcengine.com/docs/6470/72007)

Use this path only for supported 64-bit Linux hosts. LogCollector host packages do not imply native macOS or Windows support.

## Preflight

Run on the target host:

```bash
uname -s
uname -m
command -v systemctl
command -v wget
```

Confirm:

- Linux and a package matching `x86_64/amd64` or `aarch64/arm64`
- sufficient disk, CPU, memory, file permissions, and root/sudo access
- explicit region, TLS endpoint, and public/private network path
- network reachability to the package location and TLS endpoint
- the intended host group identity: Label by default, IP only when explicitly required
- an installation version selected by the user or verified in the current official guide

Do not guess a `latest` package. Before downloading, re-open the official guide and confirm the current URL, version, architecture support, and flags.

## Download and inspect

The public/private package URL pattern in the source workflow is:

```bash
wget "https://logcollector-<region>.tos-<region>.volces.com/logcollector.sh" \
  -O /tmp/logcollector.sh
```

For a private network, the official guide may use the corresponding `.ivolces.com` domain. Validate the final URL with `wget --spider` or an equivalent HTTP check, then inspect what was downloaded:

```bash
chmod 755 /tmp/logcollector.sh
file /tmp/logcollector.sh
/tmp/logcollector.sh --help
```

Use only flags reported by the downloaded version. Do not infer ARM support from an x86 package or run an unknown-architecture binary.

## Install with Label identity

Read credentials without echoing them, keep shell tracing disabled, and clear temporary environment variables afterward:

```bash
read -r -p "TLS AccessKey ID: " TLS_LOGCOLLECTOR_AK
read -r -s -p "TLS SecretKey: " TLS_LOGCOLLECTOR_SK
printf '\n'

sudo /tmp/logcollector.sh install \
  --region <region> \
  --endpoint <explicit-tls-endpoint> \
  --secret_id "${TLS_LOGCOLLECTOR_AK}" \
  --secret_key "${TLS_LOGCOLLECTOR_SK}" \
  --label <host-identifier> \
  --cpu <confirmed-cpu-limit> \
  --memory <confirmed-memory-limit>

unset TLS_LOGCOLLECTOR_AK TLS_LOGCOLLECTOR_SK
```

The resource examples are not production sizing defaults. Adjust CPU and memory for the expected collection volume and the current installer contract.

The `--label` value must match the selected host group's `HostIdentifier`. Use an IP installation flag only when the user explicitly selected an IP host group and the current installer help confirms the flag. Never set both label and IP identity.

## Verify locally

```bash
sudo systemctl is-active logcollectord.service
sudo systemctl status logcollectord.service --no-pager -l
/usr/local/logcollector/logcollector -v
file /usr/local/logcollector/logcollector
```

Then use [verification.md](verification.md) to prove heartbeat, binding, and Topic ingestion.

## Update or uninstall

Use only the lifecycle script shipped with the installed version and inspect its help first. Before an update, confirm the new version, architecture, identity, endpoint, and rollback path. Before stopping or uninstalling, confirm the exact host and collection impact.

Typical source-workflow paths are:

```bash
sudo /usr/local/logcollector/tools/logcollector.sh update_config --help
sudo /usr/local/logcollector/tools/logcollector.sh uninstall --help
```

Do not copy update or uninstall flags from another version without checking. If the installer reports that the service is still running, assess ingestion interruption and use its documented stop option only after the user confirms the impact.

## Troubleshooting order

1. package URL, HTTP reachability, and architecture
2. installer exit status and generated files
3. systemd unit and LogCollector process logs
4. endpoint, credential, region, network, and host identity
5. TLS host-group heartbeat
6. rule binding, source path/permissions, parser behavior, and Topic ingestion
