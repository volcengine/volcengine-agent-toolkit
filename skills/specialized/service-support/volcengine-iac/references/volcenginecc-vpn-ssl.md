# Volcenginecc SSL VPN Example

Verified example path:

```text
assets/examples/volcenginecc-vpn-ssl/main.tf
```

Use this example when a deployment needs Terraform-managed SSL VPN remote-access entry into a VPC. The verified shape creates a minimal VPC, a pay-as-you-go VPN gateway with SSL enabled, and one SSL VPN server. It intentionally does not create SSL client certificates because those resources return private key material into Terraform state.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpn_vpn_gateway` | VPC-side VPN gateway with SSL VPN enabled |
| `volcenginecc_vpn_ssl_vpn_server` | SSL VPN server configuration for remote clients |
| `volcenginecc_vpc_vpc` / `volcenginecc_vpc_subnet` / `volcenginecc_vpc_route_table` | Minimal network prerequisites |

## Verified command sequence

The example shape was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vpn-ssl
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

Observed final verification result: VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, VPN gateway `vgw-<vpn-gateway-id>`, and SSL VPN server `vss-<ssl-vpn-server-id>` were created. Follow-up plan returned `No changes`.

Destroy removed all five resources. Final Terraform state was empty, and cloud-side checks returned `TotalCount: 0` for `DescribeVpnGateways --VpnGatewayName cc-iac-vpn-ssl-current-gateway` and `DescribeVpcs --VpcName cc-iac-vpn-ssl-current-vpc`.

## Pitfalls found during verification

1. `client_ip_pool` must not overlap `local_subnets`. The first attempt used `client_ip_pool = "172.30.200.0/26"` with `local_subnets = ["172.30.0.0/16"]`, and create failed:

```text
EventTime: 2026-05-30T13:41:39+08:00
TaskID: task-<id>
InvalidRequest: InvalidSslVpnClientIpPool.Conflict: The specified ClientIpPool conflicts with that of local subnets.
TypeName: Volcengine::VPN::SslVpnServer
Operation: CREATE
OperationStatus: FAILED
```

2. The verified shape uses `client_ip_pool = "10.250.0.0/26"` and `local_subnets = ["172.30.0.0/16"]` to keep client addresses separate from reachable VPC CIDRs.

3. The VPN gateway must have `ssl_enabled = true` and a nonzero `ssl_max_connections` before creating `volcenginecc_vpn_ssl_vpn_server`. The verified baseline disables IPsec with `ipsec_enabled = false` so the example only exercises SSL VPN.

4. `volcenginecc_vpn_ssl_vpn_client_cert` returns `client_key`, client certificate, CA certificate, and OpenVPN client configuration as read-only attributes. Terraform will store that private key material in state, so keep client certificates out of shared default examples unless the workflow explicitly accepts encrypted, access-controlled state and certificate rotation.

5. VPN gateway creation is slow compared with VPC resources. In verification, the SSL-enabled gateway took about 3m6s to create, SSL VPN server creation took about 16s, SSL VPN server deletion took about 6s, and gateway deletion took about 15s.

## Import IDs

```bash
terraform import volcenginecc_vpn_vpn_gateway.main <vpn_gateway_id>
terraform import volcenginecc_vpn_ssl_vpn_server.main <ssl_vpn_server_id>
```
