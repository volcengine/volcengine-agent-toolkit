# Volcenginecc CBR Example

Verified example path:

```text
assets/examples/volcenginecc-cbr/main.tf
```

Use this example when a deployment needs a Cloud Backup (CBR) vault and a backup policy. Backup resources and plans that attach real ECS/vePFS sources are not included.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_cbr_vault` | Backup repository |
| `volcenginecc_cbr_backup_policy` | Disabled incremental backup schedule |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-cbr
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The vault and disabled policy created, returned a clean `No changes` follow-up plan, and destroyed with empty final state.

## Pitfalls found during verification

1. The account must be entitled to CBR (`cbr:CreateVault`, `cbr:CreateBackupPolicy`). Without it, create fails with `AccessDenied`.

2. The generated provider docs show resource name `volcenginecc_cbr_backuppolicy`; the actual Terraform resource type is `volcenginecc_cbr_backup_policy`.

3. Keep `enable_policy = false` for low-impact validation. `volcenginecc_cbr_backup_resource` and `volcenginecc_cbr_backup_plan` are not included because they require a real ECS or vePFS backup source.

## Import IDs

```bash
terraform import volcenginecc_cbr_vault.app vault-xxxxxxxx
terraform import volcenginecc_cbr_backup_policy.app policy-xxxxxxxx
```
