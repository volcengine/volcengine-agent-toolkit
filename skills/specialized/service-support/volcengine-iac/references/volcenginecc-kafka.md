# Volcenginecc Kafka Example

Verified example paths:

```text
assets/examples/volcenginecc-kafka/main.tf
assets/examples/volcenginecc-kafka-allow-list/main.tf
```

Use `volcenginecc-kafka` when a deployment needs a managed Kafka instance with a private allowlist and a topic. Use `volcenginecc-kafka-allow-list` when only a standalone access allowlist is needed.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_kafka_instance` | Pay-as-you-go Kafka instance bound to a VPC/subnet and an IP allowlist |
| `volcenginecc_kafka_topic` | Topic on the instance with partition/replica counts |
| `volcenginecc_kafka_allow_list` | IP access allowlist referenced by the instance |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependencies |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`:

```bash
cd assets/examples/volcenginecc-kafka
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The full stack (VPC, subnet, route table, allowlist, instance, topic) created, returned a clean `No changes` follow-up plan, and destroyed with empty final state.

## Pitfalls found during verification

1. The account must be entitled to Kafka. Without entitlement, instance creation fails with Cloud Control `ServiceInternalError: InternalError` rather than a clear permission message.

2. `storage_space` must be at least `300` for `compute_spec = "kafka.20xrate.hw"`. `storage_space = 100` fails with `InvalidParameter.DiskCapacity: The specified parameter DiskCapacity is not valid.`

3. The instance references the allowlist through `ip_white_list = [volcenginecc_kafka_allow_list.app.allow_list_id]`.

4. The generated provider docs/example show resource name `volcenginecc_kafka_allowlist`; the actual Terraform resource type is `volcenginecc_kafka_allow_list`.

5. `volcenginecc_kafka_topic` requires the instance to exist first; `partition_number = 3` and `replica_number = 3` were used for the verified topic.

## Import IDs

```bash
terraform import volcenginecc_kafka_allow_list.app acl-xxxxxxxx
terraform import volcenginecc_kafka_instance.main kafka-xxxxxxxx
terraform import volcenginecc_kafka_topic.app "kafka-xxxxxxxx|topic-name"
```
