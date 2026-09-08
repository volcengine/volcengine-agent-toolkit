# Volcenginecc IAM Users Example

Verified example path:

```text
assets/examples/volcenginecc-iam-users/main.tf
```

Use this example when a Volcengine deployment needs Terraform-managed IAM users and groups for human or automation identities. The example creates one read-only group and one user without console login or access keys.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_iam_group` | User group for shared policy attachment |
| `volcenginecc_iam_user` | IAM sub-user identity for controlled access |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-iam-users
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

Observed apply result: `volcenginecc_iam_group.readers` and `volcenginecc_iam_user.app` created successfully. A follow-up plan returned `No changes`. Destroy removed both resources and final state was empty.

Observed IDs in the verification account:

```text
group_name = cc-iac-iam-users-group
user_name  = cc-iac-iam-users-user
```

## Pitfalls found during verification

1. The example intentionally does not set `login_profile.password`. Console login passwords would be stored in Terraform configuration/state, so add them only through a secret-managed workflow.

2. Do not add `volcenginecc_iam_accesskey` to shared examples. The resource exposes `secret_access_key` as a read-only state attribute, so a successful apply writes a newly generated secret into Terraform state. If a deployment truly needs access keys, use encrypted remote state, short-lived keys, explicit rotation, and strict state access controls.

3. `volcenginecc_iam_group.attached_policies.policy_scope` must be fully defined as a nested set item. For global system policies, `policy_scope_type = "Global"` was enough for a clean no-op plan.

4. `volcenginecc_iam_user.groups` can reference the group name directly. Creating membership through the user resource and attaching a policy through the group resource produced a clean no-op plan.

5. IAM user and group names are account-scoped enough to collide during repeated tests. Change `local.prefix` or import existing identities before applying in a shared account.

## Import IDs

```bash
terraform import volcenginecc_iam_group.readers <user-group-name>
terraform import volcenginecc_iam_user.app <user-name>
```
