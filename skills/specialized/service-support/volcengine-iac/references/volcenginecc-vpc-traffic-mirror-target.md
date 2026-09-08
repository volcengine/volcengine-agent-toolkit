# Volcenginecc VPC Traffic Mirror Target Example

Verified example path:

```text
assets/examples/volcenginecc-vpc-traffic-mirror-target/main.tf
```

Use this example when a deployment needs a Terraform-managed traffic mirror target backed by a private Classic Load Balancer. Pair it with `volcenginecc-vpc-traffic-mirror-filter` when preparing traffic mirror sessions.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpc_traffic_mirror_target` | Mirror destination that receives copied traffic |
| `volcenginecc_clb_clb` | Private CLB used as the mirror target backend |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network prerequisites |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vpc-traffic-mirror-target
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -auto-approve -input=false
terraform state list
```

Observed apply result: VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, private CLB `clb-<id>`, and traffic mirror target `tmt-<traffic-mirror-target-id>` were created successfully. A follow-up plan returned `No changes`. Destroy removed all 5 resources, final Terraform state was empty, and cloud-side lookups by VPC/CLB name returned `TotalCount: 0`.

Observed timings in `cn-beijing`: VPC create about 10s, subnet about 21s, route table about 10s, private CLB about 10s, mirror target about 11s. Destroy removed the mirror target in about 10s, CLB in about 6s, route table in about 15s, subnet in about 7s, and VPC in about 6s.

## Pitfalls found during verification

1. For a generic verified example, prefer `instance_type = "ClbInstance"` and a private CLB target. A standalone ENI target failed with `InvalidEni.InstanceMismatch` because the ENI was not attached to an ECS instance.

2. This verifies only the mirror target lifecycle. `volcenginecc_vpc_traffic_mirror_session` still requires a mirror-source ECS ENI on an instance family that supports traffic mirroring; `ecs.g4i.large` was rejected with `InvalidInstanceSpecification.Malformed`.

3. Use `volcenginecc_clb_clb.load_balancer_id` as the target `instance_id`, not the Terraform `id` by assumption. They matched in verification, but the explicit exported field is clearer and follows the provider schema.

4. Keep `master_zone_id` and `slave_zone_id` different for the private CLB. The verified pair was `cn-beijing-a` and `cn-beijing-b`.

5. The private CLB target shape avoids public EIP allocation. If switching to a public CLB, verify billing and cleanup separately.

## Import IDs

```bash
terraform import volcenginecc_vpc_traffic_mirror_target.clb tmt-xxxxxxxx
terraform import volcenginecc_clb_clb.target clb-xxxxxxxx
```
