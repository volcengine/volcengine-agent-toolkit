# Volcenginecc IAM Example

Verified example path:

```text
assets/examples/volcenginecc-iam/main.tf
```

Use this example when a Volcengine deployment needs Terraform-managed IAM project, role, and custom policy primitives for access segregation or service-to-service trust.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_iam_project` | Project namespace for grouping cloud resources and permission boundaries |
| `volcenginecc_iam_role` | Assumable role for cross-service or automation access |
| `volcenginecc_iam_policy` | Custom IAM policy document for least-privilege permissions |

This example deliberately stops at creating the project, role, and policy. It does not bind policies to users, groups, or roles because those bindings depend on the target account's identity model and should be designed per deployment. For IAM users and groups, use the companion verified example [`assets/examples/volcenginecc-iam-users/main.tf`](../assets/examples/volcenginecc-iam-users/main.tf) and notes in [`volcenginecc-iam-users.md`](./volcenginecc-iam-users.md). For external workload identity federation, use [`assets/examples/volcenginecc-iam-oidc-provider/main.tf`](../assets/examples/volcenginecc-iam-oidc-provider/main.tf) or [`assets/examples/volcenginecc-iam-saml-provider/main.tf`](../assets/examples/volcenginecc-iam-saml-provider/main.tf), with notes in [`volcenginecc-iam-oidc-provider.md`](./volcenginecc-iam-oidc-provider.md) and [`volcenginecc-iam-saml-provider.md`](./volcenginecc-iam-saml-provider.md).

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-iam
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_account_id="$(ve sts GetCallerIdentity | jq -r '.Result.AccountId')"
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: IAM project, role, and custom policy created successfully. A follow-up plan returned `No changes`. Destroy removed all 3 resources and final state was empty.

Observed timings in `cn-beijing`: IAM project, role, and policy each created within seconds; destroy also completed within seconds.

## Pitfalls found during verification

1. `iam_role.trust_policy_document` and `iam_policy.policy_document` should be generated with `jsonencode`. Hand-written JSON strings are easy to misquote, and policy formatting differences can create noisy Terraform diffs.

2. The role trust principal needs the real Volcengine account ID. Use `ve sts GetCallerIdentity` or another account-discovery method, pass it through `TF_VAR_account_id`, and keep the example free of account-specific IDs.

3. The verified trust policy uses the account root principal shape `trn:iam::<account-id>:root` with `sts:AssumeRole`. Replace it with narrower principals for production roles.

4. `iam_policy.policy_type` must match the policy namespace. The verified custom policy uses `policy_type = "Custom"`.

5. Project names and IAM role/policy names are global enough within an account to collide across repeated tests. Change `local.prefix` or import existing resources before applying in a shared account.

6. IAM resources are security-sensitive even when the sample policy is read-only. Review the generated plan before apply and avoid broadening `Action` or `Principal` while testing provider behavior.

## Import IDs

```bash
terraform import volcenginecc_iam_project.main <project-name>
terraform import volcenginecc_iam_role.main <role-name>
terraform import volcenginecc_iam_policy.main <policy-name>|Custom
```
