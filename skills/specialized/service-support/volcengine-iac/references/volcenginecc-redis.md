# Volcenginecc Redis Example

Verified example path:

```text
assets/examples/volcenginecc-redis/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed Redis instance with a custom allowlist, parameter group, and application account.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_redis_instance` | Redis cache instance for application state, sessions, queues, or rate limits |
| `volcenginecc_redis_account` | Redis ACL account with a predefined role |
| `volcenginecc_redis_allow_list` | IP allowlist for Redis access |
| `volcenginecc_redis_parameter_group` | Custom Redis parameter group |

The example includes a minimal VPC, subnet, and route table so it can be validated independently. In real deployments, wire Redis to the verified network foundation instead of creating a separate VPC. For public Redis endpoints, use the companion verified example [`assets/examples/volcenginecc-redis-public-address/main.tf`](../assets/examples/volcenginecc-redis-public-address/main.tf) and notes in [`volcenginecc-redis-public-address.md`](./volcenginecc-redis-public-address.md).

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-redis
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_redis_password='use-a-real-secret'
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: VPC, subnet, route table, Redis allowlist, Redis parameter group, Redis instance, and Redis account created successfully. A follow-up plan returned `No changes`. Destroy removed all 7 resources and final state was empty.

Observed timings in `cn-beijing`: Redis instance creation took about 3m17s, Redis account creation about 16s, Redis instance deletion about 38s.

## Verified spec

The verified low-cost Redis spec is:

```hcl
engine_version  = "6.0"
shard_capacity  = 512
shard_number    = 1
node_number     = 1
sharded_cluster = 0
multi_az        = "disabled"
```

This maps to the Redis API spec list returned by:

```bash
ve redis DescribeDBInstanceSpecs --body '{}'
```

The relevant API response shape was `ArchType = "Standard"`, `InstanceClass = "Standalone"`, `ShardNumbers = [1]`, `NodeNumbers = [1]`, and `ShardCapacity = 512`.

## Pitfalls found during verification

1. The generated docs/example for parameter groups use the wrong resource type: `volcenginecc_redis_parametergroup`. Terraform rejects it. Use `volcenginecc_redis_parameter_group`.

2. Non-sharded Standalone Redis requires `shard_number = 1`. The first attempt used `shard_capacity = 256`, `shard_number = 2`, `node_number = 1`, `sharded_cluster = 0` and failed with `InvalidInstanceSpec: The specified instance spec does not exist`.

3. Query Redis specs before changing sizing. `ve redis DescribeDBInstanceSpecs --body '{}'` returns allowed `ArchType`, `InstanceClass`, `ShardNumbers`, `NodeNumbers`, and `ShardCapacitySpecs`. Do not infer valid combinations from docs alone.

4. The API uses `ArchType = "Standard"` for the basic non-cluster architecture. Passing `ArchType = "Basic"` to `DescribeDBInstanceSpecs` failed with `InvalidArchType`.

5. Redis passwords are marked sensitive in Terraform output, but Terraform state still stores password values. Do not commit `terraform.tfstate*`; delete throwaway verification directories after destroy.

6. `allow_list = "127.0.0.1"` means deny external access. Use it for safe examples. Replace it with specific CIDRs for real clients; avoid `0.0.0.0/0` unless explicitly required.

7. `redis_allow_list` can bind to instances through `instance_ids`, but the verified example binds the allowlist at instance creation via `allow_list_ids`. This avoids a separate update pass.

8. `redis_account.account_name` must start with a lowercase letter, end with a lowercase letter or number, be 2-16 characters, and contain only lowercase letters, numbers, and underscores.

## Import IDs

```bash
terraform import volcenginecc_redis_instance.main <instance-id>
terraform import volcenginecc_redis_account.app <instance-id>|<account-name>
terraform import volcenginecc_redis_allow_list.app <allow-list-id>
terraform import volcenginecc_redis_parameter_group.app <parameter-group-id>
```
