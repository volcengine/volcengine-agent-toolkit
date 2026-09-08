# Volcenginecc Blocked Verification Notes

This file records resources whose Terraform configuration reached `validate`/`plan` or an initial API call but could not be fully verified because the current account lacks service enablement, permissions, quota, or required external dependencies.

## KMS

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_kms_key_ring` | Teardown-blocked | Creates once KMS is enabled, but the keyring cannot be deleted while it still holds a key pending scheduled deletion |
| `volcenginecc_kms_key` | Teardown-blocked | Creates after the keyring, but deletion is a scheduled `ScheduleKeyDeletion` with a mandatory multi-day pending window, so `terraform destroy` cannot remove it in the same run |
| `volcenginecc_kms_secret` | Create-capable | Secrets Manager is enabled; not promoted because the keyring/key teardown keeps the stack from a clean destroy |

As of 2026-06-17, KMS and Secrets Manager are enabled for the account, so the historical `ServiceNotOpen` errors below no longer occur. The remaining blocker is teardown, not service enablement: `volcenginecc_kms_key` deletion is scheduled with a mandatory pending window (minimum 7 days), so a single `terraform destroy` cannot remove the key and its keyring and reach empty state. Do not promote KMS as a verified example until this teardown behavior is acceptable for shared examples. The historical service-not-enabled evidence is kept below for reference.

Minimal configuration validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, but `apply` originally failed on key ring creation while KMS was disabled. The 2026-05-30 retry failed with the same service-not-enabled error:

```text
ServiceNotEnabled: KMS_ServiceNotOpen: KMS service not open yet, please open the service and try again later.
TypeName: Volcengine::KMS::KeyRing
Operation: CREATE
OperationStatus: FAILED
```

Latest retry evidence:

```text
EventTime: 2026-05-30T08:24:50+08:00
TaskID: task-<id>
ServiceNotEnabled: KMS_ServiceNotOpen: KMS service not open yet, please open the service and try again later.
TypeName: Volcengine::KMS::KeyRing
Operation: CREATE
OperationStatus: FAILED
```

Current-account retry on 2026-05-30 in `<tmp-workdir>` used only `volcenginecc_kms_key_ring` to avoid putting secret values in state before the service is enabled. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed with the same service boundary:

```text
EventTime: 2026-05-30T10:50:04+08:00
TaskID: task-<id>
ServiceNotEnabled: KMS_ServiceNotOpen: KMS service not open yet, please open the service and try again later.
TypeName: Volcengine::KMS::KeyRing
Operation: CREATE
OperationStatus: FAILED
```

Retried the same key-ring-only shape again on 2026-05-30 after other products had been verified. `terraform fmt`, `init -backend=false`, `validate`, and `plan` still succeeded; `apply` failed before creating any KMS resource:

```text
EventTime: 2026-05-30T12:24:07+08:00
TaskID: task-<id>
ServiceNotEnabled: KMS_ServiceNotOpen: KMS service not open yet, please open the service and try again later.
TypeName: Volcengine::KMS::KeyRing
Operation: CREATE
OperationStatus: FAILED
```

Retried the same key-ring-only shape again on 2026-05-30 at 13:55 with the current account. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; `apply` still failed at service enablement before creating any KMS resource:

```text
EventTime: 2026-05-30T13:55:43+08:00
TaskID: task-<id>
ServiceNotEnabled: KMS_ServiceNotOpen: KMS service not open yet, please open the service and try again later.
TypeName: Volcengine::KMS::KeyRing
Operation: CREATE
OperationStatus: FAILED
```

No KMS resources were created; Terraform state remained empty.

After KMS service permission was granted, a 2026-05-30 retry in `<tmp-workdir>` created keyring `cc-iac-kms-retry` (`<resource-id>`) and key `cc-iac-kms-retry-key` (`<resource-id>`) successfully. Creating `volcenginecc_kms_secret` still failed because Credential Manager / Secrets Manager is not open:

```text
EventTime: 2026-05-30T15:08:48+08:00
TaskID: task-<id>
AccessDenied: SecretsManagerServiceNotOpen: Secrets Manager service not open yet. Please open the service and try again later.
TypeName: Volcengine::KMS::Secret
Operation: CREATE
OperationStatus: FAILED
```

Destroy scheduled the key for deletion instead of physically removing it, then keyring deletion failed because the pending-deletion key still counts toward the keyring:

```text
EventTime: 2026-05-30T15:09:05+08:00
TaskID: task-<id>
InvalidRequest: InvalidKeyringDeletion: Unable to delete keyring [cc-iac-kms-retry]. Please delete [1] keys in the keyring first.
TypeName: Volcengine::KMS::KeyRing
Operation: DELETE
OperationStatus: FAILED
```

Cloud-side check showed the key in `PendingDelete` with `ScheduleDeleteTime = "2026-06-06T15:09:03.374+08:00"` and the keyring still present with `KeyCount = 1`. Do not promote KMS to a clean verified example until `kms_key` destroy behavior and keyring cleanup are acceptable for shared examples. After the scheduled key deletion completes, delete keyring `<resource-id>` / `cc-iac-kms-retry` and remove the temporary Terraform state.

When KMS is enabled for the account, retry with this shape:

```hcl
resource "volcenginecc_kms_key_ring" "main" {
  keyring_name = "cc-iac-kms"
  keyring_type = "CustomKeyring"
  project_name = "default"
  description  = "volcenginecc KMS example keyring"
}

resource "volcenginecc_kms_key" "main" {
  keyring_name     = volcenginecc_kms_key_ring.main.keyring_name
  key_name         = "cc-iac-kms-key"
  key_spec         = "SYMMETRIC_256"
  key_usage        = "ENCRYPT_DECRYPT"
  protection_level = "SOFTWARE"
  origin           = "CloudKMS"
  multi_region     = false
}

resource "volcenginecc_kms_secret" "main" {
  secret_name    = "cc-iac-kms/generic"
  version_name   = "v1"
  project_name   = "default"
  secret_type    = "Generic"
  encryption_key = volcenginecc_kms_key.main.trn
  secret_value = jsonencode({
    example = "non-sensitive-verification-value"
  })
}
```

Do not store real AK/SK, passwords, or certificates in repository examples or temporary Terraform state during verification.

## Entry Traffic

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_clb_clb` | Verified | Private CLB create/destroy succeeded; see `volcenginecc-clb.md` |
| `volcenginecc_clb_certificate` | Verified | Server certificate with traditional RSA private key created/no-op/destroyed; see `volcenginecc-clb.md` |
| `volcenginecc_clb_acl` | Verified | Standalone CLB ACL create/no-op/destroy succeeded; see `volcenginecc-clb.md` |
| `volcenginecc_clb_server_group` | Blocked | `AccessDenied: Forbidden: You are not authorized to perform operations on the specified service` during create |
| `volcenginecc_clb_listener` | Not applied | Depends on CLB server group |
| `volcenginecc_clb_rule` | Not applied | Depends on CLB listener and server group |
| `volcenginecc_alb_health_check_template` | Verified | Create/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_acl` | Verified | Standalone ALB ACL create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_customized_cfg` | Verified | Standalone ALB customized config create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_load_balancer` | Verified | Private Basic ALB create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_server_group` | Verified | Empty IP-type HTTP server group create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_listener` | Verified | Disabled HTTP listener create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_rule` | Verified | Basic host/path forwarding rule create/no-op/destroy succeeded; see `volcenginecc-alb.md` |
| `volcenginecc_alb_certificate` | Verified for Server | Server certificate with traditional RSA private key created/no-op/destroyed; CA certificate remains unverified |
| `volcenginecc_clb_nlb_security_policy` | Whitelist-blocked | Custom NLB TLS policy planned but create failed requesting whitelist key `nlb_tls_allow` |
| `volcenginecc_clb_nlb` | Lifecycle-only | Private NLB create/destroy succeeded, but the required server group has persistent no-op drift |
| `volcenginecc_clb_nlb_server_group` | Drift-blocked | Created/destroyed only after explicit session persistence settings; follow-up plans never converged |
| `volcenginecc_clb_nlb_listener` | Lifecycle-only | TCP listener created/destroyed, but depends on drift-blocked NLB server group |
| `volcenginecc_apig_gateway` | Verified | Private-only APIG gateway create/no-op/destroy succeeded; see `volcenginecc-apig.md` |
| `volcenginecc_apig_gateway_service` | Verified | Private HTTP gateway service create/no-op/destroy succeeded; see `volcenginecc-apig.md` |
| `volcenginecc_apig_upstream` | Whitelist-blocked | Domain upstream plan succeeded but create failed with `OperationDenied.AccountNotInWhitelist` |
| `volcenginecc_apig_upstream_source` | Dependency/whitelist-blocked | Requires APIG upstream capability plus a real VKE cluster or Nacos source; Nacos auth would store credentials |
| `volcenginecc_apig_custom_domain` | Dependency-blocked | Requires a real custom domain and certificate lifecycle |

CLB partial verification in `cn-beijing`: VPC, subnet, route table, and private CLB created successfully. Creating `clb_server_group` then failed with:

```text
AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.
TypeName: Volcengine::CLB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Latest CLB full-path retry in `cn-beijing`: VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, and private CLB `clb-<id>` created successfully. Creating an empty IP-type `volcenginecc_clb_server_group` failed with the same permission error before listener/rule creation:

```text
EventTime: 2026-05-30T09:47:16+08:00
TaskID: task-<id>
AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.
TypeName: Volcengine::CLB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

The private CLB, route table, subnet, and VPC were destroyed successfully and final Terraform state was empty. Retry `clb_server_group`, `clb_listener`, and `clb_rule` after the account has CLB server group create permission.

Current-account retry on 2026-05-30 in `<tmp-workdir>` used a private CLB plus empty IP-type server group, disabled HTTP listener, and forwarding rule. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded for all seven resources. Apply created VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, and private CLB `clb-<id>`, then failed on `volcenginecc_clb_server_group` before listener/rule creation with the same permission boundary:

```text
EventTime: 2026-05-30T11:47:38+08:00
TaskID: task-<id>
AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.
TypeName: Volcengine::CLB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy removed the private CLB, route table, subnet, and VPC; final Terraform state was empty. `DescribeLoadBalancers --LoadBalancerName cc-iac-clb-full-clb` and `DescribeVpcs --VpcName cc-iac-clb-full-vpc` both returned `TotalCount: 0`.

After the user reported CLB permissions were added, a 2026-05-30 retry in `<tmp-workdir>` used the verified private CLB example plus empty IP-type `clb_server_group`, disabled HTTP listener, and forwarding rule. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded for all seven resources. Apply created VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, and private CLB `clb-<id>`, then `clb_server_group` still failed before listener/rule creation:

```text
EventTime: 2026-05-30T15:17:10+08:00
TaskID: task-<id>
AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.
TypeName: Volcengine::CLB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy removed the private CLB, route table, subnet, and VPC. Final Terraform state was empty, `ve clb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-clb-clb"}'` returned `TotalCount: 0`, and exact VPC-name matching for `cc-iac-clb-vpc` returned no rows. The missing permission is still the Cloud Control `Volcengine::CLB::ServerGroup` create path, not the base CLB instance path.

After another permission grant, a 2026-05-30 retry in `<tmp-workdir>` used a private CLB, empty IP-type server group, disabled HTTP listener, and forwarding rule. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded for all seven resources. Apply created VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, and private CLB `clb-<id>`, then `clb_server_group` still failed before listener/rule creation:

```text
EventTime: 2026-05-30T17:22:32+08:00
TaskID: task-<id>
AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.
TypeName: Volcengine::CLB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy removed the private CLB, route table, subnet, and VPC. Final Terraform state was empty, `ve clb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-clb-1716-clb"}'` returned `TotalCount: 0`, exact VPC-name matching for `cc-iac-clb-1716-vpc` returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`. The missing permission remains the Cloud Control `Volcengine::CLB::ServerGroup` create path.

APIG private gateway/service verification in `cn-beijing`: a one-subnet private standard gateway using `1c2g`, 2 replicas, and `enable_public_network = false` created successfully, followed by a private HTTP gateway service. The clean no-op shape omits `resource_spec.clb_spec_code` and `resource_spec.public_network_billing_type`; setting them while public network is disabled caused a replacement diff because the API read both back as empty strings. Gateway create took about 2 minutes, service create about 15 seconds, and the service returned a private default domain.

`volcenginecc_apig_upstream` with `source_type = "Domain"` and `example.com:80` planned successfully but failed on create:

```text
EventTime: 2026-05-30T10:56:42+08:00
TaskID: task-<id>
AccessDenied: OperationDenied.AccountNotInWhitelist: Operation is denied because the account is not in the whitelist.
TypeName: Volcengine::APIG::Upstream
Operation: CREATE
OperationStatus: FAILED
```

`volcenginecc_apig_upstream_source` was not applied after the account-level upstream whitelist failure. The resource is not a generic domain upstream: it imports a VKE/Kubernetes or Nacos source into APIG. A reusable example would require either a verified VKE cluster source or a real Nacos registry; the Nacos `basic.password` field would also be stored in Terraform state. Retry only after `apig_upstream` is allowed in the account, using a VKE source first to avoid registry credentials in shared examples.

APIG destroy caveat: service and gateway deletion succeeded, but subnet deletion initially failed with `InvalidSubnet.InUse` while service-managed ENIs were being released, and VPC deletion then failed on APIG-created security groups. Recovery was: wait until `ve vpc DescribeNetworkInterfaces --SubnetId <subnet_id>` returns empty, delete only the APIG-created `apig-sg-*` groups in the temporary VPC, rerun `terraform destroy`, and confirm final state is empty. `ListGateways`, `ListGatewayServices`, and VPC lookup confirmed no temporary APIG/VPC resources remained.

ALB partial verification in `cn-beijing`: health check template created successfully. A private Basic ALB and an IP-type empty ALB server group both planned successfully, then failed during apply:

```text
OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::LoadBalancer
Operation: CREATE
OperationStatus: FAILED
```

```text
OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Latest ALB full-path retry in `cn-beijing`: VPC `vpc-<id>`, two subnets, and two custom route tables created successfully. Creating both private Basic `volcenginecc_alb_load_balancer` and empty IP-type `volcenginecc_alb_server_group` still failed before listener/rule creation:

```text
EventTime: 2026-05-30T09:49:51+08:00
TaskID: task-<id>
GeneralServiceException: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::LoadBalancer
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T09:49:12+08:00
TaskID: task-<id>
InvalidRequest: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy hit one transient `InvalidOperation.Conflict` on a route table, then a retry succeeded. All ALB retry dependencies were destroyed and final Terraform state was empty. Retry `alb_load_balancer`, `alb_server_group`, `alb_listener`, and `alb_rule` after the account/IAM path permits ALB create calls.

Current-account retry on 2026-05-30 in `<tmp-workdir>` used a private Basic ALB, empty IP-type HTTP server group, disabled HTTP listener, and path rule. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded after setting `alb_server_group.health_check.port = 0`; despite the docs marking the field optional, provider validation requires it even when health checks are disabled. Apply created VPC `vpc-<id>`, subnets `subnet-<id>` and `subnet-<id>`, and route tables `vtb-<id>` and `vtb-<id>`, then ALB load balancer and server group failed with the same IAM query boundary:

```text
EventTime: 2026-05-30T11:51:47+08:00
TaskID: task-<id>
GeneralServiceException: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::LoadBalancer
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T11:51:09+08:00
TaskID: task-<id>
InvalidRequest: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy removed both route tables, both subnets, and the VPC; final Terraform state was empty. `DescribeLoadBalancers --LoadBalancerName cc-iac-alb-full-alb` and `DescribeVpcs --VpcName cc-iac-alb-full-vpc` both returned `TotalCount: 0`.

After the user reported ALB permissions were added, a 2026-05-30 retry in `<tmp-workdir>` used a private Basic ALB, two subnets, empty IP-type HTTP server group, disabled HTTP listener, and forwarding rule. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply created VPC `vpc-<id>`, subnets `subnet-<id>` and `subnet-<id>`, and route tables `vtb-<id>` and `vtb-<id>`, then ALB load balancer and server group still failed:

```text
EventTime: 2026-05-30T15:20:02+08:00
TaskID: task-<id>
GeneralServiceException: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::LoadBalancer
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T15:19:23+08:00
TaskID: task-<id>
InvalidRequest: OperationFailed.QueryIAM: The request on the specified resource failed due to the query on IAM failed.
TypeName: Volcengine::ALB::ServerGroup
Operation: CREATE
OperationStatus: FAILED
```

Destroy initially hit transient `InvalidOperation.Conflict` on one route table; a retry removed the remaining route table, subnet, and VPC. Final Terraform state was empty, `ve alb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-alb-retry-alb"}'` returned `TotalCount: 0`, and exact VPC-name matching for `cc-iac-alb-retry-vpc` returned no rows. The account/IAM path for ALB load balancer and server group create is still blocked.

After another permission grant, a 2026-05-30 retry in `<tmp-workdir>` verified the full private Basic ALB path. The first apply created VPC `vpc-<id>`, subnets `subnet-<id>` and `subnet-<id>`, route tables `vtb-<id>` and `vtb-<id>`, server group `rsp-<id>`, private ALB `alb-<id>`, listener `lsn-<id>`, and rule `rule-<id>`.

The first follow-up plan showed server group health-check drift because the API reads disabled health checks back with defaults:

```text
~ http_code    = "http_2xx,http_3xx" -> "http_2xx"
~ http_version = "HTTP1.0" -> "HTTP1.1"
~ method       = "HEAD" -> "GET"
+ cross_zone_enabled = "on"
```

Aligning the configuration to the API defaults (`method = "HEAD"`, `http_version = "HTTP1.0"`, `http_code = "http_2xx,http_3xx"`) and omitting `cross_zone_enabled` produced a clean no-op plan. Destroy then removed rule, listener, server group, ALB, route tables, subnets, and VPC. Final Terraform state was empty, `ve alb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-alb-1724-alb"}'` returned `TotalCount: 0`, `ve alb DescribeServerGroups --body '{"ServerGroupName":"cc-iac-alb-1724-sg"}'` returned `TotalCount: 0`, exact VPC-name matching returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`. The verified example now lives in `assets/examples/volcenginecc-alb`.

Formal verification of `assets/examples/volcenginecc-alb` in `<tmp-workdir>` then created VPC `vpc-<id>`, server group `rsp-<id>`, private ALB `alb-<id>`, listener `lsn-<id>`, and rule `rule-<id>`. A follow-up `terraform plan -detailed-exitcode` returned `No changes`. The first destroy hit one transient route-table `InvalidOperation.Conflict` after ALB/service ENI deletion; `DescribeNetworkInterfaces` showed no ENIs, and a second destroy removed the remaining route table, subnet, and VPC. Final Terraform state was empty, `ve alb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-alb-alb"}'` returned `TotalCount: 0`, `ve alb DescribeServerGroups --body '{"ServerGroupName":"cc-iac-alb-sg"}'` returned `TotalCount: 0`, exact VPC-name matching for `cc-iac-alb-vpc` returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`.

ALB server certificate verification in `cn-beijing`: a self-signed `Server` certificate with a traditional RSA private key created successfully, had a clean no-op plan, and destroyed successfully. The created certificate ID was `<certificate-id>`; final Terraform state was empty. A first server-certificate attempt with OpenSSL's default PKCS#8 private key failed with:

```text
InvalidPrivateKey.Malformed: The specified PrivateKey is malformed.
TypeName: Volcengine::ALB::Certificate
Operation: CREATE
OperationStatus: FAILED
```

The earlier ALB CA certificate attempt used a one-day self-signed CA certificate and failed with:

```text
InvalidCACertificate.Malformed: The specified CACertificate is malformed. The specified ca certificate's format is malformed.
TypeName: Volcengine::ALB::Certificate
Operation: CREATE
OperationStatus: FAILED
```

All temporary CLB/ALB resources were destroyed; final Terraform state was empty for both verification directories.

Standalone ALB/CLB ACL verification in `cn-beijing`: `volcenginecc_alb_acl` and `volcenginecc_clb_acl` both created with one TEST-NET CIDR entry, had a clean no-op plan, and destroyed successfully. Created IDs were `<acl-id>` for ALB and `<acl-id>` for CLB. ACL creation took about 21s and deletion about 15s. These ACL examples verify policy group lifecycle only; listener attachment still depends on verified listener resources.

CLB server certificate verification in `cn-beijing`: a self-signed server certificate with a traditional RSA private key created successfully, had a clean no-op plan, and destroyed successfully. The created certificate ID was `<certificate-id>`; final Terraform state was empty. A first server-certificate attempt with OpenSSL's default PKCS#8 private key failed with:

```text
InvalidPrivateKey.Malformed: The specified PrivateKey is malformed.
TypeName: Volcengine::CLB::Certificate
Operation: CREATE
OperationStatus: FAILED
```

Standalone ALB customized config verification in `cn-beijing`: `volcenginecc_alb_customized_cfg` created with content `client_max_body_size 60M;\r\nkeepalive_timeout 77s;\r\n`, had a clean no-op plan, and destroyed successfully. Created ID was `ccfg-<id>`. Creation took about 15s and deletion about 6s. This verifies config-policy lifecycle only; listener association still depends on verified listener resources.

NLB TLS security policy retry in `cn-beijing`: `volcenginecc_clb_nlb_security_policy` validated and planned with `tls_versions = ["TLSv1.2"]` and common TLSv1.2 cipher suites, but create failed before any resource was created:

```text
RequestForbidden: Forbidden: You are not authorized to perform operations on the specified service; apply for the following whitelist key, 'nlb_tls_allow'.
TypeName: Volcengine::CLB::NLBSecurityPolicy
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T07:04:48+08:00
```

No NLB security policy resources were created; Terraform state remained empty. Retry after the `nlb_tls_allow` whitelist is granted.

NLB main path retry in `cn-beijing`: a private intranet NLB, IP-type empty TCP server group, and disabled TCP listener validated and planned successfully. NLB instance creation succeeded with ID `nlb-<id>`; TCP listener creation succeeded with ID `lsn-<id>`; all resources later destroyed successfully and final Terraform state was empty.

The first two server group create attempts failed because the provider/API sent an invalid session persistence timeout when session persistence was disabled or timeout was omitted:

```text
InvalidRequest: InvalidSessionPersistenceTimeout.Malformed: The specified SessionPersistenceTimeout is malformed.
TypeName: Volcengine::CLB::NLBServerGroup
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T08:06:08+08:00
```

```text
InvalidRequest: InvalidSessionPersistenceTimeout.Malformed: The specified SessionPersistenceTimeout is malformed.
TypeName: Volcengine::CLB::NLBServerGroup
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T08:07:16+08:00
```

Setting `session_persistence_enabled = true` and `session_persistence_timeout = 1000` allowed the server group to create with ID `rsp-<id>`. However, every follow-up plan proposed an in-place update on Optional+Computed fields (`connection_drain_timeout`, `health_check` nested defaults, and `servers`) even after applying that update. `lifecycle.ignore_changes` on those fields, and even `ignore_changes = all`, did not suppress the provider-planned update. Do not add a verified NLB example until `volcenginecc_clb_nlb_server_group` can reach a clean no-op plan.

Minimal retry shape that created but drifted:

```hcl
resource "volcenginecc_clb_nlb_server_group" "app" {
  server_group_name           = "cc-iac-nlb-sg-app"
  project_name                = "default"
  vpc_id                      = volcenginecc_vpc_vpc.main.vpc_id
  protocol                    = "TCP"
  type                        = "ip"
  scheduler                   = "wrr"
  ip_address_version          = "ipv4"
  any_port_enabled            = false
  connection_drain_enabled    = false
  preserve_client_ip_enabled  = false
  session_persistence_enabled = true
  session_persistence_timeout = 1000
  proxy_protocol_type         = "off"
  timestamp_remove_enabled    = true

  health_check = {
    enabled             = false
    healthy_threshold   = 3
    interval            = 10
    method              = "GET"
    timeout             = 3
    type                = "TCP"
    unhealthy_threshold = 3
  }
}
```

## Network Interconnect

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_cen_cen` | Verified | CEN with same-account VPC attachment create/no-op/destroy succeeded; see `volcenginecc-cen.md` |
| `volcenginecc_cen_bandwidth_package` | Not applied | Depends on CEN permission and creates a billable bandwidth package |
| `volcenginecc_cen_inter_region_bandwidth` | Dependency-blocked | Requires CEN and CEN bandwidth package |
| `volcenginecc_cen_route_entry` | Dependency-blocked | Requires a created CEN attached to a network instance |
| `volcenginecc_cen_service_route_entry` | Dependency-blocked | Requires a created CEN and service VPC route target |
| `volcenginecc_cen_grant_instance` | Dependency/cross-account blocked | Requires another account's CEN ID and owner ID |
| `volcenginecc_directconnect_direct_connect_gateway` | Verified | Direct Connect gateway create/no-op/destroy succeeded; see `volcenginecc-directconnect.md` |
| `volcenginecc_directconnect_virtual_interface` | Dependency-blocked | Requires Direct Connect gateway and a real physical dedicated line ID |
| `volcenginecc_directconnect_gateway_route` | Dependency-blocked | Requires Direct Connect gateway and a VIF/CEN/TransitRouter next hop |
| `volcenginecc_transitrouter_transit_router` | Verified | TransitRouter create/no-op/destroy succeeded; see `volcenginecc-transitrouter.md` |
| `volcenginecc_transitrouter_transit_router_route_table` | Dependency-blocked | Requires a verified TransitRouter instance |
| `volcenginecc_transitrouter_vpc_attachment` | Dependency-blocked | Requires TransitRouter plus VPC/subnet attach points |
| `volcenginecc_transitrouter_vpn_attachment` | Dependency-blocked | Requires TransitRouter plus a VPN connection |
| `volcenginecc_transitrouter_peer_attachment` | Dependency/billable blocked | Requires two TransitRouter instances plus a bandwidth package |
| `volcenginecc_transitrouter_transit_router_route_entry` | Dependency-blocked | Requires a route table and valid attachment next hop |
| `volcenginecc_privatelink_endpoint_service` | Verified | Interface endpoint service backed by private CLB create/no-op/destroy succeeded; see `volcenginecc-privatelink.md` |
| `volcenginecc_privatelink_vpc_endpoint` | Verified | Same-account consumer endpoint create/no-op/destroy succeeded and reached `Connected`; see `volcenginecc-privatelink.md` |
| `volcenginecc_privatelink_vpc_endpoint_connection` | Advanced-path blocked | Auto-accepted baseline does not need explicit connection resource; verify separately only for manual connection/resource allocation workflows |

CEN minimal configuration validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, using a temporary VPC attached through `instances`. VPC creation succeeded, then CEN creation failed:

```text
EventTime: 2026-05-30T11:14:35+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: cen:CreateCen on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CEN::CEN
Operation: CREATE
OperationStatus: FAILED
```

Recovery: `terraform destroy` removed the temporary VPC successfully. Final `terraform state list` returned empty, and `ve vpc DescribeVpcs --VpcName cc-iac-cen-vpc-current` returned `TotalCount: 0`.

After `cen:CreateCen` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified the CEN+single-VPC attachment lifecycle. CEN `cc-iac-cen-retry-cen` created with ID `cen-<id>` and attached VPC `vpc-<id>`. `terraform plan -detailed-exitcode` returned `No changes`; destroy removed the CEN first, then the VPC. Final Terraform state was empty, `ve cen DescribeCens --body '{"CenName":"cc-iac-cen-retry-cen"}'` returned `TotalCount: 0`, and exact VPC-name matching for `cc-iac-cen-retry-vpc` returned no rows.

The verified example now lives in `assets/examples/volcenginecc-cen`; validation notes and pitfalls live in `references/volcenginecc-cen.md`. Start with the CEN+single-VPC attachment shape before trying bandwidth packages, inter-region bandwidth, published routes, or cross-account grants:

```hcl
resource "volcenginecc_cen_cen" "main" {
  cen_name     = "cc-iac-cen"
  description  = "volcenginecc CEN example"
  project_name = "default"

  instances = [
    {
      instance_id        = volcenginecc_vpc_vpc.main.vpc_id
      instance_owner_id  = var.account_id
      instance_region_id = "cn-beijing"
      instance_type      = "VPC"
    }
  ]
}
```

CEN bandwidth packages, inter-region bandwidth, published routes, and cross-account grants are still excluded from the default example because they add billable or external-account dependencies.

DirectConnect gateway retry in `cn-beijing`: the minimal gateway-only configuration used `enable_ipv_6 = false`, project `default`, and one tag. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before a gateway ID was created:

```text
EventTime: 2026-05-30T13:32:58+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: directconnect:CreateDirectConnectGateway on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::DirectConnect::DirectConnectGateway
Operation: CREATE
OperationStatus: FAILED
```

No DirectConnect resources were created; Terraform state remained empty. Retry `directconnect_direct_connect_gateway` after the create permission is granted. Add `directconnect_virtual_interface` only with a real physical dedicated line ID, and add `directconnect_gateway_route` only after a valid VIF, CEN, or TransitRouter next hop exists.

After `directconnect:CreateDirectConnectGateway` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified the standalone Direct Connect gateway lifecycle. Gateway `cc-iac-dc-retry-gw` created with ID `<directconnect-gateway-id>`. `terraform plan -detailed-exitcode` returned `No changes`; destroy removed the gateway, final Terraform state was empty, and `ve directconnect DescribeDirectConnectGateways --body '{"DirectConnectGatewayName":"cc-iac-dc-retry-gw"}'` returned `TotalCount: 0`. The verified example now lives in `assets/examples/volcenginecc-directconnect`; validation notes and pitfalls live in `references/volcenginecc-directconnect.md`.

TransitRouter retry in `cn-beijing`: the minimal router-only configuration used `asn = 64512`, `multicast_enabled = false`, project `default`, and one tag. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before a TransitRouter ID was created:

```text
EventTime: 2026-05-30T13:35:09+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: transitrouter:CreateTransitRouter on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::TransitRouter::TransitRouter
Operation: CREATE
OperationStatus: FAILED
```

No TransitRouter resources were created; Terraform state remained empty. Retry `transitrouter_transit_router` after the create permission is granted. Add route tables and VPC attachments only after the base router reaches clean no-op; peer attachments also need a bandwidth package and should be treated as billable inter-region resources.

After `transitrouter:CreateTransitRouter` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified the standalone TransitRouter lifecycle. TransitRouter `cc-iac-tr-retry` created with ID `<transit-router-id>`, `asn = 64512`, and `multicast_enabled = false`. `terraform plan -detailed-exitcode` returned `No changes`; destroy removed the router, final Terraform state was empty, and `ve transitrouter DescribeTransitRouters --body '{"TransitRouterName":"cc-iac-tr-retry"}'` returned `TotalCount: 0`. The verified example now lives in `assets/examples/volcenginecc-transitrouter`; validation notes and pitfalls live in `references/volcenginecc-transitrouter.md`.

PrivateLink CLB endpoint service configuration validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`. The retry used a temporary VPC, subnet, route table, private CLB, and an Interface endpoint service with private DNS disabled. VPC, subnet, route table, and CLB all created successfully, then endpoint service creation failed:

```text
EventTime: 2026-05-30T11:18:51+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: privatelink:CreateVpcEndpointService on resource: trn:clb:cn-beijing:<account-id>:clb/clb-<id>,trn:iam::<account-id>:project/default
TypeName: Volcengine::PrivateLink::EndpointService
Operation: CREATE
OperationStatus: FAILED
```

Recovery: `terraform destroy` removed the private CLB, route table, subnet, and VPC successfully. Final `terraform state list` returned empty; `ve clb DescribeLoadBalancers` for the temporary CLB returned `TotalCount: 0`; `ve vpc DescribeVpcs --VpcName cc-iac-pl-current-vpc` returned `TotalCount: 0`; `ve privatelink DescribeVpcEndpointServices --ServiceResourceType CLB --ServiceType Interface` returned `TotalCount: 0`.

After `privatelink:CreateVpcEndpointService` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified the full auto-accepted Interface PrivateLink path. The first apply created the service VPC/subnet/route table, private CLB `clb-<id>`, and endpoint service `<endpoint-service-id>`. A follow-up plan returned `No changes`.

A second apply added a consumer VPC/subnet/route table/security group and endpoint `<endpoint-id>`. The first endpoint apply hit the common transient VPC security-group conflict, then a rerun succeeded:

```text
EventTime: 2026-05-30T16:04:43+08:00
TaskID: task-<id>
InvalidRequest: InvalidOperation.Conflict: The specified resource operation conflicts.
TypeName: Volcengine::VPC::SecurityGroup
Operation: CREATE
OperationStatus: FAILED
```

After the rerun, `ve privatelink DescribeVpcEndpoints --body '{"EndpointName":"cc-iac-pl-retry-endpoint"}'` showed the endpoint with `ConnectionStatus = "Connected"`, so no explicit `volcenginecc_privatelink_vpc_endpoint_connection` resource was needed for the baseline. The full stack then had a clean no-op plan.

Destroy removed endpoint, endpoint service, CLB, security group, route tables, subnets, and both VPCs. Final Terraform state was empty. `DescribeVpcEndpointServices` for service ID `<endpoint-service-id>` returned `TotalCount: 0`, `DescribeVpcEndpoints` for endpoint ID `<endpoint-id>` no longer returned that endpoint, `ve clb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-pl-retry-clb"}'` returned `TotalCount: 0`, and exact VPC-name matching for both temporary VPCs returned no rows.

The verified example now lives in `assets/examples/volcenginecc-privatelink`; validation notes and pitfalls live in `references/volcenginecc-privatelink.md`. Keep `private_dns_enabled = false` for the baseline test; enabling Private DNS adds public domain verification.

## VKE Remaining Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vke_cluster` | Verified | No-node managed cluster create/no-op/destroy succeeded |
| `volcenginecc_vke_node_pool` | Verified | Zero-replica node pool create/no-op/destroy succeeded |
| `volcenginecc_vke_kubeconfig` | Verified | Private kubeconfig create/no-op/destroy succeeded |
| `volcenginecc_vke_addon` | Verified | Managed `pod-identity-webhook` addon create/no-op/destroy succeeded; see `volcenginecc-vke.md` |
| `volcenginecc_vke_default_node_pool` | Verified | Default node pool create/no-op/destroy succeeded on a zero-worker cluster; see `volcenginecc-vke.md` |
| `volcenginecc_vke_permission` | Dependency-bound | Requires a real cluster plus a deliberate IAM user/role/account grantee ID and authorization model |
| `volcenginecc_vke_node` | Dependency-blocked | Requires an existing ECS instance to attach as a worker node |

`vke_node_pool` parameter narrowing during verification:

```text
MissingParameter.NodeConfig: The required parameter NodeConfig is missing.
MissingParameter.NodeConfig.Security.Login: The required parameter NodeConfig.Security.Login is missing.
InvalidParameter.AutoScaling.MaxReplicas: The specified parameter AutoScaling.MaxReplicas is invalid.
```

The verified zero-replica fix is: include real `node_config`, include `security.login`, and set `min_replicas = 0`, `desired_replicas = 0`, `max_replicas = 1`.

`vke_addon` was later verified with a deliberate on-demand managed addon:

```hcl
resource "volcenginecc_vke_addon" "pod_identity_webhook" {
  cluster_id  = volcenginecc_vke_cluster.main.cluster_id
  name        = "pod-identity-webhook"
  version     = "v0.1.1"
  deploy_mode = "Managed"
}
```

Creation took 5m26s and deletion took 5m17s. `ve vke ListAddons` showed the addon as `Running` before Terraform finished waiting, so allow several minutes for Cloud Control waiter convergence.

`vke_default_node_pool` was verified with only security login and cluster security groups:

```hcl
resource "volcenginecc_vke_default_node_pool" "default" {
  cluster_id = volcenginecc_vke_cluster.main.cluster_id

  node_config = {
    security = {
      login = {
        password = var.node_password_base64
      }
      security_group_ids = tolist(volcenginecc_vke_cluster.main.cluster_config.security_group_ids)
    }
  }
}
```

`vke_node` remains dependency-blocked because it attaches an existing ECS instance to a node pool:

```hcl
resource "volcenginecc_vke_node" "worker" {
  cluster_id         = volcenginecc_vke_cluster.main.cluster_id
  node_pool_id       = volcenginecc_vke_node_pool.zero.node_pool_id
  instance_id        = var.existing_ecs_instance_id
  keep_instance_name = true
}
```

Do not add a verified `vke_node` example until an ECS instance can be created or selected, attached, re-planned to no-op, detached/deleted, and the cleanup order is proven.

`vke_permission` remains dependency-bound because it grants RBAC to a real IAM principal on a real cluster:

```hcl
resource "volcenginecc_vke_permission" "visitor" {
  role_domain    = "namespace"
  cluster_id     = var.cluster_id
  namespace      = "kube-public"
  role_name      = "vke:visitor"
  is_custom_role = false
  grantee_id     = var.iam_user_id
  grantee_type   = "User"
}
```

Do not add a shared verified example until the target grantee is created/imported intentionally, the permission reaches `Success`, a no-op plan is clean, and revocation on destroy is proven. Avoid granting permissions to the caller account as a shortcut during verification.

## ECS Image

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_ecs_deployment_set` | Verified | Standalone placement set create/no-op/destroy succeeded; see `volcenginecc-ecs-extras.md` |
| `volcenginecc_ecs_hpc_cluster` | Verified | Standalone HPC cluster create/no-op/destroy succeeded; see `volcenginecc-ecs-extras.md` |
| `volcenginecc_ecs_launch_template_version` | Verified | Version 2 on a real launch template create/no-op/destroy succeeded; see `volcenginecc-ecs-launch-template-version.md` |
| `volcenginecc_ecs_image` | Dependency-bound | Requires a valid system disk snapshot, instance, snapshot group, or import image URL |

`ecs_image` is not part of the verified ECS examples because the low-cost EBS snapshot example creates a data disk snapshot, while ECS custom images require a system disk snapshot, whole-instance source, snapshot group, or imported image object:

```hcl
resource "volcenginecc_ecs_image" "from_system_snapshot" {
  image_name  = "cc-iac-image"
  snapshot_id = var.system_disk_snapshot_id
  project_name = "default"
}
```

Do not create an image from a data disk snapshot. Retry only after a throwaway ECS instance with a system disk snapshot is available, or after a test image object is staged in TOS for import. Verify create, no-op, and image deletion because custom images can keep snapshot references and block cleanup.

## IAM Federation and Access Keys

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_iam_user` | Verified | User create/no-op/destroy succeeded without login password or access key; see `volcenginecc-iam-users.md` |
| `volcenginecc_iam_group` | Verified | Group create/no-op/destroy succeeded with global read-only policy scope; see `volcenginecc-iam-users.md` |
| `volcenginecc_iam_oidc_provider` | Verified | Public issuer OIDC provider create/no-op/destroy succeeded; see `volcenginecc-iam-oidc-provider.md` |
| `volcenginecc_iam_saml_provider` | Verified | Role SSO SAML provider create/no-op/destroy succeeded; see `volcenginecc-iam-saml-provider.md` |
| `volcenginecc_iam_accesskey` | Sensitive-state blocked | Successful create would write `secret_access_key` into Terraform state |

Do not add `iam_accesskey` to reusable examples. The provider schema exposes `secret_access_key` as a read-only attribute, so a create writes the generated secret to Terraform state even if outputs are sensitive. If a deployment requires access keys, keep the state encrypted and access-controlled, rotate immediately, and never commit state or plans.

Do not use placeholder IdP URLs, fake thumbprints, or generated private keys in shared examples. Retry only with a disposable IdP metadata document whose certificate is public metadata, not a private key.

## CloudIdentity

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_cloudidentity_group` | Permission-blocked | `AccessDenied: User is not authorized to perform: cloudidentity:CreateGroup` during create |
| `volcenginecc_cloudidentity_permission_set` | Permission-blocked | `AccessDenied: User is not authorized to perform: cloudidentity:CreatePermissionSet` during create |
| `volcenginecc_cloudidentity_user` | Not applied | Requires CloudIdentity permission and writes initial password to Terraform state |
| `volcenginecc_cloudidentity_permission_set_assignment` | Dependency-blocked | Requires permission set plus real principal and target account IDs |
| `volcenginecc_cloudidentity_permission_set_provisioning` | Dependency-blocked | Requires permission set plus real target account ID |
| `volcenginecc_cloudidentity_user_provisioning` | Dependency-blocked | Requires real principal and target account IDs |

Current-account retry on 2026-05-30 in `<tmp-workdir>` used only a manual group and a system `ReadOnlyAccess` permission set, avoiding user password state and cross-account assignment/provisioning. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before any resource IDs were created:

```text
EventTime: 2026-05-30T13:30:42+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: cloudidentity:CreateGroup on resource:
TypeName: Volcengine::CloudIdentity::Group
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T13:30:42+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: cloudidentity:CreatePermissionSet on resource:
TypeName: Volcengine::CloudIdentity::PermissionSet
Operation: CREATE
OperationStatus: FAILED
```

No CloudIdentity resources were created; Terraform state remained empty. Retry group and permission set only after CloudIdentity create permissions are granted. Keep `cloudidentity_user` out of default examples unless the user explicitly accepts password-in-state risk, and add assignment/provisioning only with deliberate principal and target account IDs.

## Organization and Specialty Services

Resources not promoted to default cloud deployment examples:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_organization_organization` | Business-semantics blocked | Creates or manages the enterprise organization itself; requires a dedicated test organization and explicit owner approval |
| `volcenginecc_organization_unit` | Business-semantics blocked | Mutates enterprise organization structure; requires a known parent OU and cleanup policy |
| `volcenginecc_organization_account` | Business-semantics blocked | Creates or manages member accounts and may store account password/contact data in Terraform state |
| `volcenginecc_organization_service_control_policy` | Business-semantics blocked | Creates account/OU guardrail policies; a deny policy can break access if attached incorrectly |
| `volcenginecc_ark_endpoint` | Product/cost dependency blocked | Requires a real ModelArk foundation/custom model choice and creates a billable inference endpoint |
| `volcenginecc_escloud_instance` | Product/cost/sensitive-state blocked | Creates a billable search cluster and requires admin password stored in Terraform state |
| `volcenginecc_hbase_instance` | Product/cost blocked | Creates a billable HBase cluster with multi-node storage footprint |
| `volcenginecc_emr_cluster` | Product/cost/sensitive-state blocked | Creates a billable EMR cluster and can require ECS keypair/password/TOS/bootstrap dependencies |
| `volcenginecc_emr_node_group` | Dependency-blocked | Requires a running EMR cluster |
| `volcenginecc_emr_cluster_user` | Dependency/sensitive-state blocked | Requires a running EMR cluster and user credential lifecycle |
| `volcenginecc_emr_cluster_user_group` | Dependency-blocked | Requires a running EMR cluster and user/group model |
| `volcenginecc_gtm_pool` | Dependency-blocked | Requires an existing GTM instance ID; the provider exposes pool only, not GTM instance creation |
| `volcenginecc_fwcenter_dns_control_policy` | Dependency/business-policy blocked | Requires an existing Internet Firewall instance ID and creates a domain denylist policy |

These resources were inspected against provider docs but not applied in the shared cloud deployment baseline because they either alter organization-level business state, create high-cost specialty service instances, require an existing product instance that the provider cannot create, or would store credentials/private operational data in Terraform state. Do not add default examples for them without an explicit product-specific goal, cost approval, and a disposable test account or instance.

## RDS MySQL Extras

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_rdsmysql_endpoint` | Drift-blocked for default example | Custom direct endpoint create/delete succeeded, but no-op plan tried to update `addresses.domain_prefix` and failed because the domain prefix already exists |
| `volcenginecc_rdsmysql_backup` | Verified (with timing caveat) | `backup_method` must be `Snapshot` (`Physical`/`Logical` return `参数BackupMethod值无效`). A fresh instance runs an initial backup, so the first manual backup can hit `OperationDenied_BackupJobExists`; re-apply after it finishes. Create + clean no-op confirmed 2026-06-17 |

The custom endpoint retry used a verified MySQL instance in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```hcl
resource "volcenginecc_rdsmysql_endpoint" "custom" {
  instance_id         = volcenginecc_rdsmysql_instance.main.instance_id
  endpoint_name       = "${local.prefix}-custom"
  endpoint_type       = "Custom"
  connection_mode     = "Direct"
  nodes               = "Primary"
  read_write_mode     = "ReadWrite"
  read_write_spliting = false

  addresses = [
    {
      domain_prefix  = "cciacmysql"
      dns_visibility = false
      port           = "3306"
    }
  ]
}
```

Creation succeeded and returned endpoint ID `mysql-ae90e8397914-custom-058a`, and later destroy deleted it successfully. The first follow-up plan was not clean because readback dropped `addresses.domain_prefix`; reapply attempted to update the already-created address and failed:

```text
OperationDenied_Common: domain prefix already exists
TypeName: Volcengine::RDSMySQL::Endpoint
Operation: UPDATE
OperationStatus: FAILED
```

Do not include `rdsmysql_endpoint` in generated examples until a shape produces create, no-op plan, and destroy without suppressing meaningful drift.

Manual backup creation was tested with both documented method values. The `Physical` attempt failed:

```text
InvalidParameter: 参数BackupMethod值无效
TypeName: Volcengine::RDSMySQL::Backup
Operation: CREATE
OperationStatus: FAILED
```

The `Logical` attempt with `backup_type = "Full"` also returned the same invalid backup method error. On 2026-06-17, `backup_method = "Snapshot"` with `backup_type = "Full"` created successfully and reached a clean no-op plan. The only caveat is timing: a newly created instance runs an initial backup job, so the first manual backup can fail with `OperationDenied_BackupJobExists` and needs a re-apply once the instance's backup job finishes. It is kept out of the shared example to avoid that first-apply flakiness, but the verified shape is `backup_method = "Snapshot"`, `backup_type = "Full"`.

During this retry, dependent database/account creation initially failed with `InstanceIsNotRunning` immediately after the instance became visible. Waiting about 90 seconds and re-running apply succeeded. A later destroy attempt hit the same status window while deleting the account; after retry, database/account, instance, allowlist, endpoint, VPC, subnet, and route table were all destroyed and final Terraform state was empty.

## veFaaS Remaining Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vefaas_function` | Verified | Function create/no-op/destroy succeeded with a valid Python ZIP containing root-level `index.py`; see `volcenginecc-vefaas.md` |
| `volcenginecc_vefaas_release` | Partially verified | Successful release create/no-op succeeded; delete is not supported after final `finished` status |
| `volcenginecc_vefaas_timer` | Verified | Disabled timer trigger create/no-op/destroy succeeded after release |
| `volcenginecc_vefaas_sandbox` | Lifecycle-only/drift-blocked | Native/image function, release, sandbox create/destroy succeeded with a pre-cached public sandbox image, but follow-up plans drift on `volcenginecc_vefaas_release` computed fields. |
| `volcenginecc_vefaas_kafka_trigger` | Dependency-blocked | Requires Kafka instance/topic and SASL credentials; current Kafka instance create still fails with Cloud Control `ServiceInternalError` |

The initial empty-ZIP function create succeeded, but release failed with:

```text
revision_build_failed: function failed to build revision source: failed to download and validate source: failed to validate entry file for runtime: python3.9/v1, err: Unable to find function entry (index.py). Please make sure the root directory contains function entry.
```

Updating that existing function from an empty ZIP to a valid ZIP failed server-side:

```text
ServiceInternalError: InternalServiceError: Internal error occurred: panic: [happened in biz handler, method=VeFaaSServiceV2.UpdateFunction, please check the panic at the server side] runtime error: slice bounds out of range [:-1].
TypeName: Volcengine::VEFAAS::Function
Operation: UPDATE
OperationStatus: FAILED
```

The verified path creates the function with valid ZIP source from the start.

Creating a timer before a successful release failed with:

```text
InvalidRequest: InvalidOperation: function has not been fully released yet, please release it first
TypeName: Volcengine::VEFAAS::Timer
Operation: CREATE
OperationStatus: FAILED
```

Deleting a successful release failed with:

```text
AccessDenied: InvalidOperation: This operation is not supported., release already in final status: finished
TypeName: Volcengine::VEFAAS::Release
Operation: DELETE
OperationStatus: FAILED
```

For cleanup after a successful release, run `terraform state rm volcenginecc_vefaas_release.main`, then destroy the timer/function resources.

Creating a sandbox for the verified Python function failed with:

```text
AccessDenied: InvalidOperation: fn is not webserver sandbox function, not support to create sandbox instance
TypeName: Volcengine::VEFAAS::Sandbox
Operation: CREATE
OperationStatus: FAILED
```

A later native/image sandbox retry used `runtime = "native/v1"`, `source_type = "image"`, `source = "nginx:1.25-alpine"`, `command = "nginx -g 'daemon off;'"`, `port = 80`, and `cpu_strategy = "always"` on the function, release, and sandbox path. `fmt`, `init`, `validate`, and `plan` passed, but apply failed on function create:

```text
NotFound: ResourceNotFound: Sandbox image not found in pre cache sandbox image list, you need to precache your sandbox image first
TypeName: Volcengine::VEFAAS::Function
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T06:46:56+08:00
```

No resources were created by the native/image retry; Terraform state remained empty. Do not add a verified `vefaas_sandbox` example until a pre-cached sandbox image is available and function create, release, sandbox create, no-op plan, and destroy all succeed.

Current-account sandbox retries on 2026-05-30 found usable pre-cached sandbox images via `ve vefaas ListSandboxImages --body '{"ImageType":"public","PageNumber":1,"PageSize":5}'` and `--body '{"ImageType":"private","PageNumber":1,"PageSize":5}'`. `ImageType` must be lowercase; uppercase values were rejected as invalid. The public All-in-one image group was available, and the account had four successful historical pre-cache tickets.

Two pre-cached-image shapes still failed at sandbox startup:

```text
EventTime: 2026-05-30T12:08:19+08:00
TaskID: task-<id>
InvalidOperation: error_code: "function_exited", error_message "function exited unexpectedly(exit status 127) ... bash: ./run.sh: No such file or directory"
TypeName: Volcengine::VEFAAS::Sandbox
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T12:09:44+08:00
TaskID: task-<id>
InvalidOperation: error_code: "function_exited", error_message "function exited unexpectedly(exit status 1) ... /etc/sudoers.d/: Is a directory"
TypeName: Volcengine::VEFAAS::Sandbox
Operation: CREATE
OperationStatus: FAILED
```

The working lifecycle shape used public image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3`, `image_id = "kwdxncbgsn"`, and command `python3 -m http.server 8080 --bind 0.0.0.0`. Function, release, and sandbox created successfully; sandbox reached `Ready`. Follow-up plan was not clean because `volcenginecc_vefaas_release` proposed an in-place update on computed fields. Cleanup removed the finished release from Terraform state, then destroyed sandbox and function. Sandbox destroy took about 66s; final Terraform state was empty.

## RDS SQL Server

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_rdsmssql_allow_list` | Lifecycle-verified | Create/no-op/delete succeeded after permissions were granted; deletion may need to wait for association count to drop to 0 |
| `volcenginecc_rdsmssql_instance` | Destroy-caveat | Basic SQL Server 2019 Standard create and no-op succeeded; VPC cleanup can remain blocked by delayed RDS service-managed security group release |

Minimal configuration validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`. The first apply created only the network dependencies, then failed on allowlist creation:

```text
AccessDenied: User is not authorized to perform: rds_mssql:CreateAllowList on resource: trn:iam::<account-id>:project/default,trn:vpc:cn-beijing:<account-id>:securitygroup/*
TypeName: Volcengine::RDSMsSQL::AllowList
Operation: CREATE
OperationStatus: FAILED
```

A second apply without the allowlist dependency was used only to test the instance API and failed with:

```text
AccessDenied: User is not authorized to perform: rds_mssql:CreateDBInstance on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::RDSMsSQL::Instance
Operation: CREATE
OperationStatus: FAILED
```

Temporary VPC, subnet, and route table resources were destroyed successfully; final Terraform state was empty.

Latest allowlist-only retry in `cn-beijing`: a standalone `volcenginecc_rdsmssql_allow_list` validated and planned successfully, then failed with the same permission denial before any resources were created:

```text
EventTime: 2026-05-30T09:53:23+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: rds_mssql:CreateAllowList on resource: trn:iam::<account-id>:project/default,trn:vpc:cn-beijing:<account-id>:securitygroup/*
TypeName: Volcengine::RDSMsSQL::AllowList
Operation: CREATE
OperationStatus: FAILED
```

Retried the standalone allowlist shape again on 2026-05-30 at 13:59 with allow list name `cc-iac-mssql-allow-retry`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply still failed before creating any resource:

```text
EventTime: 2026-05-30T13:59:24+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: rds_mssql:CreateAllowList on resource: trn:iam::<account-id>:project/default,trn:vpc:cn-beijing:<account-id>:securitygroup/*
TypeName: Volcengine::RDSMsSQL::AllowList
Operation: CREATE
OperationStatus: FAILED
```

Terraform state remained empty. This permission boundary was resolved by later grants; the remaining issue is destroy-time backend cleanup.

After the user reported MSSQL permissions were added, a 2026-05-30 retry in `<tmp-workdir>` used a standalone allowlist plus minimal Basic SQL Server 2019 Standard instance, VPC, subnet, and route table. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded. The allowlist created successfully with ID `<acl-id>`, proving `rds_mssql:CreateAllowList` was granted. The instance failed three times, including after 90s and 180s waits, because RDS MSSQL could not see the Terraform-created VPC even though `ve vpc DescribeVpcs` returned it as `Available`:

```text
EventTime: 2026-05-30T15:23:26+08:00
TaskID: task-<id>
NotFound: VpcIDNotFound: The specified VpcID does not exist.
TypeName: Volcengine::RDSMsSQL::Instance
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T15:25:23+08:00
TaskID: task-<id>
NotFound: VpcIDNotFound: The specified VpcID does not exist.
TypeName: Volcengine::RDSMsSQL::Instance
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T15:29:12+08:00
TaskID: task-<id>
NotFound: VpcIDNotFound: The specified VpcID does not exist.
TypeName: Volcengine::RDSMsSQL::Instance
Operation: CREATE
OperationStatus: FAILED
```

Discovery confirmed `cn-beijing-a` supports `SQLServer_2019_Std` Basic and spec `rds.mssql.3il.x8.medium.s1`, so this is not an obvious zone/spec mismatch. Destroy removed the allowlist, route table, subnet, and VPC; final Terraform state was empty. `ve rdsmssql DescribeAllowLists` for `cc-iac-mssql-retry-allow` returned an empty list, `ve rdsmssql DescribeDBInstances` for `cc-iac-mssql-retry-instance` returned `Total: 0`, and exact VPC-name matching for `cc-iac-mssql-retry-vpc` returned no rows. Retry the instance with an older, pre-existing disposable VPC/subnet or after the RDS MSSQL VPC visibility path is confirmed.

After another permission grant, a 2026-05-30 retry in `<tmp-workdir>` created the full minimal SQL Server path successfully. The configuration used VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, allowlist `<acl-id>`, and Basic SQL Server 2019 Standard instance `<db-instance-id>` with spec `rds.mssql.3il.x8.medium.s1`. Create took about 4m37s and a follow-up `terraform plan -detailed-exitcode` returned `No changes`, so the earlier `VpcIDNotFound` no longer reproduces.

RDS SQL Server is promoted only as a lifecycle/destroy-caveat example, not as a clean verified example, because destroy did not fully converge in the same run. The instance delete returned success after about 10s, and later `DescribeDBInstances` returned `Total: 0`. However, subnet deletion initially failed while two RDS service-managed ENIs were still attached; after about 60s, `DescribeNetworkInterfaces --SubnetId subnet-<id>` returned `TotalCount: 0` and the allowlist `AssociatedInstanceNum` dropped to `0`. A second destroy removed the allowlist and subnet, but VPC deletion remained blocked by the RDS service-managed security group `sg-<id>`:

```text
EventTime: 2026-05-30T17:51:50+08:00
TaskID: task-<id>
InvalidRequest: InvalidVpc.InUse: The specified VPC has dependent resource of a security group.
TypeName: Volcengine::VPC::VPC
Operation: DELETE
OperationStatus: FAILED
```

Manual deletion of `sg-<id>` failed because it is service-managed:

```text
Forbidden: You are not authorized to perform operations on the specified security group.
The specified security group is a service-managed security group.
```

After another 3 minutes, `DescribeDBInstances` still returned `Total: 0` and `DescribeNetworkInterfaces --VpcId vpc-<id>` still returned `TotalCount: 0`, but `DescribeSecurityGroups --VpcId vpc-<id>` still showed the service-managed security group plus the default security group. After another 5 minutes, the service-managed security group was still present, and a final `terraform destroy` failed with the same VPC dependency:

```text
EventTime: 2026-05-30T18:04:52+08:00
TaskID: task-<id>
InvalidRequest: InvalidVpc.InUse: The specified VPC has dependent resource of a security group.
TypeName: Volcengine::VPC::VPC
Operation: DELETE
OperationStatus: FAILED
```

Current residue after the retry: Terraform state in `<tmp-workdir>` contains only `volcenginecc_vpc_vpc.main` for VPC `vpc-<id>`; the temporary binary `tfplan` was deleted because it may contain sensitive variables. Cloud-side residue is VPC `vpc-<id>` plus service-managed security group `sg-<id>` (`Mssql Managed Security Group`) and its default security group. Instance `<db-instance-id>`, allowlist `<acl-id>`, RDS ENIs, route table, and subnet were deleted or no longer visible. Continue cleanup by waiting for the RDS service-managed security group to disappear, then rerun `terraform destroy` to remove the VPC. Keep MSSQL out of the clean verified count until this cleanup behavior is understood.

After the user successfully created and released a separate RDS MySQL instance, a 2026-05-31 retry in `<tmp-workdir>` used the shared `assets/examples/volcenginecc-rdsmssql` shape with prefix `cc-iac-mssql-0531`, CIDR `10.118.0.0/16`, and the 60s `time_sleep` create/destroy delay. Apply succeeded: VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, allowlist `<acl-id>`, and SQL Server instance `<db-instance-id>` were created successfully. Instance creation took 4m45s and a follow-up plan returned `No changes`.

Destroy order was correct with the updated dependency graph: SQL Server instance deleted first in 12s, then `time_sleep` waited 60s, then the allowlist, route table, and subnet all deleted successfully. VPC deletion still failed because the RDS service-managed security group remained:

```text
EventTime: 2026-05-31T02:40:06+08:00
TaskID: task-<id>
InvalidRequest: InvalidVpc.InUse: The specified VPC has dependent resource of a security group.
TypeName: Volcengine::VPC::VPC
Operation: DELETE
OperationStatus: FAILED
```

Cloud-side checks after the failed destroy showed `DescribeDBInstances` `Total: 0`, `DescribeAllowLists` empty, and `DescribeNetworkInterfaces --VpcId vpc-<id>` `TotalCount: 0`, but `DescribeSecurityGroups --VpcId vpc-<id>` still returned default security group `sg-<id>` and service-managed MSSQL security group `sg-<id>`. `DescribeVpcs --VpcIds ["vpc-<id>"]` returned `TotalCount: 0`, so the VPC and security-group views are inconsistent. An additional 60s wait followed by another `terraform destroy` failed with the same VPC security-group dependency:

```text
EventTime: 2026-05-31T02:42:03+08:00
TaskID: task-<id>
InvalidRequest: InvalidVpc.InUse: The specified VPC has dependent resource of a security group.
TypeName: Volcengine::VPC::VPC
Operation: DELETE
OperationStatus: FAILED
```

Current residue from the 2026-05-31 retry: Terraform state in `<tmp-workdir>` contains only `volcenginecc_vpc_vpc.main` for VPC `vpc-<id>`; cloud-side residue is the VPC/security-group index entry plus service-managed MSSQL security group `sg-<id>` and default security group `sg-<id>`. Keep this example lifecycle-verified only. The 60s sleep fixes Terraform ordering and the short allowlist/subnet release window, but does not fix this service-managed SG cleanup issue.

The shared lifecycle example uses this shape:

```hcl
resource "volcenginecc_rdsmssql_allow_list" "app" {
  project_name    = "default"
  allow_list_name = "cc-iac-mssql-allow"
  allow_list_type = "IPv4"
  user_allow_list = "10.96.0.0/16"
}

resource "volcenginecc_rdsmssql_instance" "main" {
  node_spec              = "rds.mssql.3il.x8.medium.s1"
  zone_id                = "cn-beijing-a"
  subnet_id              = volcenginecc_vpc_subnet.main.subnet_id
  db_engine_version      = "SQLServer_2019_Std"
  instance_type          = "Basic"
  storage_space          = 20
  vpc_id                 = volcenginecc_vpc_vpc.main.vpc_id
  instance_name          = "cc-iac-mssql-instance"
  super_account_password = var.mssql_password
  server_collation       = "Chinese_PRC_CI_AS"
  time_zone              = "China Standard Time"
  project_name           = "default"
  maintenance_time       = "18:00Z-21:59Z"
  allow_list_ids         = [volcenginecc_rdsmssql_allow_list.app.allow_list_id]

  charge_info = {
    charge_type = "PostPaid"
  }
}
```

`assets/examples/volcenginecc-rdsmssql` exists as a lifecycle/destroy-caveat example only. It adds a `time_sleep` 60s create/destroy delay between network readiness and SQL Server lifecycle, but operators should still poll `DescribeDBInstances`, `DescribeNetworkInterfaces`, `DescribeAllowLists`, and `DescribeSecurityGroups` every 60s before rerunning destroy if the VPC is blocked. `super_account_password` is sensitive in plan output but will still be stored in Terraform state.

## veDB MySQL

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vedbm_allow_list` | Verified (create) | `vedbm:CreateAllowList` is now granted; standalone allowlist creates successfully (2026-06-17) |
| `volcenginecc_vedbm_instance` | Provider-blocked | Allowlist permission granted, but create fails with `InvalidChargeType: The Charge Type is only support PostPaid/PrePaid` even with `charge_detail.charge_type = "PostPaid"`, `storage_charge_type`, and `number` set per the provider example; likely a provider 0.0.46 charge mapping bug |
| `volcenginecc_vedbm_account` | Dependency-blocked | Requires a running veDBM instance; account password is stored in Terraform state |
| `volcenginecc_vedbm_database` | Dependency-blocked | Requires a running veDBM instance and optional account grants |
| `volcenginecc_vedbm_endpoint` | Dependency-blocked | Requires a running veDBM instance and node selection |
| `volcenginecc_vedbm_backup` | Dependency-blocked | Requires a running veDBM instance |

Current-account retry on 2026-05-30 in `<tmp-workdir>` used only a standalone IPv4 allowlist to avoid creating a billable database instance or storing database passwords. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before an allowlist ID was created:

```text
EventTime: 2026-05-30T13:29:27+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: vedbm:CreateAllowList on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::VEDBM::AllowList
Operation: CREATE
OperationStatus: FAILED
```

No veDBM resources were created; Terraform state remained empty. After `vedbm:CreateAllowList` and `vedbm:CreateDBInstance` are granted, retry the standalone allowlist first. Add `vedbm_instance` only with a sensitive password variable and a disposable VPC/subnet, then add account, database, endpoint, and backup in later applies after the instance reaches a stable running state.

## BMQ

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_bmq_instance` | Teardown/drift-blocked | After `ServiceRoleForBmq` was authorized (2026-06-17) the instance creates (~16m) and reaches instance-level no-op, but the security group still shows the generic default-egress readback drift and destroy needs multiple passes while BMQ service-managed ENIs release |
| `volcenginecc_bmq_group` | Dependency-blocked | Requires a successfully created BMQ instance |

As of 2026-06-17, `ServiceRoleForBmq` is authorized and `volcenginecc_bmq_instance` creates successfully (about 16 minutes) with a clean instance-level follow-up plan. It is still not promoted to a verified example: the `volcenginecc_vpc_security_group` shows the generic default-egress readback drift, and `terraform destroy` needs two or three passes because BMQ leaves service-managed ENIs that block security-group/subnet deletion until they release. The historical service-role-missing evidence is kept below.

BMQ API discovery succeeded in `cn-beijing`: `ve bmq ListSpecifications` returned `bmq.standard` as available and `ve bmq DescribeAvailableZones` showed `cn-beijing-a`, `cn-beijing-c`, and `cn-beijing-d` not sold out. The Terraform configuration validated and planned successfully with provider `volcengine/volcenginecc ~> 0.0.46`, using VPC, subnet, route table, security group, `bmq.standard`, and a private overlay endpoint. Apply created only the network dependencies, then failed on BMQ instance creation:

```text
AccessDenied: User is not authorized to perform: bmq:CreateInstance on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::BMQ::Instance
Operation: CREATE
OperationStatus: FAILED
```

Temporary VPC, subnet, route table, and security group resources were destroyed successfully; final Terraform state was empty.

Current-account retry on 2026-05-30 in `<tmp-workdir>` used VPC, subnet, route table, security group, and a private overlay `volcenginecc_bmq_instance`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. A first apply created VPC `vpc-<id>`, subnet `subnet-<id>`, and route table `vtb-<id>`, but the security group create hit a transient VPC control-plane conflict:

```text
EventTime: 2026-05-30T12:01:40+08:00
TaskID: task-<id>
InvalidOperation.Conflict: The specified resource operation conflicts.
TypeName: Volcengine::VPC::SecurityGroup
Operation: CREATE
OperationStatus: FAILED
```

Rerunning apply after the VPC settled created security group `sg-<id>`, then the BMQ instance failed at the service permission boundary:

```text
EventTime: 2026-05-30T12:02:28+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: bmq:CreateInstance on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::BMQ::Instance
Operation: CREATE
OperationStatus: FAILED
```

Destroy removed the security group, route table, subnet, and VPC; final Terraform state was empty. `DescribeVpcs --VpcName cc-iac-bmq-current-vpc` returned `TotalCount: 0`. `ve bmq ListInstances --Region ...` was not usable as a residue check because that CLI command rejected `--Region`; no BMQ instance ID was created because `CreateInstance` failed before resource creation.

After BMQ create permission was granted, a 2026-05-30 retry in `<tmp-workdir>` again hit the transient VPC security-group conflict on the first apply, then succeeded on a second apply after the VPC settled. BMQ instance creation then moved past the earlier IAM permission boundary and failed because the service-linked role is missing:

```text
EventTime: 2026-05-30T15:44:07+08:00
TaskID: task-<id>
NotFound: RoleNotExist: Role 'trn:iam::<account-id>:role/ServiceRoleForBmq' does not exist.
TypeName: Volcengine::BMQ::Instance
Operation: CREATE
OperationStatus: FAILED
```

Cleanup destroyed the security group, route table, subnet, and VPC. Final Terraform state was empty; exact VPC-name matching for `cc-iac-bmq-retry-vpc` returned no rows, and `ve bmq SearchInstances` returned `TotalCount: 0`.

After another permission grant, a 2026-05-30 retry in `<tmp-workdir>` used the same private overlay shape and created VPC `vpc-<id>`, subnet `subnet-<id>`, route table `vtb-<id>`, and security group `sg-<id>`. The BMQ instance request then ran for about 16 minutes. Terraform reported the Cloud Control task as failed:

```text
EventTime: 2026-05-30T16:53:19+08:00
TaskID: task-<id>
InvalidRequest: InvalidParameter: parameter is invalid, pls check parameters
TypeName: Volcengine::BMQ::Instance
Operation: CREATE
OperationStatus: FAILED
```

However, `ve bmq SearchInstances --body '{"SearchKey":"cc-iac-bmq-1636"}'` immediately showed the instance was actually created and `RUNNING` as `bmq-<id>`. Because Terraform did not put the instance in state after the failed task, import was required before cleanup:

```text
terraform import volcenginecc_bmq_instance.main bmq-<id>
```

The imported instance still did not converge to a clean no-op plan. Terraform planned updates for `endpoints`, computed `tags`, and the security group had an extra default egress rule (`description = "放通全部流量"`, `priority = 100`) in addition to the configured egress rule. This means the shape is not suitable for a verified example even though the cloud instance can be created.

Destroy deleted the BMQ instance, then the first network cleanup attempt failed because BMQ-managed VCI ENIs were still attached to the security group:

```text
EventTime: 2026-05-30T16:55:34+08:00
TaskID: task-<id>
AccessDenied: Forbidden: You are not authorized to perform operations on the specified elastic network interface. The specified elastic network interface is a service-managed elastic network interface.
TypeName: Volcengine::VPC::SecurityGroup
Operation: DELETE
OperationStatus: FAILED
```

After `ve vpc DescribeNetworkInterfaces --VpcId vpc-<id>` and `--SubnetId subnet-<id>` returned no rows, rerunning `terraform destroy` removed the security group, route table, subnet, and VPC. Final Terraform state was empty; `ve bmq SearchInstances` returned `TotalCount: 0`, `ve vpc DescribeVpcs --VpcName cc-iac-bmq-1636-vpc` returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`.

When `ServiceRoleForBmq` exists and BMQ can assume it, retry with this shape:

```hcl
resource "volcenginecc_bmq_instance" "main" {
  name                   = "cc-iac-bmq"
  billing_type           = "POST"
  project_name           = "default"
  specification          = "bmq.standard"
  vpc_id                 = volcenginecc_vpc_vpc.main.vpc_id
  message_retention      = 1
  security_group_id_list = [volcenginecc_vpc_security_group.app.security_group_id]
  subnet_id_list         = [volcenginecc_vpc_subnet.main.subnet_id]
  zone_id_list           = ["cn-beijing-a"]

  endpoints = {
    overlay = {
      vpc_ids = [volcenginecc_vpc_vpc.main.vpc_id]
    }
  }
}
```

Do not add an `assets/examples/volcenginecc-bmq` verified example until apply, no-op plan, and destroy all succeed. The provider exposes `volcenginecc_bmq_instance` and `volcenginecc_bmq_group`, but no `volcenginecc_bmq_topic`; BMQ topics still need the `ve bmq CreateTopic` API or another tool path.

## File Storage

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_filenas_instance` | Verified | FileNAS `Extreme/NFS/Standard` create/no-op/destroy succeeded; see `volcenginecc-filenas.md` |
| `volcenginecc_filenas_snapshot` | Drift-blocked for default example | Create/delete succeeded, but no-op plan repeatedly showed `retention_days = -1 -> 2147483647` |
| `volcenginecc_filenas_mount_point` | Dependency-blocked | Requires `permission_group_id`; provider `0.0.46` has no FileNAS permission group resource |
| `volcenginecc_efs_file_system` | Verified | EFS `Premium/Premium_125` create/no-op/destroy succeeded; see `volcenginecc-efs.md` |
| `volcenginecc_vepfs_instance` | Service-internal blocked | `ServiceInternalError: InternalError: Service has some internal Error` during create |
| `volcenginecc_vepfs_mount_service` | Dependency/service-catalog blocked | Requires vePFS instance; `ve vepfs DescribeMountServiceNodeTypes` returned empty node type lists in Beijing |

EFS minimal configuration validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, using `cn-beijing-a`, `Premium`, `Premium_125`, and provisioned bandwidth `300`. Apply failed immediately with:

```text
AccessDenied: AccessDenied: User is not authorized to perform: efs:CreateFileSystem on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::EFS::FileSystem
Operation: CREATE
OperationStatus: FAILED
```

No EFS resources were created; Terraform state remained empty.

Current-account retry on 2026-05-30 used the same minimal shape in `<tmp-workdir>`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed with the same permission boundary:

```text
EventTime: 2026-05-30T10:45:47+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: efs:CreateFileSystem
```

Retried the same standalone EFS file system shape again on 2026-05-30 at 14:04 with file system name `cc-iac-efs-retry`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply still failed before creating any resource:

```text
EventTime: 2026-05-30T14:04:03+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: efs:CreateFileSystem on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::EFS::FileSystem
Operation: CREATE
OperationStatus: FAILED
```

Post-failure checks: `terraform state list` returned empty in the earlier retry, and `ve efs DescribeFileSystems` with `FileSystemName=cc-iac-efs-current` returned `TotalCount: 0`. The 14:04 retry returned `Identifier: null`; a cloud-side `ve efs DescribeFileSystems` check with `FileSystemName=cc-iac-efs-retry` returned `TotalCount: 0`.

After `efs:CreateFileSystem` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified the EFS file system lifecycle. The initial tagged shape created successfully but a follow-up plan showed a tag drift because `type = "Custom"` read back without `type`. Removing the `tags` block produced a clean no-op plan. The verified EFS file system `cc-iac-efs-retry` created with ID `<efs-id>`, `terraform plan -detailed-exitcode` returned `No changes`, destroy removed the file system, final Terraform state was empty, and `ve efs DescribeFileSystems --body '{"FileSystemName":"cc-iac-efs-retry"}'` returned `TotalCount: 0`.

The verified example now lives in `assets/examples/volcenginecc-efs`; validation notes and pitfalls live in `references/volcenginecc-efs.md`. Use this shape:

```hcl
resource "volcenginecc_efs_file_system" "main" {
  file_system_name    = "cc-iac-efs-fs"
  description         = "volcenginecc EFS example file system"
  charge_type         = "PayAsYouGo"
  zone_id             = "cn-beijing-a"
  instance_type       = "Premium"
  performance_density = "Premium_125"
  project_name        = "default"

  performance = {
    bandwidth_mode        = "Provisioned"
    provisioned_bandwidth = 300
  }
}
```

FileNAS `volcenginecc_filenas_snapshot` was deliberately excluded from the verified default example even though create and delete both succeeded. The persistent no-op drift is caused by generated provider schema: `retention_days` is read-only/computed but also has default `2147483647`, while the API reads back `-1`.

```text
~ retention_days = -1 -> 2147483647
```

Do not use `ignore_changes = [retention_days]`; Terraform warns that the attribute is provider-decided and the ignore rule is redundant. If snapshots are needed anyway, document this residual drift in the plan review.

FileNAS mount points need an existing permission group:

```hcl
resource "volcenginecc_filenas_mount_point" "app" {
  file_system_id      = volcenginecc_filenas_instance.main.file_system_id
  mount_point_name    = "cc-iac-filenas-mount"
  permission_group_id = var.filenas_permission_group_id
  subnet_id           = var.subnet_id
  vpc_id              = var.vpc_id
}
```

The `ve filenas CreatePermissionGroup` API exists, but the provider does not expose a matching `volcenginecc_filenas_permission_group` resource in `0.0.46`, so a from-scratch Terraform-only example would hide an unmanaged prerequisite.

vePFS sale discovery succeeded in `cn-beijing`: `ve vepfs DescribeZones` returned `OnSale` for `Advance_100` and `Performance` in `cn-beijing-a/b/c/d/e`. The Terraform configuration validated and planned successfully with VPC, subnet, route table, and `volcenginecc_vepfs_instance`, then failed on instance creation:

```text
AccessDenied: AccessDenied: User is not authorized to perform: vepfs:CreateFileSystem on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::VEPFS::Instance
Operation: CREATE
OperationStatus: FAILED
```

Temporary VPC, subnet, and route table resources were destroyed successfully; final Terraform state was empty.

Current-account retry on 2026-05-30 in `<tmp-workdir>` confirmed the same boundary. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. The temporary VPC/subnet/route table were created, then `volcenginecc_vepfs_instance` failed:

```text
EventTime: 2026-05-30T10:46:51+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: vepfs:CreateFileSystem
```

Retried the same VPC/subnet/route-table-backed shape again on 2026-05-30 at 14:05 with file system name `cc-iac-vepfs-retry-fs`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded. The temporary VPC `vpc-<id>`, subnet `subnet-<id>`, and route table `vtb-<id>` were created, then `volcenginecc_vepfs_instance` failed:

```text
EventTime: 2026-05-30T14:05:53+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: vepfs:CreateFileSystem on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::VEPFS::Instance
Operation: CREATE
OperationStatus: FAILED
```

Recovery: `terraform destroy` removed 3 temporary network resources. Final `terraform state list` returned empty, `ve vepfs DescribeFileSystems` with `FileSystemName=cc-iac-vepfs-current` returned `TotalCount: 0`, and the temporary VPC ID no longer appeared in `DescribeVpcs`. The 14:05 retry also ended with empty Terraform state, `ve vepfs DescribeFileSystems` for `cc-iac-vepfs-retry-fs` returned `TotalCount: 0`, and exact VPC-name matching for `cc-iac-vepfs-retry-vpc` returned no rows.

After `vepfs:CreateFileSystem` was granted, a 2026-05-30 retry in `<tmp-workdir>` created the temporary VPC, subnet, and route table successfully, then vePFS instance creation failed in the service backend:

```text
EventTime: 2026-05-30T15:51:47+08:00
TaskID: task-<id>
ServiceInternalError: InternalError: Service has some internal Error. Pls Contact With Admin.
TypeName: Volcengine::VEPFS::Instance
Operation: CREATE
OperationStatus: FAILED
```

Cleanup destroyed the route table, subnet, and VPC. Final Terraform state was empty, `ve vepfs DescribeFileSystems --body '{"FileSystemName":"cc-iac-vepfs-retry-fs"}'` returned `TotalCount: 0`, and exact VPC-name matching for `cc-iac-vepfs-retry-vpc` returned no rows. `ve vepfs DescribeMountServiceNodeTypes --body '{"ZoneId":"cn-beijing-a"}'` still returned `NodeTypeInfos: []`, so mount service remains blocked even after instance creation is fixed.

After another permission grant, a 2026-05-30 retry in `<tmp-workdir>` used the same VPC/subnet/route-table-backed vePFS shape after confirming `ve vepfs DescribeZones` reports `Advance_100` and `Performance` as `OnSale` in Beijing zones. The temporary VPC `vpc-<id>`, subnet `subnet-<id>`, and route table `vtb-<id>` created successfully, then vePFS instance creation still failed in the service backend:

```text
EventTime: 2026-05-30T17:08:14+08:00
TaskID: task-<id>
ServiceInternalError: InternalError: Service has some internal Error. Pls Contact With Admin.
TypeName: Volcengine::VEPFS::Instance
Operation: CREATE
OperationStatus: FAILED
```

Cleanup destroyed the route table, subnet, and VPC. Final `terraform state list` returned empty, `ve vepfs DescribeFileSystems --body '{"Filters":[{"Key":"FileSystemName","Value":"cc-iac-vepfs-1707-fs"}],"PageNumber":1,"PageSize":10}'` returned `TotalCount: 0`, exact VPC-name matching for `cc-iac-vepfs-1707-vpc` returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`.

When the vePFS service internal error is resolved, retry with this shape:

```hcl
resource "volcenginecc_vepfs_instance" "main" {
  file_system_name = "cc-iac-vepfs-fs"
  description      = "volcenginecc vePFS example file system"
  zone_id          = "cn-beijing-a"
  charge_type      = "PayAsYouGo"
  file_system_type = "VePFS"
  store_type       = "Advance_100"
  protocol_type    = "VePFS"
  project_name     = "default"
  capacity         = 8
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id        = volcenginecc_vpc_subnet.main.subnet_id
  version_number   = "1.4.0"
  enable_restripe  = false
}
```

Do not add `volcenginecc_vepfs_mount_service` until a vePFS instance is verified and `ve vepfs DescribeMountServiceNodeTypes` returns a usable `node_type`; it returned empty `NodeTypeInfos` for `cn-beijing-a`, `b`, `c`, `d`, and `e` in this account. The 2026-05-30 retry still returned `NodeTypeInfos: []` for `cn-beijing-a`.

## Logs and Monitoring

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_tls_project` | Verified | Project create/no-op/destroy succeeded; see `volcenginecc-tls.md` |
| `volcenginecc_tls_topic` | Verified | Topic create/no-op/destroy succeeded; see `volcenginecc-tls.md` |
| `volcenginecc_tls_index` | Verified | Index create/no-op/destroy succeeded; see `volcenginecc-tls.md` |
| `volcenginecc_tls_rule` | Verified | Minimal host file rule create/no-op/destroy succeeded without `host_group_infos`; see `volcenginecc-tls.md` |
| `volcenginecc_tls_consumer_group` | Verified | Consumer group create/no-op/destroy succeeded with `allow_consume = true` topic; see `volcenginecc-tls.md` |
| `volcenginecc_tls_schedule_sql_task` | Verified | Disabled bounded scheduled SQL task create/no-op/destroy succeeded with indexed source/destination topics; see `volcenginecc-tls.md` |
| `volcenginecc_tls_shipper` | Drift-blocked for default example | TOS shipper create/delete worked, but no-op drifted `status = true -> false`; TOS bucket cleanup hit long Cloud Control waiter |
| `volcenginecc_tls_alarm_notify_group` | Provider-shape blocked | Empty group rejected; both GeneralWebhook `receivers` and `notice_rules.receiver_infos` groups created but provider returned inconsistent nested sets after apply |
| `volcenginecc_tls_alarm` | Dependency-blocked | Requires a stable alarm notification group ID |
| `volcenginecc_cloudmonitor_rule` | Verified | Disabled ECS CPU rule create/no-op/destroy succeeded after permission grant; see `volcenginecc-cloudmonitor.md` |

`tls_rule` was re-verified in `cn-beijing` with a minimal host-file collection rule. The first retry omitted `paths` and failed after project/topic/index creation:

```text
InvalidRequest: InvalidArgument: Invalid argument key Paths, value <nil>, please check argument.
TypeName: Volcengine::TLS::Rule
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T06:52:57+08:00
```

Adding `input_type = 0`, `log_type = "minimalist_log"`, and `paths = ["/var/log/messages"]` created rule ID `<resource-id>`. Setting `pause = 1` caused readback drift (`pause = 0 -> 1` on the next plan), so the verified example omits `pause`. With `pause` omitted, the follow-up plan returned `No changes`, and destroy removed the rule, index, topic, and project successfully. Final Terraform state was empty.

`tls_consumer_group` was verified in `cn-beijing` with a project, a topic configured with `allow_consume = true`, and:

```hcl
resource "volcenginecc_tls_consumer_group" "app" {
  project_id          = volcenginecc_tls_project.main.project_id
  topic_id_list       = [volcenginecc_tls_topic.app.topic_id]
  consumer_group_name = "cc-iac-tls-cg-group"
  heartbeat_ttl       = 10
  ordered_consume     = false
}
```

Creation returned ID `<resource-id>|cc-iac-tls-cg-group`. The topic read back `consume_topic = "out-<resource-id>"`, but the follow-up plan returned `No changes`. Destroy removed consumer group, topic, and project successfully, and final Terraform state was empty.

`tls_shipper` to TOS was retried in `cn-beijing` with a temporary TLS project/topic and TOS bucket. The first TOS bucket shape used `enable_version_status = "Disabled"` and failed provider validation because the accepted values are only `Enabled` and `Suspended`. A second shape used `Suspended`, passed validation, then failed create after the API had partially created the bucket:

```text
GeneralServiceException: InvalidBody: The bucket multi-version is not enabled.
TypeName: Volcengine::TOS::Bucket
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T07:11:30+08:00
```

The next create returned `AlreadyExists` for bucket `cc-iac-tls-shipper-05300712`, so the bucket was imported into the temporary state and updated to `enable_version_status = "Enabled"`. After that, a disabled TOS shipper created successfully:

```hcl
resource "volcenginecc_tls_shipper" "tos" {
  topic_id     = volcenginecc_tls_topic.app.topic_id
  shipper_name = "cc-iac-tls-shipper-tos"
  shipper_type = "tos"
  status       = false

  content_info = {
    format = "json"
    json_info = {
      enable = true
      escape = true
      keys   = ["__content__", "__source__", "__path__", "__time__"]
    }
  }

  tos_shipper_info = {
    bucket           = volcenginecc_tos_bucket.logs.name
    compress         = "none"
    interval         = 300
    max_size         = 5
    partition_format = "%Y/%m/%d/%H/%M"
    prefix           = "tls"
  }
}
```

Created shipper ID was `<resource-id>`, but the follow-up plan was not clean:

```text
~ status = true -> false
```

Do not add `tls_shipper` to the verified TLS example until a shape produces create, no-op plan, and destroy without suppressing meaningful drift. During cleanup, shipper/topic/project deleted successfully. The TOS bucket delete entered the known long Cloud Control waiter; `tosutil stat tos://cc-iac-tls-shipper-05300712 -e=tos-cn-beijing.volces.com -re=cn-beijing` returned 404, then the stale temporary state entry was removed. Final temporary Terraform state was empty.

`tls_schedule_sql_task` was verified in `cn-beijing` with source and destination topics, each with a TLS index, plus `status = 0` and a bounded process window. The first retry without indexes failed:

```text
GeneralServiceException: IndexNotExists: Index does not exist.
TypeName: Volcengine::TLS::ScheduleSqlTask
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T07:41:18+08:00
```

Adding indexes for both topics allowed create to succeed. Created task ID was `<resource-id>`; the follow-up plan returned `No changes`, and destroy removed the task, indexes, topics, and project successfully. Final Terraform state was empty.

`tls_alarm_notify_group` empty-group retry validated and planned, then failed during create:

```text
InvalidRequest: InvalidArgument: Invalid argument key NotifyType, value [], please check argument.
TypeName: Volcengine::TLS::AlarmNotifyGroup
Operation: CREATE
OperationStatus: FAILED
```

A second retry with `notify_type = ["Trigger", "Recovery"]` and a GeneralWebhook receiver created the notification group, but Terraform failed the apply because the provider could not correlate the planned `receivers` set with the actual returned set:

```text
Provider produced inconsistent result after apply
When applying changes to volcenginecc_tls_alarm_notify_group.webhook,
provider "registry.terraform.io/volcengine/volcenginecc" produced an unexpected new value:
.receivers: planned set element ... does not correlate with any element in actual.
```

A third retry used `notice_rules.receiver_infos` instead of top-level `notify_type`/`receivers` and also planned successfully. It created the notification group, but failed after apply with the same provider set correlation class:

```text
Provider produced inconsistent result after apply
When applying changes to volcenginecc_tls_alarm_notify_group.webhook_rule,
provider "registry.terraform.io/volcengine/volcenginecc" produced an unexpected new value:
.notice_rules: planned set element ... does not correlate with any element in actual.
```

The `notice_rules` retry used this minimal shape:

```hcl
resource "volcenginecc_tls_alarm_notify_group" "webhook_rule" {
  alarm_notify_group_name = "cc-iac-tls-notify"
  iam_project_name        = "default"

  notice_rules = [
    {
      rule_node = jsonencode({
        Type  = "Condition"
        Value = ["Severity", "in", "[\"notice\",\"warning\",\"critical\"]"]
      })
      has_next     = false
      has_end_node = true

      receiver_infos = [
        {
          receiver_type     = "User"
          receiver_names    = []
          receiver_channels = ["GeneralWebhook"]
          start_time        = "00:00:00"
          end_time          = "23:59:59"

          general_webhook_url    = "https://example.com/tls-alarm"
          general_webhook_method = "POST"
          general_webhook_headers = [
            {
              key   = "Content-Type"
              value = "application/json"
            }
          ]
          general_webhook_body = "{\"alarm\":\"cc-iac-tls\"}"
        }
      ]
    }
  ]
}
```

The partially created notification groups were present in state and were destroyed successfully with Terraform. Temporary TLS project, topic, index, and notification group resources were destroyed; final Terraform state was empty.

Current-account retry on 2026-05-30 in `<tmp-workdir>` used the smallest top-level `notify_type` + one GeneralWebhook `receivers` shape, without TLS project/topic dependencies. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. The service created notification group `<resource-id>`, but Terraform failed the apply with the same provider nested-set correlation bug:

```text
Provider produced inconsistent result after apply
When applying changes to volcenginecc_tls_alarm_notify_group.webhook,
provider "registry.terraform.io/volcengine/volcenginecc" produced an unexpected new value:
.receivers: planned set element ... does not correlate with any element in actual.
```

The created notification group was present in Terraform state and destroyed successfully; final Terraform state was empty. Because even the smallest receiver shape cannot complete apply cleanly, `volcenginecc_tls_alarm` remains dependency-blocked for generated examples.

Retried the same smallest top-level `notify_type` + one GeneralWebhook `receivers` shape again on 2026-05-30 at 14:20 with group name `cc-iac-tls-notify-retry`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded. The service created notification group `<resource-id>`, then Terraform failed with the same provider nested-set correlation bug:

```text
Provider produced inconsistent result after apply
When applying changes to volcenginecc_tls_alarm_notify_group.webhook,
provider "provider[\"registry.terraform.io/volcengine/volcenginecc\"]" produced an unexpected new value:
.receivers: planned set element ... does not correlate with any element in actual.
```

The created notification group was present in Terraform state as a tainted resource and was destroyed successfully; final Terraform state was empty.

Current-account notification group discovery on 2026-05-30 used the read-only `volcenginecc_tls_alarm_notify_groups` data source. It returned an empty ID set:

```text
data.volcenginecc_tls_alarm_notify_groups.all: Read complete after 1s [id="cn-beijing"]
alarm_notify_group_ids = toset([])
```

Do not add a verified `tls_alarm_notify_group` or `tls_alarm` example until a notification group can apply, re-plan to no-op, and destroy cleanly. If an existing notification group is imported for a real deployment, prove a no-op plan before referencing it from `volcenginecc_tls_alarm`.

`cloudmonitor_rule` minimal disabled ECS CPU rule validated and planned successfully in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, using `namespace = "VCM_ECS"`, `sub_namespace = "Instance"`, `enable_state = "disable"`, `CpuTotal`, and no contact group IDs. Create failed, and a 2026-05-30 retry failed with the same permission denial:

```text
AccessDenied: AccessDenied: User is not authorized to perform: cloudmonitor:CreateRule on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Latest retry evidence:

```text
EventTime: 2026-05-30T08:23:16+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: cloudmonitor:CreateRule on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Latest current-AK retry evidence:

```text
EventTime: 2026-05-30T10:38:58+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: cloudmonitor:CreateRule on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Current-account retry on 2026-05-30 in `<tmp-workdir>` used the same disabled ECS CPU rule shape with rule name `cc-iac-cm-ecs-cpu-current`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed before creating any resource:

```text
EventTime: 2026-05-30T12:20:27+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: cloudmonitor:CreateRule on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Retried the same disabled ECS CPU rule shape again on 2026-05-30 at 13:57 with rule name `cc-iac-cm-ecs-cpu-retry`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply still failed before creating any resource:

```text
EventTime: 2026-05-30T13:57:30+08:00
TaskID: task-<id>
AccessDenied: User is not authorized to perform: cloudmonitor:CreateRule on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

No CloudMonitor resources were created in those retries; Terraform state remained empty. The latest `ve cloudmonitor ListRules --body '{"PageNumber":1,"PageSize":10,"RuleName":"cc-iac-cm-ecs-cpu-current"}'` returned an empty `Data` list. The account has a default CloudMonitor contact group (`<resource-id>`) but it contains no contacts.

After `cloudmonitor:CreateRule` was granted, a 2026-05-30 retry in `<tmp-workdir>` verified `volcenginecc_cloudmonitor_rule`. The first post-permission create without a concrete notification route failed with:

```text
EventTime: 2026-05-30T15:10:31+08:00
TaskID: task-<id>
InvalidRequest: InvalidParam.Notification: 通知渠道和回调不能同时为空
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Binding the default contact group then failed because it had no members:

```text
EventTime: 2026-05-30T15:11:04+08:00
TaskID: task-<id>
InvalidRequest: ContactGroupMemberEmpty: 联系组 默认告警联系组 <resource-id> 的联系人为空，请选择非空联系组
TypeName: Volcengine::CloudMonitor::Rule
Operation: CREATE
OperationStatus: FAILED
```

Using Webhook notification moved validation to the metric period field. `period = "1m"` and `period = "60s"` both failed with `InvalidParam.Period`; `period = "60"` succeeded. The verified disabled ECS CPU rule created ID `<resource-id>`, follow-up `terraform plan -detailed-exitcode` returned `No changes`, `terraform destroy` removed the rule, final Terraform state was empty, and `ve cloudmonitor ListRules --body '{"PageNumber":1,"PageSize":10,"RuleName":"cc-iac-cm-ecs-cpu-retry2"}'` returned an empty `Data` list.

Retry shape:

```hcl
resource "volcenginecc_cloudmonitor_rule" "ecs_cpu" {
  rule_name        = "cc-iac-cm-ecs-cpu"
  description      = "volcenginecc CloudMonitor example disabled ECS CPU rule"
  rule_type        = "static"
  namespace        = "VCM_ECS"
  sub_namespace    = "Instance"
  level            = "warning"
  evaluation_count = 1
  enable_state     = "disable"
  regions          = ["cn-beijing"]
  project_name     = "default"

  original_dimensions = {
    key    = "ResourceID"
    values = ["*"]
  }

  multiple_conditions = false
  condition_operator  = "&&"

  conditions = [
    {
      metric_name         = "CpuTotal"
      statistics          = "avg"
      comparison_operator = ">"
      threshold           = "95"
      period              = "1m"
      metric_unit         = "Percent"
    }
  ]

  no_data = {
    enable           = false
    evaluation_count = 3
  }

  recovery_notify = {
    enable = false
  }

  silence_time    = 5
  alert_methods   = ["Email"]
  effect_start_at = "00:00"
  effect_end_at   = "23:59"
}
```

## VPC Extended Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vpc_prefix_list` | Verified | Prefix list create/no-op/destroy succeeded; see `volcenginecc-vpc-extras.md` |
| `volcenginecc_vpc_network_acl` | Verified | Subnet ACL create/no-op/destroy succeeded; see `volcenginecc-vpc-extras.md` |
| `volcenginecc_vpc_eni` | Verified | Standalone secondary ENI create/no-op/destroy succeeded; see `volcenginecc-vpc-extras.md` |
| `volcenginecc_vpc_ha_vip` | Verified | Unbound HAVIP create/no-op/destroy succeeded; see `volcenginecc-vpc-extras.md` |
| `volcenginecc_vpc_bandwidth_package` | Verified | Empty IPv4 BGP shared bandwidth package create/no-op/destroy succeeded; see `volcenginecc-vpc-extras.md` |
| `volcenginecc_vpc_ipv6_gateway` | Dependency-blocked | VPC creation with `enable_ipv_6 = true` failed before gateway create |
| `volcenginecc_vpc_ipv6_address_bandwidth` | Dependency-blocked | Requires a VPC/subnet/ENI IPv6 address; VPC IPv6 create is unsupported in current API path |
| `volcenginecc_vpc_flow_log` | Permission-blocked | `InvalidOperation.NoPermission` during create |
| `volcenginecc_vpc_traffic_mirror_filter` | Verified | Standalone filter create/no-op/destroy succeeded; see `volcenginecc-vpc-traffic-mirror-filter.md` |
| `volcenginecc_vpc_traffic_mirror_filter_rule` | Verified | Ingress TCP rule create/no-op/destroy succeeded; see `volcenginecc-vpc-traffic-mirror-filter.md` |
| `volcenginecc_vpc_traffic_mirror_target` | Verified | Private CLB target create/no-op/destroy succeeded; see `volcenginecc-vpc-traffic-mirror-target.md` |
| `volcenginecc_vpc_traffic_mirror_session` | Spec-blocked | Attached ECS ENI from `ecs.g4i.large` rejected because the instance spec does not support traffic mirror |

IPv6 retry in `cn-beijing`: a VPC with `enable_ipv_6 = true`, IPv6 subnet, IPv6 gateway, and IPv6-enabled ENI validated and planned successfully, but VPC create failed before any resource was created:

```text
EventTime: 2026-05-30T08:37:36+08:00
TaskID: task-<id>
InvalidRequest: InvalidParameter.EnableIpv6: The EnableIpv6 parameter is currently not supported.
TypeName: Volcengine::VPC::VPC
Operation: CREATE
OperationStatus: FAILED
```

No IPv6 resources were created; Terraform state remained empty. Retry `volcenginecc_vpc_ipv6_gateway` and `volcenginecc_vpc_ipv6_address_bandwidth` only after the Cloud Control VPC create path accepts `enable_ipv_6 = true`, or by importing an existing IPv6-enabled VPC/subnet/IPv6 address.

Flow log retry in `cn-beijing`: a VPC plus TLS project/topic target validated and planned successfully. TLS project/topic and the VPC created, then `volcenginecc_vpc_flow_log` failed:

```text
EventTime: 2026-05-30T08:41:37+08:00
TaskID: task-<id>
AccessDenied: InvalidOperation.NoPermission: The current service is not allowed to do this operation.
TypeName: Volcengine::VPC::FlowLog
Operation: CREATE
OperationStatus: FAILED
```

The TLS project, TLS topic, and VPC dependencies were destroyed and Terraform state was empty afterward. Retry after the account has permission to create VPC flow logs.

Traffic mirror filter retry in `cn-beijing`: standalone filter `<traffic-mirror-filter-id>` and ingress TCP filter rule `<traffic-mirror-rule-id>` created successfully, returned a clean no-op plan, then destroyed successfully with final Terraform state empty. See `volcenginecc-vpc-traffic-mirror-filter.md` for the verified example.

Full traffic mirror target/session retry in `cn-beijing`: filter, ingress TCP filter rule, VPC, subnet, route table, security group, and two standalone ENIs created successfully. Creating a mirror target from the standalone target ENI failed:

```text
EventTime: 2026-05-30T08:40:22+08:00
TaskID: task-<id>
InvalidRequest: InvalidEni.InstanceMismatch: The specified elastic network interface is not attached to the specified instance.
TypeName: Volcengine::VPC::TrafficMirrorTarget
Operation: CREATE
OperationStatus: FAILED
```

All created dependencies were destroyed and Terraform state was empty afterward. Retry the full target/session path with two ECS-attached ENIs, or a CLB instance as the target, instead of standalone ENIs.

Second full traffic mirror target/session retry in `cn-beijing`: a temporary ECS instance `i-<id>` with attached primary ENI `<eni-id>` and a private CLB `clb-<id>` were created successfully. A CLB mirror target `<traffic-mirror-target-id>`, filter `<traffic-mirror-filter-id>`, and rule `<traffic-mirror-rule-id>` also created successfully. A later standalone CLB mirror target example returned a clean no-op plan and is now verified in `volcenginecc-vpc-traffic-mirror-target.md`. Creating the mirror session then failed:

```text
EventTime: 2026-05-30T09:41:03+08:00
TaskID: task-<id>
InvalidRequest: InvalidInstanceSpecification.Malformed: The specified instance does not currently support traffic mirror.
TypeName: Volcengine::VPC::TrafficMirrorSession
Operation: CREATE
OperationStatus: FAILED
```

The mirror target/filter/rule, private CLB, ECS instance, keypair, security group, route table, subnet, and VPC were all destroyed successfully. Final Terraform state was empty in both temporary verification directories. Retry `volcenginecc_vpc_traffic_mirror_session` only after selecting an ECS instance family that explicitly supports traffic mirroring.

## VPN Remaining Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vpn_vpn_gateway` | Verified | IPsec and SSL gateway shapes both create/no-op/destroy; see `volcenginecc-vpn.md` and `volcenginecc-vpn-ssl.md` |
| `volcenginecc_vpn_customer_gateway` | Verified | Customer gateway create/no-op/destroy succeeded in the IPsec example |
| `volcenginecc_vpn_vpn_connection` | Verified | IPsec connection create/no-op/destroy succeeded with sensitive PSK variable |
| `volcenginecc_vpn_vpn_gateway_route` | Verified | Static VPN gateway route create/no-op/destroy succeeded |
| `volcenginecc_vpn_ssl_vpn_server` | Verified | SSL VPN server create/no-op/destroy succeeded; see `volcenginecc-vpn-ssl.md` |
| `volcenginecc_vpn_ssl_vpn_client_cert` | Sensitive-state blocked | Resource returns `client_key`, client certificate, CA certificate, and OpenVPN config into Terraform state |

SSL VPN server retry in `cn-beijing`: VPC, subnet, route table, SSL-enabled VPN gateway, and SSL VPN server created successfully. The first SSL server attempt failed because `client_ip_pool = "172.30.200.0/26"` overlapped `local_subnets = ["172.30.0.0/16"]`:

```text
EventTime: 2026-05-30T13:41:39+08:00
TaskID: task-<id>
InvalidRequest: InvalidSslVpnClientIpPool.Conflict: The specified ClientIpPool conflicts with that of local subnets.
TypeName: Volcengine::VPN::SslVpnServer
Operation: CREATE
OperationStatus: FAILED
```

Changing `client_ip_pool` to `10.250.0.0/26` fixed the shape. The successful run created VPN gateway `<vpn-gateway-id>` and SSL VPN server `<ssl-vpn-server-id>`; a follow-up plan returned `No changes`. Destroy removed the SSL server, gateway, route table, subnet, and VPC; final Terraform state was empty. `DescribeVpnGateways --VpnGatewayName cc-iac-vpn-ssl-current-gateway` and `DescribeVpcs --VpcName cc-iac-vpn-ssl-current-vpc` both returned `TotalCount: 0`.

Do not add `vpn_ssl_vpn_client_cert` to shared examples unless the user explicitly accepts that generated client private key material will be stored in Terraform state.

## TOS Extended Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_tos_bucket` | Verified | Bucket create/no-op/destroy succeeded; see `volcenginecc-tos.md` |
| `volcenginecc_tos_bucket_cors` | Verified | CORS create/no-op/destroy succeeded; see `volcenginecc-tos.md` |
| `volcenginecc_tos_bucket_encryption` | Verified | AES256 encryption create/no-op/destroy succeeded; see `volcenginecc-tos.md` |
| `volcenginecc_tos_bucket_inventory` | Assume-role blocked | Terraform-created IAM role/policy still failed `InvalidRole: assume role fail` |
| `volcenginecc_tos_bucket_notification` | Verified | veFaaS target notification create/no-op/destroy succeeded; see `volcenginecc-tos-notification.md` |
| `volcenginecc_tos_bucket_realtime_log` | External role blocked | `InvalidRole: Role must exist` using default-looking role name |

TOS extended retry in `cn-beijing`: bucket `cc-iac-tos-extra-05300844` created successfully, then all three extended resources failed:

```text
EventTime: 2026-05-30T08:46:43+08:00
TaskID: task-<id>
GeneralServiceException: InvalidRole: Role must exist.
TypeName: Volcengine::TOS::BucketInventory
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T08:46:43+08:00
TaskID: task-<id>
NotFound: NotificationRule not found
TypeName: Volcengine::TOS::BucketNotification
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T08:46:43+08:00
TaskID: task-<id>
GeneralServiceException: InvalidRole: Role must exist.
TypeName: Volcengine::TOS::BucketRealtimeLog
Operation: CREATE
OperationStatus: FAILED
```

The bucket was deleted; `tosutil stat tos://cc-iac-tos-extra-05300844 -e=tos-cn-beijing.volces.com -re=cn-beijing` returned 404. The Cloud Control delete waiter kept running after cloud-side deletion, so the temporary state entry was removed only after the 404 and Terraform refresh warning confirmed the resource was gone.

Retry inventory and realtime log only after creating the required IAM roles and granting TOS service access. Retry notification with a real Kafka, RocketMQ, or veFaaS destination; do not use `notification_rules = []` as a create-time baseline.

TOS bucket inventory was retried again in the current account with Terraform-created IAM role and policy prerequisites. The role trust policy allowed `Principal.Service = ["tos.volcengine.com"]` to call `sts:AssumeRole`, and the custom policy allowed `tos:Get*`, `tos:List*`, and `tos:PutObject` on the inventory bucket. IAM role `cc-iac-tos-role-current-role`, IAM policy `cc-iac-tos-role-current-policy|Custom`, and bucket `cc-iac-tos-inv-current` all created successfully, but inventory create still failed:

```text
EventTime: 2026-05-30T13:18:49+08:00
TaskID: task-<id>
GeneralServiceException: InvalidRole: assume role fail, please check role.
TypeName: Volcengine::TOS::BucketInventory
Operation: CREATE
OperationStatus: FAILED
```

Do not add a verified `tos_bucket_inventory` example until the exact service principal, role path/name requirement, or account-side trust requirement is confirmed. Cleanup note: after the failure, IAM policy and role destroyed cleanly. The TOS bucket was cloud-side deleted (`tosutil stat` returned 404), but Cloud Control kept waiting on delete, so the stale bucket state entry was removed only after confirming the 404. Final temporary Terraform state was empty.

TOS bucket notification was later verified with a released veFaaS function destination. The first attempt with only `volcenginecc_vefaas_function` failed because TOS requires the function to be fully released:

```text
EventTime: 2026-05-30T12:44:12+08:00
TaskID: task-<id>
InvalidRequest: InvalidArgument: faas function has not been fully released yet, please release it first
TypeName: Volcengine::TOS::BucketNotification
Operation: CREATE
OperationStatus: FAILED
```

Adding `volcenginecc_vefaas_release` and an explicit `depends_on` from the notification to the release fixed the dependency. Bucket `cc-iac-tos-noti-current`, function `4cjgrs2l`, release record `ybfg6a9met7gd111`, and notification `cc-iac-tos-noti-current` created successfully, and a follow-up plan returned `No changes`. See [`volcenginecc-tos-notification.md`](./volcenginecc-tos-notification.md) for cleanup caveats: TOS bucket deletion can leave a stuck Cloud Control waiter after TOS returns 404, and finished veFaaS release records may need `terraform state rm`.

## EBS Extended Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_storageebs_volume` | Verified | Standalone data disk create/no-op/destroy succeeded; see `volcenginecc-ecs.md` and `volcenginecc-ebs-snapshot.md` |
| `volcenginecc_storageebs_snapshot` | Verified | Manual snapshot create/no-op/destroy succeeded; see `volcenginecc-ebs-snapshot.md` |
| `volcenginecc_storageebs_snapshot_group` | Lifecycle verified with parent drift | Snapshot group create/destroy succeeded from an ECS system volume; fresh no-op drift came from parent ECS/security-group Optional+Computed fields, not the snapshot group |

Manual snapshot verification in `cn-beijing`: a 10 GiB `ESSD_PL0` postpaid data disk in `cn-beijing-a` created successfully, snapshot `<snapshot-id>` created in about 2m6s, a follow-up plan returned `No changes`, and destroy removed the snapshot and disk. Final Terraform state was empty.

Snapshot group retry in `cn-beijing`: an ECS-backed system volume path validated, planned, applied, and destroyed successfully. First create failed only because `description` was set on the snapshot group:

```text
EventTime: 2026-05-30T10:00:58+08:00
TaskID: task-<id>
InvalidRequest: InvalidParameter.Description: The specified description is invalid.
TypeName: Volcengine::StorageEBS::SnapshotGroup
Operation: CREATE
OperationStatus: FAILED
```

After omitting `description`, snapshot group `sg-<id>` created from ECS instance `i-<id>` and system volume `vol-<id>`, returned a clean follow-up plan, and destroyed successfully. A fresh run from empty state also created snapshot group `sg-<id>` from ECS instance `i-<id>` and system volume `vol-<id>`; the snapshot group itself had no drift, but the follow-up plan showed parent `volcenginecc_ecs_instance` and `volcenginecc_vpc_security_group` Optional+Computed pseudo-diffs. Destroy removed all seven resources and final Terraform state was empty.

Use [`volcenginecc-ebs-snapshot-group.md`](./volcenginecc-ebs-snapshot-group.md) for the verified lifecycle example. Do not use standalone unattached disks for snapshot groups.

## Auto Scaling

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_autoscaling_scaling_group` | Lifecycle verified with drift/destroy caveat | Create/destroy succeeded only with a launch template; follow-up plan showed provider readback pseudo-diffs |
| `volcenginecc_autoscaling_scaling_configuration` | Lifecycle verified with destroy caveat | Create succeeded and was cascaded by scaling group deletion; direct Terraform destroy can fail while it is the active configuration |
| `volcenginecc_autoscaling_scaling_lifecycle_hook` | Lifecycle verified | Scale-out hook create/delete succeeded |
| `volcenginecc_autoscaling_scaling_policy` | Verified (scheduled) | Scheduled policy creates and reaches clean self no-op with a near-future `launch_time` and `is_enabled_policy = false`; now part of the example |

Auto Scaling retry in `cn-beijing`: VPC, subnet, route table, security group, keypair, ECS launch template, scaling group, scaling configuration, and lifecycle hook validated, planned, applied, and destroyed. A successful run created launch template `lt-<id>`, scaling group `scg-<id>`, scaling configuration `scc-<id>`, and lifecycle hook `sgh-<id>`; destroy removed all nine resources and final Terraform state was empty.

Creating the scaling group without `launch_template_id` failed even though generated docs mark it optional:

```text
EventTime: 2026-05-30T10:14:57+08:00
TaskID: task-<id>
MissingParameter.LaunchTemplateId
TypeName: Volcengine::AutoScaling::ScalingGroup
Operation: CREATE
OperationStatus: FAILED
```

Creating the required launch template without `launch_template_version.volumes` failed:

```text
EventTime: 2026-05-30T10:15:37+08:00
TaskID: task-<id>
MissingParameter.LaunchTemplateVolumes
TypeName: Volcengine::ECS::LaunchTemplate
Operation: CREATE
OperationStatus: FAILED
```

Scheduled scaling policies first failed for far-future launch times such as `2030-01-01T00:00Z`, `2030-01-01T00:00+08:00`, and `2030-01-01T00:00:00Z`. The root cause was the launch time being too far out, not the format: a near-future UTC `launch_time` (for example a few days ahead, `YYYY-MM-DDTHH:MMZ`) with `is_enabled_policy = false` creates successfully. The earlier far-future attempts returned:

```text
EventTime: 2026-05-30T10:23:55+08:00
TaskID: task-<id>
InvalidRequest: InvalidScheduledPolicyLaunchTime.Malformed: The specified ScheduledPolicy LaunchTime is malformed.
TypeName: Volcengine::AutoScaling::ScalingPolicy
Operation: CREATE
OperationStatus: FAILED
```

One cleanup run exposed Terraform destroy ordering drift: deleting the active scaling configuration before the scaling group failed with `InvalidScalingConfiguration.InUse`. Recovery removed the configuration from state, destroyed the scaling group first, confirmed both group and configuration were gone with `ve autoscaling DescribeScalingGroups --ScalingGroupIds.1 scg-<id>` and `ve autoscaling DescribeScalingConfigurations --ScalingConfigurationIds.1 scc-<id>`, then destroyed the remaining launch template/network dependencies. Final Terraform state was empty.

Use [`volcenginecc-autoscaling.md`](./volcenginecc-autoscaling.md) for the verified lifecycle example, which now includes a scheduled `autoscaling_scaling_policy`. Alarm and recurrence policy shapes are not yet verified.

## CBR

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_cbr_vault` | Verified | Backup vault create/no-op/destroy succeeded after permission grant (2026-06-17); see `volcenginecc-cbr.md` |
| `volcenginecc_cbr_backup_policy` | Verified | Disabled incremental policy create/no-op/destroy succeeded (2026-06-17); see `volcenginecc-cbr.md` |
| `volcenginecc_cbr_backup_resource` | Dependency-blocked | Requires permission plus a real ECS or vePFS backup source |
| `volcenginecc_cbr_backup_plan` | Dependency-blocked | Requires a backup policy and backup resource |

Current-account retry on 2026-05-30 in `<tmp-workdir>` used a minimal independent shape: one backup vault and one disabled full backup policy. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before any resource IDs were created:

```text
EventTime: 2026-05-30T13:26:06+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: cbr:CreateVault on resource: trn:iam::<account-id>:project/default
TypeName: Volcengine::CBR::Vault
Operation: CREATE
OperationStatus: FAILED
```

```text
EventTime: 2026-05-30T13:26:06+08:00
TaskID: task-<id>
AccessDenied: AccessDenied: User is not authorized to perform: cbr:CreateBackupPolicy on resource:
TypeName: Volcengine::CBR::BackupPolicy
Operation: CREATE
OperationStatus: FAILED
```

After `cbr:CreateVault` and `cbr:CreateBackupPolicy` were granted, the minimal vault plus disabled policy was verified (create, clean no-op, destroy, empty state) on 2026-06-17 and now lives in `assets/examples/volcenginecc-cbr` with notes in `volcenginecc-cbr.md`. The provider docs have a resource naming pitfall: the backup policy example uses `volcenginecc_cbr_backuppolicy`, but the registered Terraform resource type is `volcenginecc_cbr_backup_policy`. `cbr_backup_resource` and `cbr_backup_plan` remain dependency-blocked until a disposable ECS or vePFS backup source is chosen.

## VMP

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_vmp_workspace` | Service-disabled blocked | `ProductUnsubscribed: You are not subscribed to VMP` during create |
| `volcenginecc_vmp_alerting_rule` | Dependency-blocked | Requires a working VMP workspace; notification policies are optional only after create is proven |

Current-account retry on 2026-05-30 in `<tmp-workdir>` used a minimal workspace without custom credentials: `auth_type = "None"`, `public_access_enabled = false`, `delete_protection_enabled = false`, and `instance_type_id = "vmp.standard.15d"`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded. Apply failed before a workspace ID was created:

```text
EventTime: 2026-05-30T13:27:55+08:00
TaskID: task-<id>
ServiceNotEnabled: ProductUnsubscribed: You are not subscribed to VMP. Please go to the VMP console web page to subscribe to the service.
TypeName: Volcengine::VMP::Workspace
Operation: CREATE
OperationStatus: FAILED
```

No VMP resources were created; Terraform state remained empty. Do not add a verified `volcenginecc-vmp` example until the VMP service is subscribed. After subscription, retry the private workspace first; only add `vmp_alerting_rule` after the workspace reaches no-op, using `status = "Disabled"` and no notification policy IDs to test whether rules can be staged before notification routing exists.

## DNS, PrivateZone, CDN, and WAF Remaining Resources

Attempted resources:

| Resource | Status | Evidence |
|---|---|---|
| `volcenginecc_dns_zone` | Verified | Public zone create/no-op/destroy succeeded; see `volcenginecc-dns.md` |
| `volcenginecc_privatezone_private_zone` | Verified | Private zone create/no-op/destroy succeeded; see `volcenginecc-privatezone.md` |
| `volcenginecc_privatezone_record` | Verified | Private A record create/no-op/destroy succeeded; see `volcenginecc-privatezone.md` |
| `volcenginecc_privatezone_resolver_endpoint` | Verified | Outbound two-AZ endpoint create/no-op/destroy succeeded after creating the `private_zone` service-linked role (2026-06-17); see `volcenginecc-privatezone-resolver.md` |
| `volcenginecc_privatezone_resolver_rule` | Verified | Outbound forwarding rule create/no-op/destroy succeeded on the verified endpoint; see `volcenginecc-privatezone-resolver.md` |
| `volcenginecc_privatezone_user_vpc_authorization` | External dependency blocked | Self-account validation rejected; requires a real target account/verification flow |
| `volcenginecc_cdn_domain` | Service-disabled blocked | `ServiceNotEnabled: OperationDenied.ServiceStopped` during create |
| `volcenginecc_cdn_share_config` | Service-disabled blocked | Minimal shared referer config planned, but CDN service is stopped for the account |
| `volcenginecc_waf_domain` | Domain dependency blocked | Unregistered test domain failed DNICP validation |

As of 2026-06-17, creating the service-linked role with `ve iam CreateServiceLinkedRole --ServiceName private_zone` resolved the trust error, and the outbound resolver endpoint plus forwarding rule were verified (create, clean no-op, destroy, empty state); they now live in `assets/examples/volcenginecc-privatezone-resolver`. The historical failure is kept below.

PrivateZone resolver endpoint validated and planned successfully with a two-AZ VPC/subnet shape, then failed during create:

```text
InvalidRequest: ErrServiceNotTrusted: ServiceLinkedRole of private_zone is not trusted
TypeName: Volcengine::PrivateZone::ResolverEndpoint
Operation: CREATE
OperationStatus: FAILED
```

Latest retry evidence:

```text
EventTime: 2026-05-30T08:28:34+08:00
TaskID: task-<id>
InvalidRequest: ErrServiceNotTrusted: ServiceLinkedRole of private_zone is not trusted
TypeName: Volcengine::PrivateZone::ResolverEndpoint
Operation: CREATE
OperationStatus: FAILED
```

Retried the same two-AZ VPC/subnet shape again on 2026-05-30 at 14:14, with `volcenginecc_privatezone_resolver_rule` in the same plan depending on the endpoint. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded. Apply created temporary VPC `vpc-<id>`, subnets `subnet-<id>` and `subnet-<id>`, and route table `vtb-<id>`; endpoint creation still failed before the resolver rule dependency could run:

```text
EventTime: 2026-05-30T14:14:22+08:00
TaskID: task-<id>
InvalidRequest: ErrServiceNotTrusted: ServiceLinkedRole of private_zone is not trusted
TypeName: Volcengine::PrivateZone::ResolverEndpoint
Operation: CREATE
OperationStatus: FAILED
```

The failed retries created only temporary VPC/subnet/route-table dependencies. Recovery destroyed all temporary network resources; final Terraform state was empty, and exact VPC-name matching for `cc-iac-pzone-resolver-retry-vpc` returned no rows.

Because the resolver endpoint never created, `volcenginecc_privatezone_resolver_rule` was not applied. When the PrivateZone service-linked role is trusted, retry with this shape:

```hcl
resource "volcenginecc_privatezone_resolver_endpoint" "outbound" {
  name          = "cc-iac-pzone-endpoint"
  vpc_id        = volcenginecc_vpc_vpc.main.vpc_id
  vpc_region    = "cn-beijing"
  direction     = "OUTBOUND"
  endpoint_type = "IPv4"
  project_name  = "default"

  ip_configs = [
    {
      az_id     = "cn-beijing-a"
      subnet_id = volcenginecc_vpc_subnet.primary.subnet_id
    },
    {
      az_id     = "cn-beijing-b"
      subnet_id = volcenginecc_vpc_subnet.secondary.subnet_id
    }
  ]
}

resource "volcenginecc_privatezone_resolver_rule" "outbound" {
  name        = "cc-iac-pzone-rule"
  type        = "OUTBOUND"
  endpoint_id = tonumber(volcenginecc_privatezone_resolver_endpoint.outbound.endpoint_id)
  zone_name   = "corp.internal"

  forward_i_ps = [
    {
      ip   = "100.96.0.10"
      port = 53
    }
  ]

  vp_cs = [
    {
      region = "cn-beijing"
      vpc_id = volcenginecc_vpc_vpc.main.vpc_id
    }
  ]
}
```

`volcenginecc_privatezone_user_vpc_authorization` validated and planned with the current account ID and `auth_type = 0`, then failed as expected:

```text
InvalidRequest: ErrAccountSelfValidationNotAllowed: account self-validation not allowed
TypeName: Volcengine::PrivateZone::UserVPCAuthorization
Operation: CREATE
OperationStatus: FAILED
```

Retried the same current-account `auth_type = 0` shape on 2026-05-30 at 14:17. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply still failed at the self-account validation boundary before creating any authorization:

```text
EventTime: 2026-05-30T14:17:17+08:00
TaskID: task-<id>
InvalidRequest: ErrAccountSelfValidationNotAllowed: account self-validation not allowed
TypeName: Volcengine::PrivateZone::UserVPCAuthorization
Identifier: <account-id>
Operation: CREATE
OperationStatus: FAILED
```

Terraform state remained empty.

Do not add this as a generic verified example. It needs either an enterprise-organization target account (`auth_type = 0`) or an out-of-band verification code (`auth_type = 1`) for a real cross-account VPC authorization.

`volcenginecc_cdn_domain` minimal IP-origin configuration validated and planned successfully, then create failed because CDN is stopped for the account:

```text
ServiceNotEnabled: OperationDenied.ServiceStopped: 服务处于停用状态，不支持该操作。
TypeName: Volcengine::CDN::Domain
Operation: CREATE
OperationStatus: FAILED
```

Current-account retry on 2026-05-30 used the same minimal IP-origin shape in `<tmp-workdir>`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed before creating a CDN domain:

```text
EventTime: 2026-05-30T12:27:35+08:00
TaskID: task-<id>
ServiceNotEnabled: OperationDenied.ServiceStopped: 服务处于停用状态，不支持该操作。
TypeName: Volcengine::CDN::Domain
Operation: CREATE
OperationStatus: FAILED
```

Retried the same minimal IP-origin shape again on 2026-05-30 at 14:09 with domain `cdn.example.com`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply still failed at the CDN service-state boundary:

```text
EventTime: 2026-05-30T14:09:21+08:00
TaskID: task-<id>
ServiceNotEnabled: OperationDenied.ServiceStopped: 服务处于停用状态，不支持该操作。
TypeName: Volcengine::CDN::Domain
Identifier: cdn.example.com
Operation: CREATE
OperationStatus: FAILED
```

Terraform state remained empty. A cloud-side `ve cdn DescribeCdnConfig` check for `cdn.example.com` was also blocked by `OperationDenied.ServiceStopped`, so CDN must be enabled before any domain residue can be queried directly.

`volcenginecc_cdn_share_config` minimal shared referer allowlist configuration also validated and planned successfully, then failed with the same service-stopped status:

```text
ServiceNotEnabled: OperationDenied.ServiceStopped: 服务处于停用状态，不支持该操作。
TypeName: Volcengine::CDN::ShareConfig
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T07:07:48+08:00
```

Current-account retry on 2026-05-30 used the same minimal shared referer allowlist shape in `<tmp-workdir>`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed before creating a shared config:

```text
EventTime: 2026-05-30T12:27:35+08:00
TaskID: task-<id>
ServiceNotEnabled: OperationDenied.ServiceStopped: 服务处于停用状态，不支持该操作。
TypeName: Volcengine::CDN::ShareConfig
Operation: CREATE
OperationStatus: FAILED
```

No CDN shared config resources were created; Terraform state remained empty. Retry both CDN resources only after CDN is enabled for the account.

Retry shape after CDN is enabled:

```hcl
resource "volcenginecc_cdn_domain" "main" {
  domain         = "cdn.example.com"
  service_type   = "web"
  service_region = "outside_chinese_mainland"
  project        = "default"

  origin = [
    {
      origin_action = {
        origin_lines = [
          {
            address               = "1.1.1.1"
            http_port             = "80"
            https_port            = "443"
            instance_type         = "ip"
            origin_host           = "cdn.example.com"
            origin_type           = "primary"
            private_bucket_access = false
            weight                = "1"
          }
        ]
      }
    }
  ]
}
```

`volcenginecc_waf_domain` minimal CNAME HTTP configuration validated and planned successfully, then create failed because the throwaway domain was not registered with DNICP:

```text
InvalidRequest: InvalidParameter: Domain(cc-iac-waf-0530043107.com) The domain name is not registered with DNICP
TypeName: Volcengine::WAF::Domain
Operation: CREATE
OperationStatus: FAILED
```

Current-account retry on 2026-05-30 used the same CNAME HTTP shape in `<tmp-workdir>`, with a public IP origin and `protocols = ["HTTP"]`. `terraform fmt`, `init -backend=false`, `validate`, and `plan` succeeded; apply failed before creating a WAF domain because the test domain was not registered with DNICP:

```text
EventTime: 2026-05-30T12:28:51+08:00
TaskID: task-<id>
InvalidRequest: InvalidParameter: Domain(cc-iac-waf-current.example.com) The domain name is not registered with DNICP
TypeName: Volcengine::WAF::Domain
Operation: CREATE
OperationStatus: FAILED
```

Retried the same CNAME HTTP shape again on 2026-05-30 at 14:10 with domain `cc-iac-waf-retry.example.com`. `terraform fmt -check`, `init -backend=false`, `validate`, and `plan` succeeded; apply was still rejected by DNICP registration validation before creating a WAF domain:

```text
EventTime: 2026-05-30T14:10:59+08:00
TaskID: task-<id>
InvalidRequest: InvalidParameter: Domain(cc-iac-waf-retry.example.com) The domain name is not registered with DNICP
TypeName: Volcengine::WAF::Domain
Identifier: cc-iac-waf-retry.example.com
Operation: CREATE
OperationStatus: FAILED
```

Terraform state remained empty. A generic WAF example cannot be cleanly verified with a throwaway domain; use a real registered domain and an origin that can safely receive WAF probes.

Retry with a real registered domain and reachable origin:

```hcl
resource "volcenginecc_waf_domain" "main" {
  access_mode        = 10
  domain             = "www.example.com"
  lb_algorithm       = "wrr"
  public_real_server = 1
  project_name       = "default"
  vpc_id             = ""
  protocols          = ["HTTP"]

  protocol_ports = {
    http = [80]
  }

  backend_groups = [
    {
      access_port = [80]
      name        = "default"
      backends = [
        {
          protocol = "HTTP"
          port     = 80
          ip       = "1.1.1.1"
          weight   = 50
        }
      ]
    }
  ]
}
```
