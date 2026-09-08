# Volcenginecc PrivateZone Example

Verified example path:

```text
assets/examples/volcenginecc-privatezone/main.tf
```

Use this example when ECS, VKE, RDS, Redis, or other VPC workloads need private DNS names such as `app.svc.internal`.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_privatezone_private_zone` | Private DNS zone associated with one or more VPCs |
| `volcenginecc_privatezone_record` | Private DNS record inside the zone |

The example includes a minimal VPC, two subnets, and a route table so it can be validated independently. In real deployments, wire the private zone to the verified network foundation instead of creating a separate VPC.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-privatezone
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy
```

Observed apply result: VPC, two subnets, route table, private zone `svc.internal`, and A record `app.svc.internal -> 10.97.1.10` were created successfully. A targeted no-op plan for the created resources returned `No changes`. Destroy removed all resources and final state was empty.

## Pitfalls found during verification

1. `volcenginecc_privatezone_record.zid` is a number, while `private_zone.zid` reads back as a string. Use `tonumber(volcenginecc_privatezone_private_zone.main.zid)`.

2. Do not set `weight_enabled = true` unless load balancing is actually needed and verified. The API accepted it, but `record_sets.weight_enabled` read back as `false`. The verified committed example omits weight fields for a clean simple record.

3. Associate the private zone with a real VPC using a fully specified `vpcs` object (`vpc_id` and `region`). Private DNS only takes effect in associated VPCs.

4. Add the private zone only after the VPC route table/subnet associations are ready. The verified example uses `depends_on = [volcenginecc_vpc_route_table.app]` to avoid early VPC consistency windows.

5. `privatezone_resolver_endpoint`, `privatezone_resolver_rule`, and `privatezone_user_vpc_authorization` were not fully verified in the current account. See `volcenginecc-blocked.md` before using them.

## Import IDs

```bash
terraform import volcenginecc_privatezone_private_zone.main <zid>
terraform import volcenginecc_privatezone_record.app <record_id>
```
