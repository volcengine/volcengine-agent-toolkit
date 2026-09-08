# Volcenginecc RabbitMQ Example

Verified example path:

```text
assets/examples/volcenginecc-rabbitmq/main.tf
```

Use this example when a deployment needs a managed RabbitMQ instance with a private IP allowlist.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_rabbitmq_instance` | Pay-as-you-go RabbitMQ instance bound to a VPC/subnet |
| `volcenginecc_rabbitmq_allow_list` | IPv4 access allowlist |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependencies |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`:

```bash
cd assets/examples/volcenginecc-rabbitmq
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_rabbitmq_password='<complex-password>'
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The stack (VPC, subnet, route table, allowlist, instance) created, returned a clean `No changes` follow-up plan, and destroyed with empty final state.

## Pitfalls found during verification

1. The account must be entitled to RabbitMQ. Without entitlement, instance creation fails with `AccessDenied: OperationDenied.AccountNotAuthorized`.

2. `user_name` and `user_password` must satisfy RabbitMQ rules or create fails with `InvalidParameter: The specified parameter Name or PassWord is not valid.` `user_name = "appadmin"` was rejected; `ccrabbituser` worked. Use a password that meets complexity requirements.

3. `user_password` is sensitive in plan output but is still stored in Terraform state. Pass it through `TF_VAR_rabbitmq_password`; do not hardcode it.

4. The generated provider docs/example show resource name `volcenginecc_rabbitmq_allowlist`; the actual Terraform resource type is `volcenginecc_rabbitmq_allow_list`.

## Import IDs

```bash
terraform import volcenginecc_rabbitmq_allow_list.app acl-xxxxxxxx
terraform import volcenginecc_rabbitmq_instance.main rbtmq-xxxxxxxx
```
