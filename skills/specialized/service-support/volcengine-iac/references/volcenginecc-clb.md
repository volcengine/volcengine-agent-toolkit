# Volcenginecc CLB Example

Verified example path:

```text
assets/examples/volcenginecc-clb/main.tf
assets/examples/volcenginecc-clb-certificate/main.tf
assets/examples/volcenginecc-clb-acl/main.tf
```

Use these examples when a Volcengine deployment needs a Terraform-managed Classic Load Balancer instance, an uploaded CLB server certificate for HTTPS listeners, or a standalone CLB access-control policy group. The CLB instance example creates a private CLB to avoid allocating public EIP during validation.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_clb_clb` | Classic Load Balancer instance for TCP/UDP/HTTP/HTTPS entry traffic |
| `volcenginecc_clb_certificate` | Uploaded CLB server certificate for HTTPS listener `certificate_source = "clb"` |
| `volcenginecc_clb_acl` | Listener-level access-control policy group, verified independently of listener binding |

The example includes a minimal VPC, subnet, and route table so it can be validated independently. In real deployments, wire CLB to the verified network foundation instead of creating a separate VPC.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-clb
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform destroy
```

Observed apply result: VPC, subnet, route table, private CLB instance, and standalone CLB ACL created successfully. Destroy removed all resources and final state was empty.

The CLB certificate example requires certificate material through environment variables:

```bash
cd assets/examples/volcenginecc-clb-certificate
export TF_VAR_certificate_public_key="$(<server.crt)"
export TF_VAR_certificate_private_key="$(<server-rsa.key)"
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: CLB server certificate created successfully with ID `cert-<certificate-id>`, a follow-up plan was clean no-op, destroy removed the certificate, and final Terraform state was empty.

Observed timings in `cn-beijing`: CLB instance creation took about 11s; CLB instance deletion took about 6s; CLB certificate creation took about 6s and deletion took about 6s; CLB ACL creation took about 21s and deletion about 15s.

## Pitfalls found during verification

1. The generated `clb_clb` docs include `region_id`, but provider `0.0.46` rejects it with `Unsupported argument`. Do not include `region_id`; the provider uses `VOLCENGINE_REGION`.

2. Private CLB works with `load_balancer_billing_type = 2`, `load_balancer_spec = "small_1"`, `address_ip_version = "ipv4"`, and no `eip` block.

3. `master_zone_id` and `slave_zone_id` must be different zones in the selected region. The verified pair was `cn-beijing-a` and `cn-beijing-b`.

4. `bypass_security_group_enabled` is a string enum (`"on"` / `"off"`), not a boolean.

5. `volcenginecc_clb_acl` is verified only as a standalone access-control policy group. Listener attachment still depends on a verified CLB listener path.

6. `volcenginecc_clb_certificate` requires a PEM certificate plus a traditional RSA private key (`-----BEGIN RSA PRIVATE KEY-----`). OpenSSL's default PKCS#8 private key (`-----BEGIN PRIVATE KEY-----`) failed with `InvalidPrivateKey.Malformed`.

7. Do not commit certificate material or Terraform state from certificate examples. Even with `sensitive = true`, `public_key` and `private_key` are stored in Terraform state.

8. `volcenginecc_clb_server_group` was blocked by account permissions during verification: Cloud Control returned `AccessDenied: Forbidden: You are not authorized to perform operations on the specified service.` Until permissions are fixed, do not present `clb_server_group`, `clb_listener`, or `clb_rule` as fully verified.

9. `volcenginecc_clb_nlb`, `volcenginecc_clb_nlb_server_group`, and `volcenginecc_clb_nlb_listener` can create and destroy as a private NLB chain, but the server group follow-up plan did not converge because Optional+Computed defaults (`connection_drain_timeout`, `health_check`, `servers`) kept planning in-place updates. Keep NLB out of verified examples until a clean no-op plan is proven.

10. If you switch the example to public CLB, add an `eip` block and verify billing/cleanup explicitly. Do not infer public behavior from the private CLB run.

## Import IDs

```bash
terraform import volcenginecc_clb_clb.main <load-balancer-id>
terraform import volcenginecc_clb_certificate.server <certificate-id>
terraform import volcenginecc_clb_acl.main <acl-id>
```
