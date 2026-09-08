# Volcenginecc veFaaS Example

Verified example path:

```text
assets/examples/volcenginecc-vefaas/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed veFaaS function, an initial release, and a disabled timer trigger.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vefaas_function` | Serverless function unit with inline ZIP source |
| `volcenginecc_vefaas_release` | Publishes the latest function revision |
| `volcenginecc_vefaas_timer` | Disabled timer trigger attached after a successful release |

## Dependency-blocked resources

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_vefaas_sandbox` | Lifecycle-only | Native/image function, release, sandbox create/destroy succeeded with a pre-cached public sandbox image, but follow-up plans drift on `volcenginecc_vefaas_release` computed fields. |
| `volcenginecc_vefaas_kafka_trigger` | Not in default example | Requires a released function plus a real Kafka instance, topic, and SASL credentials. Do not use placeholder credentials. |

## Verified command sequence

The example shape was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vefaas
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
```

Observed apply result: function, release, and timer created successfully. A follow-up plan returned `No changes`.

Observed timings in `cn-beijing`: function creation took about 15s, release took about 16s, timer creation took about 1s.

Destroy caveat: the timer and function destroy paths were verified, but a successful `volcenginecc_vefaas_release` reached final `finished` status and Cloud Control rejected `DELETE` with `InvalidOperation: This operation is not supported., release already in final status: finished`. For cleanup after a finished release, remove only the release resource from Terraform state, then destroy the function:

```bash
terraform state rm volcenginecc_vefaas_release.main
terraform destroy -input=false
```

## Pitfalls found during verification

1. `source_type = "zip"` is accepted on create, but the service reads it back as `tos`. Without `lifecycle.ignore_changes = [source_type]`, a refreshed plan can propose replacing the function even when the source is unchanged.

2. The ZIP for `runtime = "python3.9/v1"` must contain root-level `index.py`. An empty ZIP created the function, but release failed with `revision_build_failed` and `Unable to find function entry (index.py)`.

3. Do not update a function from an empty ZIP to a valid ZIP as the normal path. The verified attempt hit a veFaaS server-side panic in `UpdateFunction` with `runtime error: slice bounds out of range [:-1]`. Create the function with valid source from the start.

4. Create the timer only after a successful release. Creating a timer before release failed with `InvalidOperation: function has not been fully released yet, please release it first`.

5. A finished `vefaas_release` is an operation record more than a deletable infrastructure object. Terraform destroy can fail on the release even though downstream cleanup should proceed.

6. Do not store real AK/SK, repository passwords, or Kafka SASL credentials in function source, `source_access_config`, or Terraform files. They will land in Terraform state.

## Sandbox retry record

`volcenginecc_vefaas_sandbox` remains excluded from the clean no-op verified example. The lifecycle path now works with a pre-cached public sandbox image, but the required `volcenginecc_vefaas_release` still has computed-field drift after creation.

Verified lifecycle shape:

```hcl
resource "volcenginecc_vefaas_function" "sandbox" {
  name            = "cc-iac-vefaas-sandbox"
  runtime         = "native/v1"
  source_type     = "image"
  source          = "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3"
  command         = "python3 -m http.server 8080 --bind 0.0.0.0"
  port            = 8080
  cpu_strategy    = "always"
  memory_mb       = 512
  request_timeout = 30
  max_concurrency = 10
  project_name    = "default"
}

resource "volcenginecc_vefaas_release" "sandbox" {
  function_id           = volcenginecc_vefaas_function.sandbox.function_id
  revision_number       = 0
  target_traffic_weight = 100
  rolling_step          = 100
  max_instance          = 1
}

resource "volcenginecc_vefaas_sandbox" "sandbox" {
  function_id = volcenginecc_vefaas_release.sandbox.function_id
  instance_image_info = {
    image    = "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3"
    image_id = "kwdxncbgsn"
    command  = "python3 -m http.server 8080 --bind 0.0.0.0"
    port     = 8080
  }
  timeout         = 3
  memory_mb       = 512
  cpu_milli       = 250
  request_timeout = 30
  max_concurrency = 10
}
```

Historical failed shapes:

1. Uncached image `nginx:1.25-alpine` failed before creating any resources:

```text
NotFound: ResourceNotFound: Sandbox image not found in pre cache sandbox image list, you need to precache your sandbox image first
TypeName: Volcengine::VEFAAS::Function
Operation: CREATE
TaskID: task-<id>
EventTime: 2026-05-30T06:46:56+08:00
```

2. Private pre-cached image `vefaas-sandbox-cn-beijing.cr.volces.com/vefaas-sandbox/sandbox-server:latest` with `command = "./run.sh"` created the native function and release, then sandbox create failed because the command did not exist in the image:

```text
EventTime: 2026-05-30T12:08:19+08:00
TaskID: task-<id>
InvalidOperation: error_code: "function_exited", error_message "function exited unexpectedly(exit status 127) ... bash: ./run.sh: No such file or directory"
TypeName: Volcengine::VEFAAS::Sandbox
Operation: CREATE
OperationStatus: FAILED
```

3. Public pre-cached All-in-one image with `/opt/gem/run.sh` created the native function and release, then sandbox create failed because the entrypoint expected user/UID/GID environment that veFaaS did not provide by default:

```text
EventTime: 2026-05-30T12:09:44+08:00
TaskID: task-<id>
InvalidOperation: error_code: "function_exited", error_message "function exited unexpectedly(exit status 1) ... /etc/sudoers.d/: Is a directory"
TypeName: Volcengine::VEFAAS::Sandbox
Operation: CREATE
OperationStatus: FAILED
```

Successful lifecycle retry on 2026-05-30 used public image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3`, `image_id = "kwdxncbgsn"`, and command `python3 -m http.server 8080 --bind 0.0.0.0`. Function creation took about 15s, release about 11s, and sandbox about 10s. The sandbox reached `Ready` and destroyed cleanly; sandbox destroy took about 66s and function destroy about 6s. The release was removed from state before destroy because finished releases are not deletable.

The lifecycle retry is not a clean no-op verified example. A follow-up plan still proposed an in-place update on `volcenginecc_vefaas_release` computed fields such as `creation_time`, `current_traffic_weight`, `description`, `release_record_id`, and status fields even though function and sandbox were stable. Do not add this as a clean generated example until the release no-op drift is resolved or the example is explicitly cataloged as lifecycle-only.

Current provider schema expects sandbox image fields under `instance_image_info`; top-level `image`, `command`, and `port` are invalid for `volcenginecc_vefaas_sandbox`.

## Import IDs

```bash
terraform import volcenginecc_vefaas_function.main <function-id>
terraform import volcenginecc_vefaas_release.main <function-id>
terraform import volcenginecc_vefaas_timer.main <function-id>|<timer-id>
terraform import volcenginecc_vefaas_sandbox.main <function-id>|<sandbox-id>
terraform import volcenginecc_vefaas_kafka_trigger.main <function-id>|<kafka-trigger-id>
```
