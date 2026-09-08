# Volcenginecc ALB Notes

Verified example paths:

```text
assets/examples/volcenginecc-alb/main.tf
assets/examples/volcenginecc-alb-health-check/main.tf
assets/examples/volcenginecc-alb-certificate/main.tf
assets/examples/volcenginecc-alb-acl/main.tf
assets/examples/volcenginecc-alb-customized-cfg/main.tf
```

Use these examples when a Volcengine deployment needs a private Basic ALB entry point with an HTTP listener and forwarding rule, a reusable ALB health check template, an uploaded ALB server certificate for HTTPS listeners, a standalone ALB access-control policy group, or a reusable ALB customized NGINX config.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_alb_load_balancer` | Private Basic Application Load Balancer for HTTP entry traffic |
| `volcenginecc_alb_server_group` | Empty IP-type HTTP server group ready for backend registration |
| `volcenginecc_alb_listener` | Disabled baseline HTTP listener on port 8080 |
| `volcenginecc_alb_rule` | Host/path forwarding rule to the server group |
| `volcenginecc_alb_health_check_template` | Reusable HTTP/TCP health check template for ALB server groups |
| `volcenginecc_alb_certificate` | Uploaded ALB server certificate for HTTPS listener `certificate_source = "alb"` |
| `volcenginecc_alb_acl` | Listener-level access-control policy group, verified independently of listener binding |
| `volcenginecc_alb_customized_cfg` | Reusable listener-level NGINX config policy, verified independently of listener binding |

## Verified command sequence

The full private ALB, health check template, and server certificate examples were verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-alb
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
```

```bash
cd assets/examples/volcenginecc-alb-health-check
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

```bash
cd assets/examples/volcenginecc-alb-certificate
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_certificate_public_key="$(<server.crt)"
export TF_VAR_certificate_private_key="$(<server.key)"
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy
```

Observed apply result: private Basic ALB, empty IP-type HTTP server group, disabled HTTP listener, host/path forwarding rule, ALB health check template, ALB server certificate, standalone ALB ACL, and standalone ALB customized config created successfully. Destroy removed all resources and final state was empty.

Observed timings in `cn-beijing`: full private ALB chain creation took about 1.5 minutes after VPC dependencies existed and deletion took about 1.5 minutes; health check template creation took about 7s and deletion took about 10s; ALB server certificate creation and deletion each took about 6s; ALB ACL creation took about 21s and deletion about 15s; ALB customized config creation took about 15s and deletion about 6s.

Formal full-chain verification for `assets/examples/volcenginecc-alb` created VPC `vpc-<id>`, server group `rsp-<id>`, ALB `alb-<id>`, listener `lsn-<id>`, and rule `rule-<id>`. `terraform plan -detailed-exitcode` returned `No changes`.

## Pitfalls found during verification

1. The generated docs say `health_check_method` options are `GETHEAD`, but the API accepted `GET` in the verified run.

2. `health_check_port = 0` means use the backend server port. This is safe for reusable templates and avoids hardcoding a backend-specific health port.

3. `health_check_domain` is optional. If you set it, it must contain at least one dot and cannot start or end with a dot. The verified value was `example.com`.

4. `volcenginecc_alb_certificate` with `certificate_type = "Server"` is verified with a PEM certificate plus a traditional RSA private key (`-----BEGIN RSA PRIVATE KEY-----`). The default OpenSSL PKCS#8 private key (`-----BEGIN PRIVATE KEY-----`) failed with `InvalidPrivateKey.Malformed`.

5. Do not commit certificate material or Terraform state from certificate examples. Even with `sensitive = true`, `public_key` and `private_key` are stored in Terraform state.

6. `volcenginecc_alb_certificate` with `certificate_type = "CA"` and a self-signed CA certificate failed with `InvalidCACertificate.Malformed`; only the `Server` certificate path is verified.

7. `volcenginecc_alb_acl` is verified as a standalone access-control policy group. Bind it to listeners only when you intentionally enable `acl_status = "on"` and set `acl_type`; the baseline listener keeps ACL disabled.

8. `volcenginecc_alb_customized_cfg` is verified as a standalone reusable config policy. Listener association should be added only when the deployment needs custom NGINX behavior. Keep config content short and use `\r\n` line separators; the verified content had a clean no-op plan.

9. `volcenginecc_alb_load_balancer` needs at least two zone mappings for the verified private Basic shape. Create and associate route tables before the load balancer; otherwise ALB can create service ENIs while VPC dependencies are still settling.

10. `volcenginecc_alb_server_group.health_check.port` is required by provider validation even when `enabled = "off"`; use `port = 0` to mean backend-server port.

11. For a clean no-op plan with disabled health checks, align to API defaults: `method = "HEAD"`, `http_version = "HTTP1.0"`, and `http_code = "http_2xx,http_3xx"`. Setting `GET`, `HTTP1.1`, or only `http_2xx` creates a follow-up diff.

12. Do not set `cross_zone_enabled` in the baseline server group. It read back as provider/API default and a previously explicit `cross_zone_enabled = "on"` created a follow-up diff.

13. The generated ALB examples use public DualStack, bandwidth packages, WAF, QUIC, certificate center, and PCA dependencies. Strip these unless the deployment explicitly needs them and all dependency IDs are known.

14. A disabled HTTP listener with `acl_status = "off"` and no tags had a clean no-op plan. HTTPS listeners require separately verified certificate inputs.

15. `volcenginecc_alb_rule.rule_action = ""` is the baseline forward action for Basic ALB host/path rules; pair it with `server_group_id` and keep `traffic_limit_enabled = "off"` unless QPS limiting is required.

16. ALB/VPC teardown can have a short consistency window after service ENIs are released. One formal verification destroy hit `InvalidOperation.Conflict` deleting a route table; checking `DescribeNetworkInterfaces` showed no ENIs, and rerunning `terraform destroy` removed the remaining route table, subnet, and VPC.

Cloud-side cleanup evidence from the formal full-chain verification: final Terraform state was empty, `ve alb DescribeLoadBalancers --body '{"LoadBalancerName":"cc-iac-alb-alb"}'` returned `TotalCount: 0`, `ve alb DescribeServerGroups --body '{"ServerGroupName":"cc-iac-alb-sg"}'` returned `TotalCount: 0`, exact VPC-name matching for `cc-iac-alb-vpc` returned `TotalCount: 0`, and checking ENIs by the deleted VPC ID returned `InvalidVpc.NotFound`.

## Import IDs

```bash
terraform import volcenginecc_alb_health_check_template.http <health-check-template-id>
terraform import volcenginecc_alb_load_balancer.main <load-balancer-id>
terraform import volcenginecc_alb_server_group.app <server-group-id>
terraform import volcenginecc_alb_listener.http <listener-id>
terraform import volcenginecc_alb_rule.app <listener-id>|<rule-id>
terraform import volcenginecc_alb_certificate.server <certificate-id>|Server
terraform import volcenginecc_alb_acl.main <acl-id>
terraform import volcenginecc_alb_customized_cfg.main <customized-cfg-id>
```
