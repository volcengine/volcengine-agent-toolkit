# TOS S3-Compatible Backend

Default state backend for this skill. Stores Terraform state in a Volcengine TOS bucket using Terraform's built-in `s3` backend with custom endpoints.

## Why TOS, not local

Local backend works for single-developer workflows but loses durability and prevents collaboration. TOS gives us:

- Versioned state (enable bucket versioning)
- Cross-machine access via Volcengine credentials
- Compatible with Terraform's `s3` backend (no third-party plugin needed)

## What is **not** supported

**State locking through the Terraform `s3` backend is unavailable for TOS.** Volcengine TOS does not provide a Terraform `s3` backend lock table equivalent. Consequences:

- Two `terraform apply` runs against the same state at the same time can corrupt it.
- Mitigation 1 (small team): coordinate via chat / a shared `LOCK` file in the bucket / scheduled deploy windows.
- Mitigation 2 (larger team): use Terraform Cloud / Enterprise (paid) which provides locking via its own API.
- Mitigation 3: enforce single-CI-runner pattern (only the CI service account can apply; humans only `plan`).

## Bucket prerequisites

Create the bucket once per project manually or with `tosutil`. The current Volcengine CLI build may not expose a `ve tos` service, so do not generate `ve tos` commands for backend setup.

```bash
tosutil mb "tos://<PROJECT>-tfstate" -acl=private -sc=STANDARD

# If versioning is required, enable it through the TOS console, API, or another verified tool.
# Do not assume `tosutil` or `ve` exposes a bucket-versioning command in the current environment.
```

> The bucket itself **cannot** be managed by this skill's iac (chicken-and-egg: the state for that bucket would need to live somewhere). Create it manually.

## backend.tf template

The skill writes this template into the user's working directory:

```hcl
terraform {
  backend "s3" {
    bucket = "<PROJECT>-tfstate"
    key    = "<PROJECT>/<WORKSPACE>/terraform.tfstate"
    region = "cn-beijing"

    endpoints = {
      s3 = "https://tos-s3-cn-beijing.volces.com"
    }

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}
```

Do not set `force_path_style` or `use_path_style` for TOS here. Terraform then lists workspace state with a path-style prefix and TOS can reject it with `InvalidPathAccess`.

The `s3` endpoint is region-specific. Map common regions:

| Region | endpoint |
|---|---|
| cn-beijing | https://tos-s3-cn-beijing.volces.com |
| cn-shanghai | https://tos-s3-cn-shanghai.volces.com |
| cn-guangzhou | https://tos-s3-cn-guangzhou.volces.com |
| ap-southeast-1 | https://tos-s3-ap-southeast-1.volces.com |

For other regions, consult the TOS documentation. Use `tosutil ls` or `tosutil stat tos://<bucket>` only to verify access to an existing bucket; endpoint selection still comes from the region's documented S3-compatible TOS endpoint.

## Credentials

Terraform's `s3` backend reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`; those are backend variable names, not the cloud service being used. Map Volcengine creds before `terraform init`:

```bash
export AWS_ACCESS_KEY_ID="$VOLCENGINE_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$VOLCENGINE_SECRET_KEY"
export AWS_EC2_METADATA_DISABLED=true
terraform init
```

The skill's wrapper scripts (`check_drift.sh`) do this mapping automatically. For ad-hoc `terraform` invocations, run the export pair yourself.

## Workspace strategy

```bash
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod
terraform workspace select prod
```

The state path key (`<PROJECT>/<WORKSPACE>/terraform.tfstate`) automatically incorporates the workspace name, so each environment has an isolated state file inside the same bucket.

## Local fallback

If the user has no TOS bucket and does not want to create one, omit `backend.tf` entirely. Terraform falls back to a local `terraform.tfstate` file. Add to `.gitignore`:

```text
*.tfstate
*.tfstate.backup
.terraform/
.terraform.lock.hcl
```

The `iac-outputs.json` written by `export_outputs.sh` contains sensitive values (kubeconfig, DB credentials) and **must** also be in `.gitignore`.
