# Volcenginecc VPN Example

Verified example path:

```text
assets/examples/volcenginecc-vpn/main.tf
```

Use this example when a deployment needs Terraform-managed site-to-site IPsec VPN primitives for a VPC. The verified shape creates a minimal VPC, a pay-as-you-go single-tunnel VPN gateway, a customer gateway placeholder, an IPsec connection, and a static VPN gateway route.

For SSL VPN remote-access entry, use [`volcenginecc-vpn-ssl.md`](./volcenginecc-vpn-ssl.md). Keep the IPsec and SSL examples separate because IPsec needs a PSK, while SSL client certificates can write private key material into Terraform state.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpn_vpn_gateway` | VPC-side IPsec VPN gateway |
| `volcenginecc_vpn_customer_gateway` | Remote peer gateway metadata |
| `volcenginecc_vpn_vpn_connection` | IPsec tunnel definition |
| `volcenginecc_vpn_vpn_gateway_route` | Static route through the IPsec connection |
| `volcenginecc_vpc_vpc` / `volcenginecc_vpc_subnet` / `volcenginecc_vpc_route_table` | Minimal network prerequisites |

## Verified command sequence

The example shape was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vpn
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_vpn_psk='replace-with-a-strong-psk'
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy
```

Observed final verification result: VPC `vpc-<id>`, customer gateway `cgw-<customer-gateway-id>`, VPN gateway `vgw-<vpn-gateway-id>`, IPsec connection `vgc-<vpn-connection-id>`, and VPN gateway route `vgr-<vpn-route-id>` were created. Follow-up plan returned `No changes`.

Destroy removed all seven resources. Final Terraform state was empty, and cloud-side checks returned `TotalCount: 0` for `DescribeVpnGateways --VpnGatewayName cc-iac-vpn-gateway`, `DescribeCustomerGateways --CustomerGatewayName cc-iac-vpn-customer`, `DescribeVpnConnections --VpnConnectionName cc-iac-vpn-connection`, and `DescribeVpcs --VpcName cc-iac-vpn-vpc`.

## Pitfalls found during verification

1. `volcenginecc_vpn_customer_gateway.asn` should be set explicitly for clean plans. Omitting it created the resource, but the next plan wanted an update because `asn` was treated as computed.

2. Avoid `tags` on `volcenginecc_vpn_customer_gateway` with provider `0.0.46` if no-op convergence matters. The API/provider did not read configured tags back in the first attempt, so the follow-up plan wanted an in-place update. The verified example keeps tags on VPC and VPN gateway, but not on customer gateway.

3. A customer gateway `ip_address = "0.0.0.0"` works for a generic reusable example only when the IPsec connection is passive and uses IKEv1 aggressive mode. Keep `negotiate_instantly = false`, `ike_config.version = "ikev1"`, `ike_config.mode = "aggressive"`, and both IKE IDs as `0.0.0.0`.

4. The IPsec PSK is passed through sensitive variable `vpn_psk`. Terraform will still store sensitive values in state; never commit state, plan files, or `.terraform` directories from this example.

5. `volcenginecc_vpn_ssl_vpn_server` is verified separately in [`volcenginecc-vpn-ssl.md`](./volcenginecc-vpn-ssl.md). Its `client_ip_pool` must not overlap `local_subnets`.

6. `volcenginecc_vpn_ssl_vpn_client_cert` returns `client_key`, client certificate, CA certificate, and OpenVPN client config as read-only state. Do not add it to shared default examples unless the workflow explicitly accepts secret material in Terraform state.

7. VPN gateway creation is slow compared with VPC resources. In verification, gateway creation took about 2 to 3 minutes, IPsec connection creation about 36 seconds, and route creation about 16 seconds.

## Import IDs

```bash
terraform import volcenginecc_vpn_vpn_gateway.main <vpn_gateway_id>
terraform import volcenginecc_vpn_customer_gateway.remote <customer_gateway_id>
terraform import volcenginecc_vpn_vpn_connection.ipsec <vpn_connection_id>
terraform import volcenginecc_vpn_vpn_gateway_route.remote <vpn_gateway_route_id>
```
