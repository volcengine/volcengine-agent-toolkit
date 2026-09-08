# Volcenginecc DirectConnect Example

Verified example path:

```text
assets/examples/volcenginecc-directconnect/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed Direct Connect gateway as the cloud-side entry point for dedicated-line or hybrid-network connectivity.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_directconnect_direct_connect_gateway` | Cloud-side Direct Connect gateway |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_directconnect_virtual_interface` | External dependency blocked | Requires a real physical dedicated line ID. |
| `volcenginecc_directconnect_gateway_route` | Dependency-blocked | Requires a Direct Connect gateway plus a valid VIF, CEN, or TransitRouter next hop. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-directconnect
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

Observed apply result: Direct Connect gateway `cc-iac-dc-retry-gw` created successfully with ID `dcg-<directconnect-gateway-id>`. A follow-up plan returned `No changes`. Destroy removed the gateway, final Terraform state was empty, and `ve directconnect DescribeDirectConnectGateways --body '{"DirectConnectGatewayName":"cc-iac-dc-retry-gw"}'` returned `TotalCount: 0`.

Observed timings in `cn-beijing`: Direct Connect gateway create took about 37 seconds. Destroy took about 36 seconds.

## Pitfalls found during verification

1. `directconnect:CreateDirectConnectGateway` permission is required. Earlier attempts failed at the permission boundary before any gateway ID was created.

2. Omitting `bgp_asn` is valid for the baseline. The service read back the Volcengine default ASN `137718` and the follow-up plan stayed clean.

3. Keep the baseline untagged with provider `0.0.46` unless tags are required. The untagged shape produced a clean no-op plan.

4. Do not add virtual interfaces to generic examples without a real physical dedicated line ID. Fake IDs would only prove parameter validation failure, not a usable deployment path.

## Import IDs

```bash
terraform import volcenginecc_directconnect_direct_connect_gateway.main <direct-connect-gateway-id>
```
