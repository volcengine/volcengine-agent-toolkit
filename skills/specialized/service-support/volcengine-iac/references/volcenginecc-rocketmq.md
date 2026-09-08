# Volcenginecc RocketMQ Example

Verified example path:

```text
assets/examples/volcenginecc-rocketmq/main.tf
```

Use this example when a deployment needs a managed RocketMQ instance with a private IP allowlist, a topic, and a consumer group.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_rocketmq_instance` | Pay-as-you-go RocketMQ 4.8 instance bound to a VPC/subnet |
| `volcenginecc_rocketmq_topic` | Topic on the instance |
| `volcenginecc_rocketmq_group` | Consumer group on the instance |
| `volcenginecc_rocketmq_allow_list` | IPv4 access allowlist |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependencies |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`:

```bash
cd assets/examples/volcenginecc-rocketmq
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The full stack (VPC, subnet, route table, allowlist, instance, topic, group) created, returned a clean `No changes` follow-up plan, and destroyed with empty final state. Instance creation took about 2m40s.

## Pitfalls found during verification

1. The account must be entitled to RocketMQ. Without entitlement, `CreateInstance` fails with `AccessDenied`.

2. `compute_spec` must be a valid product specification code; the CLI/provider does not expose the matrix. For RocketMQ `4.8`, names use an `n` prefix (compute node count), smallest is `rocketmq.n1.x2.micro`. `version = "5.x"` requires a separate whitelist application.

3. `storage_space` is in GiB, in multiples of 100, and its valid range depends on `compute_spec`. `rocketmq.n1.x2.micro` accepts `300`. Storage sizing rule of thumb: usable storage = message volume * 3 replicas / 0.75.

4. `network_types` is fixed to `PrivateNetwork`; the instance binds one `vpc_id` + `subnet_id` and cannot change them after creation.

5. The generated provider docs show resource name `volcenginecc_rocketmq_allowlist`; the actual Terraform resource type is `volcenginecc_rocketmq_allow_list`.

6. `group_id` must be 7-120 characters of letters, numbers, hyphens, and underscores; starting with `GID_` or `GID-` is recommended.

## Import IDs

```bash
terraform import volcenginecc_rocketmq_allow_list.app acl-xxxxxxxx
terraform import volcenginecc_rocketmq_instance.main rocketmq-xxxxxxxx
terraform import volcenginecc_rocketmq_topic.app "rocketmq-xxxxxxxx|topic-name"
terraform import volcenginecc_rocketmq_group.app "rocketmq-xxxxxxxx|GID_xxxx"
```
