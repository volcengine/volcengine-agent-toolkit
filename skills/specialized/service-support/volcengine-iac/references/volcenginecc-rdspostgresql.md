# Volcenginecc RDS PostgreSQL Example

Verified example path:

```text
assets/examples/volcenginecc-rdspostgresql/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed PostgreSQL instance, application database, account, schema, private CIDR allowlist, custom private endpoint, and manual logical database backup.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_rdspostgresql_instance` | Managed PostgreSQL instance for application state |
| `volcenginecc_rdspostgresql_db_account` | Application database account |
| `volcenginecc_rdspostgresql_database` | Application database inside the instance |
| `volcenginecc_rdspostgresql_schema` | Application schema owned by the app account |
| `volcenginecc_rdspostgresql_allow_list` | Private CIDR allowlist for database access |
| `volcenginecc_rdspostgresql_db_endpoint` | Custom private endpoint for workload-specific database access |
| `volcenginecc_rdspostgresql_backup` | Manual logical database backup |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependency for the instance |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-rdspostgresql
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_postgres_password=...
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -input=false
```

Observed apply result: VPC, subnet, route table, allowlist, PostgreSQL instance, database account, database, schema, custom private endpoint, and manual logical backup created successfully. A follow-up plan returned `No changes` after the account privilege ordering and backup field fixes below. Destroy removed all 10 resources after backend association cleanup and final state was empty.

Observed timings in `cn-beijing`: PostgreSQL instance create took about 7m18s, custom endpoint create about 29s, logical backup create about 17s, backup delete about 5s, endpoint delete about 16s. Destroy of the database resources completed first, but cleanup needed retries while the RDS backend released exclusive status, allowlist association, and subnet ENI.

## Pitfalls found during verification

1. `account_privileges` reads back as `Inherit,Login`. Use that order in `volcenginecc_rdspostgresql_db_account`; `Login,Inherit` applies but causes persistent no-op plan drift.

2. `user_allow_list` is a string field, not a Terraform set/list. Use a comma-separated string only if multiple CIDRs are required.

3. Instance creation is slow. The verified small HA instance in `cn-beijing-a` took about 7m18s.

4. Destroy can fail immediately after the instance delete with `OperationDenied.AllowListIdInuse` or `InvalidSubnet.InUse`. Wait for backend cleanup and rerun `terraform destroy`; the retry succeeded after about 90 seconds.

5. Passwords are sensitive in plan output but still stored in Terraform state. Keep `postgres_password` as a sensitive variable and never commit state files.

6. A first `terraform init` attempt in the temporary verification directory failed with a provider checksum `operation not permitted` error. Removing `.terraform` and retrying `terraform init -backend=false -input=false` fixed it.

7. Creating the database immediately after custom endpoint creation can fail with `OperationFailWithReason: The operation fails due to instance is in exclusive status.` Wait about 120 seconds and rerun apply; the retry created the database and schema successfully.

8. `volcenginecc_rdspostgresql_backup` should omit `backup_type` for the verified logical database backup. Setting `backup_type = "Full"` with `backup_method = "Logical"` and `backup_scope = "Database"` failed with `InvalidParameter: The value of the specified parameter BackupType or BackupMethod is not valid.`

9. The custom endpoint verified cleanly with `private_addresses.domain_prefix`, unlike the MySQL endpoint drift case. Follow-up plan returned `No changes`.

## Import IDs

```bash
terraform import volcenginecc_rdspostgresql_instance.main <instance-id>
terraform import volcenginecc_rdspostgresql_db_account.app <instance-id>|<account-name>
terraform import volcenginecc_rdspostgresql_database.app <instance-id>|<database-name>
terraform import volcenginecc_rdspostgresql_schema.app <instance-id>|<database-name>|<schema-name>
terraform import volcenginecc_rdspostgresql_allow_list.app <allow-list-id>
terraform import volcenginecc_rdspostgresql_db_endpoint.custom <instance-id>|<endpoint-id>
terraform import volcenginecc_rdspostgresql_backup.manual <backup-id>|<instance-id>
```
