# Volcenginecc RDS MySQL Example

Verified example path:

```text
assets/examples/volcenginecc-rdsmysql/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed MySQL instance, database, application account, allowlist, and parameter template.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_rdsmysql_instance` | Managed MySQL instance for application state |
| `volcenginecc_rdsmysql_database` | Application database inside the instance |
| `volcenginecc_rdsmysql_db_account` | Application database account with scoped privileges |
| `volcenginecc_rdsmysql_allow_list` | Private CIDR allowlist for database access |
| `volcenginecc_rdsmysql_parameter_template` | Reusable MySQL parameter template |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependency for the instance |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_rdsmysql_endpoint` | Create/delete verified, no-op drift-blocked | A custom direct endpoint can be created and destroyed, but provider `0.0.46` readback omits `addresses.domain_prefix`; the next plan tries to update the endpoint and the API rejects it because the domain prefix already exists. Keep it out of default examples until a clean no-op plan is verified. |
| `volcenginecc_rdsmysql_backup` | API-blocked | Terraform `validate`/`plan` passed, but both documented `backup_method = "Physical"` and example-style `backup_method = "Logical"` failed during create with an invalid backup method error. Treat manual backups as unverified. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-rdsmysql
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_mysql_password=...
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -input=false
```

Observed apply result: VPC, subnet, route table, allowlist, parameter template, MySQL instance, database, and database account created successfully. A follow-up plan returned `No changes` after the drift fixes below. Destroy removed all 8 resources and final state was empty.

Observed timings in `cn-beijing`: parameter template create about 4s, allowlist create about 16s, VPC/subnet/route table about 42s total, MySQL instance create about 3m47s, database create about 4s, account create about 10s. Destroy took about 3m50s, with the instance deletion taking about 3m6s.

## Extra resource verification

`volcenginecc_rdsmysql_endpoint` was tested against the verified MySQL shape with a custom direct endpoint:

```hcl
resource "volcenginecc_rdsmysql_endpoint" "custom" {
  instance_id         = volcenginecc_rdsmysql_instance.main.instance_id
  endpoint_name       = "${local.prefix}-custom"
  endpoint_type       = "Custom"
  connection_mode     = "Direct"
  nodes               = "Primary"
  read_write_mode     = "ReadWrite"
  read_write_spliting = false

  addresses = [
    {
      domain_prefix  = "cciacmysql"
      dns_visibility = false
      port           = "3306"
    }
  ]
}
```

The endpoint created successfully as `mysql-ae90e8397914-custom-058a` and deleted cleanly. Do not add this to a reusable example yet: after the first read, Terraform planned an update because `domain_prefix` was missing from state readback, and the update failed with `OperationDenied_Common: domain prefix already exists`.

`volcenginecc_rdsmysql_backup` was tested with both documented/provider-example method values:

```hcl
resource "volcenginecc_rdsmysql_backup" "manual" {
  instance_id   = volcenginecc_rdsmysql_instance.main.instance_id
  backup_method = "Logical"
  backup_type   = "Full"
  backup_meta = [
    {
      database = volcenginecc_rdsmysql_database.app.name
      tables   = []
    }
  ]
}
```

`backup_method = "Physical"` and `backup_method = "Logical"` both planned successfully, then failed during create with `InvalidParameter: 参数BackupMethod值无效`. Leave manual backup creation out of generated examples until a working enum/API shape is verified.

## Pitfalls found during verification

1. `lower_case_table_names` docs say true/false, but the API rejected `"true"` with `InvalidParameter: 参数LowerCaseTableNames值无效。` The verified value is `"1"`.

2. Do not set `allow_list_desc` or `allow_list_category` in the stable example. They created successfully, but service readback omitted/normalized them and caused no-op plan drift.

3. Normal accounts automatically read back extra global privileges: `PROCESS`, `REPLICATION CLIENT`, and `REPLICATION SLAVE`. Include those in `account_privileges` to keep no-op plans clean.

4. Passwords are sensitive in plan output but still stored in Terraform state. Keep `mysql_password` as a sensitive variable and never commit state files.

5. The generated instance example includes a `ReadOnly` node while `instance_type = "DoubleNode"`. The verified minimal double-node shape uses only `Primary` and `Secondary`.

6. The generated docs call the app account resource `rdsmysql_db_account`; use `volcenginecc_rdsmysql_db_account`, not `rdsmysql_account`.

7. Immediately after instance creation, dependent database/account operations may hit a consistency window and fail with `InstanceIsNotRunning`. Waiting about 90 seconds and re-running apply succeeded during verification.

8. Destroy can hit the same status window. If account/database deletion fails with `NotStabilized: InstanceIsNotRunning`, wait for the instance to return to `Running` and rerun `terraform destroy`; the retry completed and final state was empty.

## Import IDs

```bash
terraform import volcenginecc_rdsmysql_instance.main <instance-id>
terraform import volcenginecc_rdsmysql_database.app <instance-id>|<database-name>
terraform import volcenginecc_rdsmysql_db_account.app <instance-id>|<account-name>|<host>
terraform import volcenginecc_rdsmysql_allow_list.app <allow-list-id>
terraform import volcenginecc_rdsmysql_parameter_template.app <template-id>
terraform import volcenginecc_rdsmysql_endpoint.custom <instance-id>|<endpoint-id>
terraform import volcenginecc_rdsmysql_backup.manual <instance-id>|<backup-id>
```
