# Volcenginecc PrivateZone Resolver Example

Verified example path:

```text
assets/examples/volcenginecc-privatezone-resolver/main.tf
```

Use this example when a deployment needs a PrivateZone outbound resolver endpoint and a forwarding rule (for hybrid DNS resolution from a VPC to on-premises or another resolver).

## Prerequisite

The PrivateZone service-linked role must exist and be trusted before the resolver endpoint can be created. Create it once per account:

```bash
ve iam CreateServiceLinkedRole --ServiceName private_zone
```

Without it, endpoint creation fails with `ErrServiceNotTrusted: ServiceLinkedRole of private_zone is not trusted`.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_privatezone_resolver_endpoint` | Outbound IPv4 resolver endpoint across two AZs |
| `volcenginecc_privatezone_resolver_rule` | Outbound forwarding rule for a zone name |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet` (x2), `volcenginecc_vpc_route_table` | Two-AZ network dependencies |

## Verified command sequence

Verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, AZs `cn-beijing-a` and `cn-beijing-b`:

```bash
ve iam CreateServiceLinkedRole --ServiceName private_zone
cd assets/examples/volcenginecc-privatezone-resolver
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform init -backend=false -input=false
terraform validate
terraform apply -input=false -auto-approve
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

The endpoint (two AZs) and forwarding rule created, returned a clean `No changes` follow-up plan, and destroyed with empty final state.

## Pitfalls found during verification

1. Create the `private_zone` service-linked role first (see Prerequisite); otherwise the endpoint fails with `ErrServiceNotTrusted`.

2. The resolver endpoint needs `ip_configs` for at least two AZs, each with a `subnet_id` in that AZ and a free `ip` inside the subnet CIDR.

3. `volcenginecc_privatezone_resolver_rule.endpoint_id` is a number; the endpoint resource exposes `endpoint_id` as a string, so wrap it with `tonumber(...)`.

## Import IDs

```bash
terraform import volcenginecc_privatezone_resolver_endpoint.outbound <endpoint-id>
terraform import volcenginecc_privatezone_resolver_rule.outbound <rule-id>
```
