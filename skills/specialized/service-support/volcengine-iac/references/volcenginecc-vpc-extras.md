# Volcenginecc VPC Extras Example

Verified example path:

```text
assets/examples/volcenginecc-vpc-extras/main.tf
```

Use this example when a Volcengine deployment needs additional VPC primitives beyond the base network example: subnet ACLs, reusable CIDR sets, standalone ENIs, shared bandwidth packages, or HAVIPs for active/passive workloads.

For reusable traffic mirror filter conditions, use the companion verified example [`assets/examples/volcenginecc-vpc-traffic-mirror-filter/main.tf`](../assets/examples/volcenginecc-vpc-traffic-mirror-filter/main.tf) and notes in [`volcenginecc-vpc-traffic-mirror-filter.md`](./volcenginecc-vpc-traffic-mirror-filter.md). Full mirror targets and sessions still require attached ECS ENIs or CLB targets and are tracked in [`volcenginecc-blocked.md`](./volcenginecc-blocked.md).

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vpc_prefix_list` | Reusable CIDR set for security group and route policy inputs |
| `volcenginecc_vpc_network_acl` | Subnet-level stateless allow/drop controls |
| `volcenginecc_vpc_eni` | Standalone secondary network interface for ECS attachment or mirror targets |
| `volcenginecc_vpc_ha_vip` | Private virtual IP for active/passive services such as Keepalived |
| `volcenginecc_vpc_bandwidth_package` | Regional shared bandwidth package for public IP bandwidth pooling |

The example includes a minimal VPC, subnet, route table, and security group so it can be validated independently. In real deployments, reuse the verified network foundation instead of creating a separate VPC.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vpc-extras
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform apply -auto-approve -input=false
terraform plan -input=false
terraform destroy
```

## Pitfalls found during verification

1. `volcenginecc_vpc_security_group` uses `ingress_permissions` and `egress_permissions`; older local examples or assumptions using `security_group_rules` fail validation with `Unsupported argument`.

2. A newly created security group may include the platform default egress rule (`description = "放通全部流量"`, `priority = 100`) on first read. Applying once more removed that default rule and the follow-up plan was clean.

3. Keep nested set items fully populated. For security group rules include `direction`, `prefix_list_id`, and `source_group_id`; for network ACL rules include `network_acl_entry_name`, `policy`, `port`, and `protocol`.

4. A standalone `volcenginecc_vpc_eni` can be created without an attached ECS instance. The verified example lets the API allocate the primary private IP and one secondary private IP, which avoids address collisions.

5. A standalone `volcenginecc_vpc_ha_vip` can be created without associated ECS/ENI instances. Pick an unused IP inside the subnet, and bind instances later in workload-specific Terraform.

6. `volcenginecc_vpc_bandwidth_package` can be created as an empty IPv4 BGP pay-by-bandwidth package with `billing_type = 2`, `bandwidth = 2`, and no `eip_addresses`. Add EIPs only after verifying they use compatible line and protection types.

7. Network ACL resources associate subnets through the `resources` nested set. Destroy succeeded when Terraform removed the ACL before route table/subnet cleanup; avoid manual subnet deletion before detaching/deleting the ACL.

## Import IDs

```bash
terraform import volcenginecc_vpc_prefix_list.trusted pl-xxxxxxxx
terraform import volcenginecc_vpc_network_acl.app nacl-xxxxxxxx
terraform import volcenginecc_vpc_eni.app eni-xxxxxxxx
terraform import volcenginecc_vpc_ha_vip.app havip-xxxxxxxx
terraform import volcenginecc_vpc_bandwidth_package.shared bwp-xxxxxxxx
```
