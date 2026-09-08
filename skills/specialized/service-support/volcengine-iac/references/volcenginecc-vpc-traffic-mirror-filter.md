# Volcenginecc VPC Traffic Mirror Filter Example

Verified example path:

```text
assets/examples/volcenginecc-vpc-traffic-mirror-filter/main.tf
```

Use this example when a deployment needs reusable traffic mirror filter conditions before wiring mirror sessions to ECS ENIs or CLB targets. Pair it with `volcenginecc-vpc-traffic-mirror-target` for a verified private-CLB mirror destination. Mirror sessions still require an ECS source ENI on a supported instance family and remain tracked in `volcenginecc-blocked.md`.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpc_traffic_mirror_filter` | Container for ingress/egress traffic mirror filtering rules |
| `volcenginecc_vpc_traffic_mirror_filter_rule` | Per-direction match rule selecting mirrored traffic |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vpc-traffic-mirror-filter
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform apply -auto-approve -input=false
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
terraform state list
```

Observed apply result: traffic mirror filter `tmf-<traffic-mirror-filter-id>` and ingress rule `tmr-<traffic-mirror-rule-id>` were created successfully. A follow-up plan returned `No changes`. Destroy removed both resources and final state was empty.

## Pitfalls found during verification

1. Filter and filter rule can be verified independently. Use `volcenginecc-vpc-traffic-mirror-target` when you need a verified CLB mirror target, but keep `volcenginecc_vpc_traffic_mirror_session` out of generic examples until a supported ECS source instance family is selected.

2. A standalone ENI is not enough for a mirror target. A previous attempt with a standalone target ENI failed with `InvalidEni.InstanceMismatch` because the ENI was not attached to an instance.

3. A CLB mirror target can be created from a private CLB ID and now has a clean no-op verified example. That still does not prove session support: a later retry with an attached ECS primary ENI and CLB target failed at session creation because the ECS source instance type `ecs.g4i.large` does not currently support traffic mirror.

4. For `tcp` or `udp` rules, set both `source_port_range` and `destination_port_range` in `start/end` form. Omitting ports is only appropriate for `all` or `icmp` protocol rules.

5. Priority values must be unique within the same filter and direction. Use a high, explicit value such as `100` for examples so product teams can reserve lower priorities for more specific rules.

6. Filter readback includes rule details under the parent filter. Keep the rule as a separate Terraform resource; do not try to manage `ingress_filter_rules` or `egress_filter_rules` directly because they are read-only on `volcenginecc_vpc_traffic_mirror_filter`.

## Import IDs

```bash
terraform import volcenginecc_vpc_traffic_mirror_filter.app tmf-xxxxxxxx
terraform import volcenginecc_vpc_traffic_mirror_filter_rule.ingress_http tmf-xxxxxxxx|tmr-xxxxxxxx
```
