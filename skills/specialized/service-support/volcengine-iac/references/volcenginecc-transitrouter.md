# Volcenginecc TransitRouter Example

Verified example path:

```text
assets/examples/volcenginecc-transitrouter/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed TransitRouter foundation before adding VPC, VPN, DirectConnect, or peer attachments.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_transitrouter_transit_router` | TransitRouter instance |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_transitrouter_transit_router_route_table` | Dependency-blocked | Requires a route-table design after the base router is verified. |
| `volcenginecc_transitrouter_vpc_attachment` | Dependency-blocked | Requires VPC/subnet attachment points and route behavior validation. |
| `volcenginecc_transitrouter_vpn_attachment` | Dependency-blocked | Requires a verified VPN connection. |
| `volcenginecc_transitrouter_peer_attachment` | Dependency/billable blocked | Requires two TransitRouters plus a bandwidth package. |
| `volcenginecc_transitrouter_transit_router_route_entry` | Dependency-blocked | Requires a route table and a valid attachment next hop. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-transitrouter
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
terraform state list
```

Observed apply result: TransitRouter `cc-iac-tr-retry` created successfully with ID `tr-<transit-router-id>`, `asn = 64512`, and `multicast_enabled = false`. A follow-up plan returned `No changes`. Destroy removed the router, final Terraform state was empty, and `ve transitrouter DescribeTransitRouters --body '{"TransitRouterName":"cc-iac-tr-retry"}'` returned `TotalCount: 0`.

Observed timings in `cn-beijing`: TransitRouter create took about 6 seconds. Destroy took about 6 seconds.

## Pitfalls found during verification

1. `transitrouter:CreateTransitRouter` permission is required. Earlier attempts failed at the permission boundary before any router ID was created.

2. Use `asn = 64512` for the reusable baseline. The provider and service both accepted it and the follow-up plan was clean.

3. Keep `multicast_enabled = false` unless multicast is a deliberate network-design requirement.

4. Attachments and peer connectivity should be verified separately. They introduce route propagation, subnet attachment points, VPN/DirectConnect dependencies, or billable cross-region bandwidth.

## Import IDs

```bash
terraform import volcenginecc_transitrouter_transit_router.main <transit-router-id>
```
