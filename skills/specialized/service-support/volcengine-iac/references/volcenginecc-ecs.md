# Volcenginecc ECS Example

Verified example path:

```text
assets/examples/volcenginecc-ecs/main.tf
```

Use this example when a Volcengine deployment needs Terraform-managed ECS building blocks: a VM, keypair, launch template, Cloud Assistant command, or an attached data volume. The example includes a minimal VPC/subnet/security group so it can be validated independently; for real deployments, reuse the network foundation from `volcenginecc-network` and wire its outputs into the ECS resources.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_ecs_keypair` | SSH keypair resource for ECS access or image bootstrap flows |
| `volcenginecc_storageebs_volume` | Standalone EBS data disk in the same AZ as ECS |
| `volcenginecc_ecs_command` | Cloud Assistant command definition for post-boot scripts |
| `volcenginecc_ecs_launch_template` | Repeatable ECS launch configuration |
| `volcenginecc_ecs_instance` | Runtime VM for direct ECS deployments or utility nodes |
| `volcenginecc_ecs_invocation` | One-off Cloud Assistant command execution; keep as a second-stage apply |

For ECS placement primitives, use the companion verified example [`assets/examples/volcenginecc-ecs-extras/main.tf`](../assets/examples/volcenginecc-ecs-extras/main.tf) and notes in [`volcenginecc-ecs-extras.md`](./volcenginecc-ecs-extras.md). For standalone launch template versions, use [`assets/examples/volcenginecc-ecs-launch-template-version/main.tf`](../assets/examples/volcenginecc-ecs-launch-template-version/main.tf) and notes in [`volcenginecc-ecs-launch-template-version.md`](./volcenginecc-ecs-launch-template-version.md). For manual EBS snapshots of standalone data disks, use [`assets/examples/volcenginecc-ebs-snapshot/main.tf`](../assets/examples/volcenginecc-ebs-snapshot/main.tf) and notes in [`volcenginecc-ebs-snapshot.md`](./volcenginecc-ebs-snapshot.md).

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`, image `image-z0dpqndnmy8rpzcad9rz`, and instance type `ecs.g4i.large`:

```bash
cd assets/examples/volcenginecc-ecs
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
```

Observed base apply result: VPC, subnet, route table, security group, keypair, EBS volume, ECS command, launch template, and ECS instance created successfully. The instance reached `RUNNING`.

For command invocation, wait until Cloud Assistant reports `Running`, then enable the second-stage file:

```bash
ve ecs DescribeCloudAssistantStatus --body '{"InstanceIds":["<instance-id>"]}'
mv invocation.tf.disabled invocation.tf
terraform plan -out=tfplan-invoke.binary -input=false
terraform apply -input=false tfplan-invoke.binary
```

Observed invocation result: command output base64 `dm9sY2VuZ2luZWNjLWVjcy1vawo=`, which decodes to `volcenginecc-ecs-ok`.

Before destroy, remove completed invocations from state if Cloud Control refuses deletion:

```bash
terraform state rm volcenginecc_ecs_invocation.hello
terraform destroy
```

Observed cleanup result: after state-removing the completed invocation, destroy removed the ECS instance, command, launch template, EBS volume, keypair, security group, route table, subnet, and VPC; final state was empty.

## Pitfalls found during verification

1. `volcenginecc_ecs_command.command_content` should be Base64 command text. Setting plaintext content or using `command_content_encoding = "PlainText"` caused update/readback failure with `InvalidBase64Content.Malformed`.

2. `volcenginecc_storageebs_volume.pay_type` accepted lowercase `post`. Using provider/docs-style alternatives can fail validation or API creation.

3. Avoid `volcenginecc_storageebs_volume.description` until re-tested for the target region. A simple English description failed with `InvalidDescriptionFormat`, while omitting the field created the volume successfully.

4. Keep `volcenginecc_ecs_launch_template.launch_template_version.volumes` out of the example unless the provider is re-verified. Including `volumes` created the remote object but Terraform failed with `Provider produced inconsistent result after apply: volumes was set, now null`.

5. `volcenginecc_ecs_invocation` is timing-sensitive. Creating it immediately after the instance can fail with `InvalidInstanceId.Unregister` because Cloud Assistant has not registered yet. Poll `DescribeCloudAssistantStatus` and only apply invocation after status is `Running`.

6. Completed `volcenginecc_ecs_invocation` may not be deletable through Cloud Control. Destroy failed with `InvalidOperation.Forbidden: The specified Invocation is not allowed to operate`. For one-off invocations, remove the invocation resource from state before destroy or manage invocations outside Terraform.

7. `volcenginecc_ecs_instance` produced persistent pseudo-diffs on Optional+Computed nested fields including `image`, `primary_network_interface`, `system_volume`, and `eip_address`. Even `lifecycle { ignore_changes = all }` did not make a follow-up plan clean. Treat ECS instance no-op plans as provider-instability signals and inspect carefully before applying.

8. The verified image is `Ubuntu 24.04 with OpenClaw 64 bit` (`image-z0dpqndnmy8rpzcad9rz`) in `cn-beijing-a`. Replacing region, AZ, or instance type requires checking image availability, Cloud Assistant support, and ECS quota first.

9. The example keypair resource creates a keypair object but does not write a private key for operators. For production SSH access, import an existing keypair or manage key material through a separate secret workflow.

## Import IDs

```bash
terraform import volcenginecc_ecs_keypair.main <key-pair-name>
terraform import volcenginecc_storageebs_volume.data vol-xxxxxxxx
terraform import volcenginecc_ecs_command.hello cmd-xxxxxxxx
terraform import volcenginecc_ecs_launch_template.main lt-xxxxxxxx
terraform import volcenginecc_ecs_instance.main i-xxxxxxxx
terraform import volcenginecc_ecs_invocation.hello inv-xxxxxxxx
```
