# Volcenginecc Private NAT Example

Verified example path:

```text
assets/examples/volcenginecc-private-nat/main.tf
```

Use this example when a Volcengine deployment needs private NAT and transit IPs for private address translation. It creates a minimal VPC, subnet, route table, private NAT gateway, and one extra NAT IP.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_natgateway_ngw` | Private NAT gateway when `network_type = "intranet"` |
| `volcenginecc_natgateway_nat_ip` | Additional private NAT transit IP from the NAT gateway subnet |

The VPC, subnet, and route table are included only to keep the example self-contained. For real deployments, reuse the network foundation from `volcenginecc-network`.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-private-nat
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform apply
terraform plan -detailed-exitcode -input=false
terraform destroy
```

Observed apply result: 5 resources created successfully, including private NAT gateway and one non-default NAT IP. A follow-up plan returned `No changes`. Destroy removed all 5 resources and final state was empty.

Observed IDs in the verification account:

```text
nat_gateway_id = ngw-<id>
nat_ip_id      = vpcnatip-<id>
```

## Pitfalls found during verification

1. Private NAT requires `network_type = "intranet"` and `billing_type = 3`. The public NAT example uses `network_type = "internet"` and `billing_type = 2`; do not reuse those values for `natgateway_nat_ip`.

2. `volcenginecc_natgateway_nat_ip` requires a private NAT gateway ID. It is not valid against a public NAT gateway.

3. Omitting `nat_ip` lets the platform allocate an available address from the NAT subnet. This produced a clean no-op plan and avoids hardcoding an IP that may already be occupied.

4. A private NAT gateway automatically creates a default transit IP. Adding `volcenginecc_natgateway_nat_ip` creates an additional NAT IP; the gateway readback then includes both the default IP and the Terraform-managed IP.

5. Destroy order matters. Let Terraform delete `natgateway_nat_ip` first, then the private NAT gateway, route table, subnet, and VPC. Manual cleanup should follow the same order.

## Import IDs

```bash
terraform import volcenginecc_natgateway_ngw.private ngw-xxxxxxxx
terraform import volcenginecc_natgateway_nat_ip.main vpcnatip-xxxxxxxx
```
