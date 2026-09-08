# Volcenginecc CR Example

Verified example path:

```text
assets/examples/volcenginecc-cr/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed Container Registry instance, namespace, repository, and public endpoint allowlist for image push/pull workflows.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_cr_registry` | Container Registry instance for images, Helm charts, and OCI artifacts |
| `volcenginecc_cr_name_space` | Repository namespace inside a registry |
| `volcenginecc_cr_repository` | Image repository under a namespace |
| `volcenginecc_cr_endpoint_acl_policy` | Public endpoint IP allowlist entry |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-cr
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

Observed apply result: registry, namespace, repository, and endpoint ACL policy created successfully. A follow-up plan returned `No changes`. Destroy removed all 4 resources and final state was empty.

Observed timings in `cn-beijing`: `volcenginecc_cr_registry` creation took about 2m16s and deletion took about 2m6s. Namespace, repository, and ACL operations completed within seconds after the registry was ready.

## Pitfalls found during verification

1. Registry names must be globally suitable for CR constraints: lowercase letters, numbers, and hyphens only; cannot start with a number or hyphen; cannot end with a hyphen; length 3-30. Use a short project prefix and avoid underscores.

2. `volcenginecc_cr_registry.type = "Enterprise"` creates a standard edition instance according to the generated docs. The name is misleading, but this value applied successfully.

3. Enable the public endpoint on the registry before managing `volcenginecc_cr_endpoint_acl_policy`. The example sets `endpoint = { enabled = true }` and creates the ACL after the registry exists.

4. `volcenginecc_cr_endpoint_acl_policy` import ID is `registry|entry`. Terraform state used `cciaccr0530|0.0.0.0/0` during verification.

5. `volcenginecc_cr_name_space` import ID is `registry|namespace`; `volcenginecc_cr_repository` import ID is `registry|namespace|repository`.

6. The provider docs show SetNestedAttribute warnings for tags. Fully specify both `key` and `value`; partial tag objects can cause unstable diffs.

7. Generated registry docs list `status` as Optional even though it is platform-managed. Do not set `status` in examples; let the provider read it after creation.

## Import IDs

```bash
terraform import volcenginecc_cr_registry.main <registry-name>
terraform import volcenginecc_cr_name_space.app <registry-name>|<namespace>
terraform import volcenginecc_cr_repository.app <registry-name>|<namespace>|<repository>
terraform import volcenginecc_cr_endpoint_acl_policy.public <registry-name>|<entry-cidr>
```
