# Volcenginecc Network Example

Verified example path:

```text
assets/examples/volcenginecc-network/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed network foundation for ECS, VKE, RDS, Redis, load balancers, or private dependencies.

For subnet ACLs, prefix lists, standalone ENIs, HAVIPs, and shared bandwidth packages, use the companion verified example [`assets/examples/volcenginecc-vpc-extras/main.tf`](../assets/examples/volcenginecc-vpc-extras/main.tf) and notes in [`volcenginecc-vpc-extras.md`](./volcenginecc-vpc-extras.md). For private NAT and additional transit IPs, use [`assets/examples/volcenginecc-private-nat/main.tf`](../assets/examples/volcenginecc-private-nat/main.tf) and notes in [`volcenginecc-private-nat.md`](./volcenginecc-private-nat.md).

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpc_vpc` | Isolated network for compute, managed databases, caches, and load balancers |
| `volcenginecc_vpc_subnet` | AZ-scoped placement for ECS, VKE nodes, NAT, ALB/CLB, RDS, Redis |
| `volcenginecc_vpc_route_table` | Explicit subnet route table association |
| `volcenginecc_vpc_security_group` | Inbound/outbound policy for ECS and other ENI-backed services |
| `volcenginecc_vpc_eip` | Standalone public IP or public IP bound to NAT/ECS/CLB |
| `volcenginecc_natgateway_ngw` | Public NAT gateway for private-subnet outbound internet |
| `volcenginecc_natgateway_snatentry` | SNAT rule for subnet outbound internet through NAT EIP |
| `volcenginecc_natgateway_dnatentry` | DNAT rule mapping a NAT EIP port to a private target IP and port |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-network
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: 10 resources created successfully, then no-op plan returned `No changes`, then destroy removed all 10 resources.

## Pitfalls found during verification

1. Do not copy every attribute from registry examples. Several generated examples include read-only fields such as `associate_cens`, `route_table_ids`, `security_group_ids`, and `nat_gateway_ids`. Keep resource blocks to writable schema fields unless a field is explicitly required.

2. Use real AZ IDs for subnets. The generated `vpc_subnet` doc shows `zone_id = "cn-beijing"`, but subnet creation needs an AZ such as `cn-beijing-a` or `cn-beijing-b`.

3. Avoid setting `support_ipv_4_gateway` on `volcenginecc_vpc_vpc` unless the workload explicitly needs it and you have tested it in that region. During verification, setting `support_ipv_4_gateway = true` created the VPC but read back as `false`, causing the next plan to replace the VPC.

4. Serialize early VPC child resources when Cloud Control reports conflicts. Creating security group concurrently with subnet/route-table work failed once with `InvalidOperation.Conflict`. Adding `depends_on = [volcenginecc_vpc_route_table.app]` to the security group made retry succeed.

5. Security group rules are inline `SetNestedAttribute` blocks. Fully define every nested field used by the provider, including `direction`, `prefix_list_id`, and `source_group_id`. Incomplete set items can cause unnecessary diffs or update instability.

6. A newly created security group may get a default egress rule from the platform. If the desired egress rule differs in priority/description, the next plan can update the security group. The example uses a fully specified egress rule and was no-op after one converged apply.

7. SNAT needs an EIP already bound to the NAT gateway. Creating `volcenginecc_natgateway_snatentry` with an unbound EIP failed with `InvalidEip.InstanceMismatch`. Bind the EIP by setting `instance_id = volcenginecc_natgateway_ngw.public.nat_gateway_id` and `instance_type = "Nat"` on `volcenginecc_vpc_eip`.

8. Do not set `direct_mode` while binding a previously unbound EIP to NAT. Updating the unbound EIP with `direct_mode = true` failed with `InvalidDirectModeEip.InvalidStatus: Only attached EIP support modifying direct mode`. Let the NAT gateway report `direct_mode` as read-only.

9. DNAT uses the NAT EIP public address, not the EIP allocation ID. Set `external_ip = volcenginecc_vpc_eip.nat.eip_address`; keep `external_port` and `internal_port` as strings.

10. DNAT can be created for a private IP in the NAT subnet even when no ECS is currently attached to that IP. The verified example maps `external_port = "8080"` to `internal_ip = "10.88.1.10"` and `internal_port = "80"` only to validate Terraform/API shape. For a real deployment, replace `internal_ip` with the ECS primary private IP or ENI private IP.

11. NAT state has short consistency windows after EIP/SNAT/DNAT changes. Initial DNAT create failed once with `InvalidNatGateway.InvalidStatus` immediately after NAT EIP binding and SNAT creation; rerunning plan/apply after the NAT reached `Available` succeeded. DNAT destroy also failed once with the same error after parallel SNAT deletion; waiting and rerunning `terraform destroy` succeeded.

12. NAT/SNAT/DNAT destroy order matters. Let Terraform infer the dependency from `dnatentry/snatentry -> eip.nat -> natgateway`. Manual cleanup should delete DNAT and SNAT first, then release/unbind NAT EIP, then delete NAT gateway, route table, subnets, and VPC.

## Import IDs

```bash
terraform import volcenginecc_vpc_vpc.main vpc-xxxxxxxx
terraform import volcenginecc_vpc_subnet.primary subnet-xxxxxxxx
terraform import volcenginecc_vpc_route_table.app vtb-xxxxxxxx
terraform import volcenginecc_vpc_security_group.app sg-xxxxxxxx
terraform import volcenginecc_vpc_eip.standalone eip-xxxxxxxx
terraform import volcenginecc_natgateway_ngw.public ngw-xxxxxxxx
terraform import volcenginecc_natgateway_snatentry.subnet_primary snat-xxxxxxxx
terraform import volcenginecc_natgateway_dnatentry.http_test dnat-xxxxxxxx
```
