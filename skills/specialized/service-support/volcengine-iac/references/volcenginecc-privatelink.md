# Volcenginecc PrivateLink Example

Verified example path:

```text
assets/examples/volcenginecc-privatelink/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed Interface PrivateLink path from a consumer VPC to a private CLB-backed service.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_privatelink_endpoint_service` | Interface endpoint service backed by a private CLB |
| `volcenginecc_privatelink_vpc_endpoint` | Consumer-side interface endpoint |
| `volcenginecc_clb_clb` | Private CLB service resource |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table`, `volcenginecc_vpc_security_group` | Service and consumer network prerequisites |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_privatelink_vpc_endpoint_connection` | Not required for auto-accepted baseline | Creating the endpoint against an auto-accept endpoint service automatically produced a `Connected` endpoint. Use the connection resource only when you need explicit connection/resource-allocation management. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-privatelink
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

Observed apply result: endpoint service `epsvc-<endpoint-service-id>` was created for private CLB `clb-<id>`, then endpoint `ep-<endpoint-id>` connected from a second VPC. A follow-up plan returned `No changes`; `ve privatelink DescribeVpcEndpoints --body '{"EndpointName":"cc-iac-pl-retry-endpoint"}'` showed the endpoint `ConnectionStatus = "Connected"`.

Destroy removed endpoint, endpoint service, CLB, security group, route tables, subnets, and both VPCs. Final Terraform state was empty. `DescribeVpcEndpointServices` for the service ID returned `TotalCount: 0`, `DescribeVpcEndpoints` for the endpoint ID no longer returned the endpoint, `ve clb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-pl-retry-clb"}'` returned `TotalCount: 0`, and exact VPC-name matching for both temporary VPCs returned no rows.

Observed timings in `cn-beijing`: endpoint service create took about 29 seconds after CLB creation; endpoint create took about 15 seconds. Destroy of the full stack took about 50 seconds.

## Pitfalls found during verification

1. `privatelink:CreateVpcEndpointService` permission is required. Earlier attempts failed at the permission boundary after the private CLB had already been created.

2. Keep `private_dns_enabled = false` for the baseline. Enabling Private DNS adds public-domain verification fields and DNS ownership workflow.

3. `auto_accept_enabled = true` plus `permit_account_ids = ["*"]` is enough for a same-account baseline endpoint to connect automatically. No explicit `volcenginecc_privatelink_vpc_endpoint_connection` resource was needed for the verified path.

4. VPC security-group creation can hit a transient `InvalidOperation.Conflict` immediately after VPC creation. Rerunning `terraform apply` after the VPC settles succeeded.

5. Keep the baseline untagged with provider `0.0.46` unless tags are required. The untagged shape produced a clean no-op plan.

## Import IDs

```bash
terraform import volcenginecc_privatelink_endpoint_service.main <service-id>
terraform import volcenginecc_privatelink_vpc_endpoint.main <endpoint-id>
terraform import volcenginecc_privatelink_vpc_endpoint_connection.main <service-id>|<endpoint-id>
```
