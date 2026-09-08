# Module Reference

Detailed variables and outputs for each Terraform module under `assets/modules/`. SKILL.md keeps the catalog short; this file is the canonical schema for code generation.

---

## `network`

VPC + 2× subnets across AZs + default security group.

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project` | string | yes | — | Resource name prefix |
| `az_primary` | string | yes | — | e.g. `cn-beijing-a` |
| `az_secondary` | string | yes | — | e.g. `cn-beijing-b` |
| `vpc_cidr` | string | no | `10.0.0.0/16` | |
| `subnet_cidr_primary` | string | no | `10.0.1.0/24` | |
| `subnet_cidr_secondary` | string | no | `10.0.2.0/24` | |
| `tags` | map(string) | no | `{}` | Applied to all resources |

### Outputs
| Name | Description |
|---|---|
| `vpc_id` | VPC resource ID |
| `vpc_cidr` | CIDR string echo |
| `subnet_ids` | List of both subnet IDs |
| `subnet_id_primary` | Primary AZ subnet ID |
| `subnet_id_secondary` | Secondary AZ subnet ID (required by HA RDS) |
| `security_group_id` | Default security group ID |

---

## `vke`

VKE cluster + auto-scaling node pool + CoreDNS / metrics-server addons.

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project` | string | yes | — | |
| `vpc_id` | string | yes | — | From `network.vpc_id` |
| `subnet_ids` | list(string) | yes | — | 1–3 subnet IDs |
| `security_group_id` | string | yes | — | From `network.security_group_id` |
| `k8s_version` | string | no | `1.30` | |
| `service_cidr` | string | no | `192.168.0.0/16` | Avoid VPC overlap |
| `node_instance_type` | string | no | `ecs.g3i.xlarge` | Verify availability with `ve ecs DescribeAvailableResource` |
| `node_count_desired` | number | no | `2` | |
| `node_count_min` | number | no | `1` | |
| `node_count_max` | number | no | `5` | |
| `node_system_volume_size` | number | no | `50` | GB |
| `enable_public_api` | bool | no | `false` | Costs ~5 Mbps PostPaidByBandwidth EIP |
| `tags` | map(string) | no | `{}` | |

### Outputs
| Name | Description |
|---|---|
| `cluster_id` | Cluster resource ID |
| `kubeconfig_private` | base64-encoded kubeconfig (private network); **sensitive** |
| `kubeconfig_public` | base64-encoded kubeconfig (public, only when `enable_public_api=true`); **sensitive** |
| `node_pool_id` | Default node pool ID |

> Pod network mode is hardcoded to `VpcCniShared`. Flannel is supported by the provider but not exposed in this module — open an issue if you need it.

---

## `cr`

CR registry + namespace + repository.

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project` | string | yes | — | Used for ProjectName tagging |
| `registry_name` | string | yes | — | Globally unique within account |
| `registry_type` | string | no | `Enterprise` | `Enterprise` or `Micro` |
| `namespace` | string | yes | — | |
| `repository_name` | string | yes | — | |
| `access_level` | string | no | `Private` | `Private` or `Public` |

### Outputs
| Name | Description |
|---|---|
| `registry_id` | Registry resource ID |
| `registry_name` | Echo for downstream `ve cr GetAuthorizationToken` |
| `registry_endpoint` | Domain (e.g. `cr-xxxx.cr.volces.com`) for `docker login` |
| `registry_username` | CR username |
| `namespace` | Namespace name |
| `repository_name` | Repository name |
| `repository_uri` | Full image URI without tag (`<endpoint>/<ns>/<repo>`) |

---

## `rds-mysql`

RDS MySQL HA instance (primary + secondary in different AZs).

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project` | string | yes | — | |
| `subnet_id` | string | yes | — | Primary subnet |
| `primary_zone_id` | string | yes | — | |
| `secondary_zone_id` | string | yes | — | Required by provider for HA |
| `db_engine_version` | string | no | `MySQL_8_0` | `MySQL_5_7` or `MySQL_8_0` |
| `instance_type` | string | no | `rds.mysql.1c2g` | spec_name |
| `storage_space` | number | no | `100` | GB |
| `charge_type` | string | no | `PostPaid` | `PostPaid` or `PrePaid` |
| `tags` | map(string) | no | `{}` | |

### Outputs
| Name | Description |
|---|---|
| `instance_id` | RDS instance ID |
| `endpoints` | Full endpoints list (Cluster/Primary/Custom). Each has `address`, `port`, `network_type`. Use `jq '.endpoints | map(select(.network_type == "Private"))[0]'` to extract the private endpoint. |

---

## `redis`

Redis instance (single or HA).

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project` | string | yes | — | |
| `subnet_id` | string | yes | — | |
| `primary_az` | string | yes | — | |
| `secondary_az` | string | no | `""` | Required when `multi_az=enabled` |
| `engine_version` | string | no | `6.0` | `5.0`, `6.0`, or `7.0` |
| `node_number` | number | no | `2` | 1–6 (1 = single-node) |
| `shard_capacity` | number | no | `1024` | MiB per shard |
| `sharded_cluster` | number | no | `0` | `0` disabled, `1` enabled |
| `multi_az` | string | no | `disabled` | `disabled` or `enabled` |
| `port` | number | no | `6379` | 1024–65535 |
| `charge_type` | string | no | `PostPaid` | |
| `tags` | map(string) | no | `{}` | |

### Outputs
| Name | Description |
|---|---|
| `instance_id` | Redis instance ID |
| `port` | Configured port |

> The provider does not export an endpoint attribute. Downstream resolves the address with `ve redis DescribeDBInstanceDetail --InstanceId <id>` and reads `Result.VisitAddrs`.

---

## `tos`

TOS bucket.

### Variables
| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `bucket_name` | string | yes | — | Globally unique, 3–63 chars |
| `project_name` | string | no | `default` | |
| `public_acl` | string | no | `private` | See provider docs for valid values |
| `storage_class` | string | no | `STANDARD` | `STANDARD` or `IA` |
| `az_redundancy` | string | no | `single-az` | `single-az` or `multi-az` |
| `versioning_enabled` | bool | no | `false` | |
| `tags` | map(string) | no | `{}` | |

### Outputs
| Name | Description |
|---|---|
| `bucket_name` | Echo |
| `intranet_endpoint` | Internal-network endpoint (preferred from compute inside same region) |
| `extranet_endpoint` | Public-internet endpoint |
| `location` | Region code |
