# Volcenginecc Redis Public Address Example

Verified example path:

```text
assets/examples/volcenginecc-redis-public-address/main.tf
```

Use this example only when a deployment deliberately needs Redis public network access. The baseline Redis example keeps Redis private; public Redis should be treated as an exception with a narrow allowlist and a dedicated EIP.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_redis_endpoint_public_address` | Public Redis endpoint bound to a dedicated EIP |
| `volcenginecc_vpc_eip` | Dedicated public IP for the Redis public endpoint |

The example also includes a minimal VPC, subnet, route table, Redis allowlist, and Redis instance so it can be verified independently.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-redis-public-address
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_redis_password='use-a-real-secret'
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform apply
terraform plan -detailed-exitcode -input=false
terraform destroy
```

Observed apply result: VPC, subnet, route table, EIP, Redis allowlist, Redis instance, and Redis public endpoint created successfully. A follow-up plan returned `No changes`. Destroy removed all 7 resources and final state was empty.

Observed IDs in the verification account:

```text
instance_id             = redis-<id>
eip_id                  = eip-<id>
public_endpoint_address = redis-<id>.redis.volces.com
```

Observed timings: EIP create about 16s, Redis allowlist create about 11s, Redis instance create about 3m19s, public endpoint create about 46s, public endpoint destroy about 16s, EIP destroy about 21s, Redis instance destroy about 38s.

## Pitfalls found during verification

1. Redis passwords remain in Terraform state even when the variable is sensitive. Do not commit state or plan files, and prefer encrypted remote state with strict access control.

2. Keep the Redis allowlist narrow. The verified example uses `allow_list = "127.0.0.1"` so the public endpoint exists but is not reachable from arbitrary clients. Do not combine public Redis with `0.0.0.0/0` in examples.

3. `new_address_prefix` must be globally unique, lowercase, 8-53 characters, start with a letter, and end with a letter or number. Change the sample value before reuse in a shared account.

4. Use a dedicated EIP. After public endpoint creation, the EIP reads back as attached to a Redis-managed network interface. Destroy must delete `redis_endpoint_public_address` before the EIP can be released.

5. Do not set `upgrade_region_domain = true` unless the deployment intentionally accepts domain-suffix migration behavior. The verified example leaves it omitted.

## Import IDs

```bash
terraform import volcenginecc_redis_endpoint_public_address.main '<instance-id>|<eip-id>'
terraform import volcenginecc_vpc_eip.redis eip-xxxxxxxx
```
