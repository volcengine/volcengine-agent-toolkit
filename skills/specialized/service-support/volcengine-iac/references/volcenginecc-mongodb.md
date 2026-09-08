# Volcenginecc MongoDB Example

Verified example path:

```text
assets/examples/volcenginecc-mongodb/main.tf
```

Use this example when a deployment needs a managed MongoDB ReplicaSet instance with a private IP allowlist.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_mongodb_instance` | Pay-as-you-go MongoDB ReplicaSet instance bound to a VPC/subnet |
| `volcenginecc_mongodb_allow_list` | IPv4 access allowlist |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependencies |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`:

```bash
cd assets/examples/volcenginecc-mongodb
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_mongodb_password='<complex-password>'
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The full stack (VPC, subnet, route table, allowlist, ReplicaSet instance) created, returned a clean `No changes` follow-up plan, and destroyed with empty final state. Instance creation took about 3m19s.

## Pitfalls found during verification

1. The account must be entitled to MongoDB (`mongodb:CreateAllowList` and `mongodb:CreateDBInstance`). Without it, allowlist creation fails with `AccessDenied`.

2. Discover specs before sizing: `ve mongodb DescribeNodeSpecs --body '{"RegionId":"cn-beijing"}'` returns node specs; `mongo.1c2g` is the minimal ReplicaSet node spec with `MinStorage = 20`. `storage_space_gb` must be at least the spec minimum.

3. `node_number = 3` for a ReplicaSet, `instance_type = "ReplicaSet"`, `db_engine_version = "MongoDB_7_0"`.

4. `super_account_password` is sensitive in plan output but is still stored in Terraform state. Pass it through `TF_VAR_mongodb_password`; do not hardcode it.

## Import IDs

```bash
terraform import volcenginecc_mongodb_allow_list.app acl-xxxxxxxx
terraform import volcenginecc_mongodb_instance.main mongo-replica-xxxxxxxx
```
