# Storage Service Notes

## TOS Product CLI

Use `ve tosutil` for TOS bucket and object operations. Follow
[Product CLI routing](../SKILL.md#product-cli-routing) to find and load `volcengine-tosutil`
through `volcengine-find-skills`, then follow that skill with the `ve` command prefix.
This is a delegated product CLI, independent of whether native OpenAPI metadata exposes
a `tos` service. `ve` can install the child on demand; standalone `tosutil` is not required.

## File-System Creation Is Billable

EFS, FileNAS, and vePFS read paths worked in `cn-beijing`; all returned empty filesystem lists.

Creation is billable and may require zone/product sale checks. FileNAS and vePFS zone APIs include sale/status details; inspect those before choosing a zone.
