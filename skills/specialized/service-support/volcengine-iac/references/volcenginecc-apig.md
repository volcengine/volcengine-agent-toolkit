# Volcenginecc APIG Example

Verified example path:

```text
assets/examples/volcenginecc-apig/main.tf
```

Use this example when a deployment needs a Terraform-managed API Gateway private entry point in front of services. The verified shape intentionally avoids public exposure, monitoring, logging, trace credentials, custom domains, and upstream bindings.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_apig_gateway` | Standard APIG gateway in a VPC |
| `volcenginecc_apig_gateway_service` | Private HTTP gateway service and default private access domain |
| `volcenginecc_vpc_vpc` / `volcenginecc_vpc_subnet` | Minimal network prerequisites |

## Verified command sequence

The example shape was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-apig
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

Observed apply result: a private standard APIG gateway was created in about 2 minutes, then a private HTTP gateway service was created in about 20 seconds. The verified final example created gateway `gd8d586vu6t11adlipnv0`, service `sd8d5961fd34tq15s4u8g`, and private default domain `http://sd8d5961fd34tq15s4u8g.apigateway-cn-beijing-inner.volceapi.com`. Follow-up plan returned `No changes`.

Destroy removed the gateway service and gateway. The VPC subnet deletion initially failed because APIG service-managed ENIs were still being released, and VPC deletion then failed because two APIG-created security groups remained. After the ENIs disappeared and the two temporary `apig-sg-*` security groups were deleted, Terraform destroy removed the VPC and final state was empty. Cloud-side checks returned no gateway, no gateway service, and no temporary VPC.

## Pitfalls found during verification

1. For a private-only gateway, omit `resource_spec.clb_spec_code` and `resource_spec.public_network_billing_type`. Supplying `small_1` and `bandwidth` while `enable_public_network = false` created the gateway, but refresh read both fields back as empty strings and the next plan forced replacement.

2. `public_network_bandwidth = 0` is stable for private-only gateways. Keep `network_type.enable_public_network = false` and `network_type.enable_private_network = true` for a private entry point.

3. Do not enable `trace_spec.tls_trace_spec` in reusable examples. The generated docs include `iam_user_ak` and `iam_user_sk`, which would put credentials in Terraform config and state.

4. `volcenginecc_apig_upstream` planned successfully with a Domain upstream, but apply failed because the current account is not in the whitelist:

```text
EventTime: 2026-05-30T10:56:42+08:00
TaskID: task-<id>
AccessDenied: OperationDenied.AccountNotInWhitelist: Operation is denied because the account is not in the whitelist.
TypeName: Volcengine::APIG::Upstream
Operation: CREATE
OperationStatus: FAILED
```

5. `volcenginecc_apig_custom_domain` needs a real custom domain and, for HTTPS, an APIG certificate ID. Keep it out of the default example unless domain ownership and certificate lifecycle are part of the deployment.

6. Destroy can need a recovery pass. If subnet deletion fails with `InvalidSubnet.InUse` after gateway deletion, wait and check `ve vpc DescribeNetworkInterfaces --SubnetId <subnet_id>`. If VPC deletion then fails with security-group dependencies, delete only the APIG-created security groups in the temporary VPC (`apig-sg-*`) and rerun `terraform destroy`.

## Import IDs

```bash
terraform import volcenginecc_apig_gateway.main <gateway_id>
terraform import volcenginecc_apig_gateway_service.app <service_id>
```
