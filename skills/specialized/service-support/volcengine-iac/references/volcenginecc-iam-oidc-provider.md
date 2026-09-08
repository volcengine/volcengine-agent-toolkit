# Volcenginecc IAM OIDC Provider Example

Verified example path:

```text
assets/examples/volcenginecc-iam-oidc-provider/main.tf
```

Use this example when a deployment needs an IAM OIDC provider for external workload identity federation. The verified example uses GitHub Actions' public OIDC issuer only to prove provider lifecycle; production deployments must choose client IDs and trust policies deliberately.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_iam_oidc_provider` | External OIDC identity provider metadata for IAM federation |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-iam-oidc-provider
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

Observed apply result: OIDC provider created successfully. A follow-up plan returned `No changes`. Destroy removed the OIDC provider and final state was empty.

Observed ID in the verification account:

```text
oidc_provider_name = cc-iac-oidc-github
```

## Pitfalls found during verification

1. `thumbprints` expects a lowercase SHA256 certificate fingerprint string without colons. The verified thumbprint was collected with:

```bash
openssl s_client -servername token.actions.githubusercontent.com -connect token.actions.githubusercontent.com:443 </dev/null 2>/dev/null | \
  openssl x509 -fingerprint -sha256 -noout | \
  sed 's/^.*=//; s/://g' | tr 'A-Z' 'a-z'
```

2. Use a real HTTPS issuer URL. Placeholder URLs or private endpoints that Cloud Control cannot validate should not be committed as examples.

3. The `client_ids` value is part of the federation trust boundary. The sample `sts.volcengine.example` is only a lifecycle-validation value; replace it with the audience used by the real IdP integration.

4. Creating the IdP alone does not grant access. Pair it with a narrowly scoped IAM role trust policy and test `sts:AssumeRoleWithWebIdentity` separately for real deployments.

5. OIDC provider names are account-scoped enough to collide during repeated tests. Change `oidc_provider_name` or import the existing provider before applying in a shared account.

## Import IDs

```bash
terraform import volcenginecc_iam_oidc_provider.github <oidc-provider-name>
```
