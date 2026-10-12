# Cloud Control API (cloudcontrol) Service Notes

## What Cloud Control API Is For

Cloud Control API (`ve cloudcontrol`) is a **unified, resource-oriented control plane** for hundreds of Volcengine resource types. Instead of learning each product's own Create/Describe/Delete verbs, you drive every resource through the same small set of generic actions using a JSON-Schema-defined property model:

- `ListResourceTypes` — enumerate every resource type Cloud Control supports
- `DescribeResourceType` — get the JSON Schema (Draft-7) for one resource type
- `ListResources` — list resources of a given type
- `GetResource` — read one resource by identifier
- `CreateResource` — create a resource from a `TargetState` property object
- `UpdateResource` — update a resource with an RFC 6902 JSON Patch
- `DeleteResource` — delete a resource by identifier
- `GetTask` / `ListTasks` — track asynchronous operation progress

Prefer the product-specific `ve <svc> <action>` path when the product note in this skill already covers your task well. Reach for `ve cloudcontrol` when: the resource type is not exposed by a dedicated `ve` subcommand, you want a schema-driven / IaC-style workflow, or you are managing many heterogeneous resource types through one consistent interface.

Type names use the form `Volcengine::<Service>::<Resource>`, for example `Volcengine::IAM::User`, `Volcengine::ECS::Instance`, `Volcengine::CLB::Rule`.

## Command Shapes

Confirmation follows the mode chosen in `SKILL.md` §2. In built-in mode, `List*`/`Describe*`/`Get*` are read-only and `Create*`/`Update*`/`Delete*` require confirmation; the confirmation notes below apply only in this mode. In safety-policy mode, run the Cloud Control command and follow the CLI's result (§2). Do not inspect policy rules to select another API route.

Parameter form differs per action — always check `--help` first rather than assuming a shape:

- `ListResourceTypes`, `DescribeResourceType` expose **flat parameters only**.
- `ListResources`, `GetResource`, `CreateResource`, `UpdateResource`, `DeleteResource`, `GetTask` expose both a flat form and a JSON `--body` form; use `--body` when the payload contains nested objects (properties, patch documents).

```bash
# Discover what types exist (paginate — see "Resource type discovery" below)
ve cloudcontrol ListResourceTypes --MaxResults 100

# Get the schema BEFORE creating or updating — it is the source of truth
ve cloudcontrol DescribeResourceType --TypeName "Volcengine::IAM::User"

# List existing resources of a type (some types need a required Filter; results paginate — see "Listing Resources")
ve cloudcontrol ListResources --TypeName "Volcengine::IAM::User" --MaxResults 50

# Read one resource
ve cloudcontrol GetResource --TypeName "Volcengine::IAM::User" --Identifier "my-user"
```

## Schema-First Workflow (mandatory for Create/Update)

Cloud Control validates against the resource schema, so **always fetch the schema first** and build properties strictly from it. Never invent or guess property values.

1. `DescribeResourceType --TypeName ...` → read the schema.
2. From the schema, note:
   - `required` — must be present on create.
   - `createOnlyProperties` — settable only at create time; immutable afterward.
   - `readOnlyProperties` — returned by the service, never sent.
   - `writeOnlyProperties` — can be sent but never read back (e.g. passwords).
   - `primaryIdentifier` — which property path(s) form the `Identifier` for Get/Update/Delete.
   - `filterProperties` — for listing: `filterableProperties` are the property paths you may filter on, and `required` lists filters that **must** be supplied to `ListResources` (see "Listing Resources" below).
   - `handlers.<create|read|update|delete|list>.permissions` — the underlying product actions each operation needs (e.g. `clb:CreateRules`); use these to configure the identity's permissions.
3. Build properties that conform exactly; prompt the user for any missing required value rather than fabricating one.

### Create

`CreateResource` requires `TypeName` plus a `TargetState` object that holds the resource properties. `TargetState` is mandatory — top-level property fields are **not** accepted; they must be nested inside `TargetState`. In built-in mode, confirm the full command with the user first.

```bash
ve cloudcontrol CreateResource --body '{
  "TypeName": "Volcengine::IAM::User",
  "ClientToken": "create-my-user-001",
  "TargetState": {
    "UserName": "my-user",
    "Description": "created via cloudcontrol"
  }
}'
```

- **ClientToken idempotency:** generate the token **once per logical operation** and reuse the *same* token on every retry of that operation. Retrying with a new token defeats idempotency and can create duplicate resources. Only use a fresh token for a genuinely new operation.
- If the resource type supports tags, consider adding management tags (e.g. `publish-by=deploy-skill`) consistent with the rest of this skill.

### Update (RFC 6902 JSON Patch)

`UpdateResource` requires `TypeName`, the `Identifier`, and a `PatchDocument` (a JSON Patch array). Do not target `createOnlyProperties` or `readOnlyProperties`; the service will reject those.

```bash
ve cloudcontrol UpdateResource --body '{
  "TypeName": "Volcengine::IAM::User",
  "Identifier": "my-user",
  "PatchDocument": [
    {"op": "replace", "path": "/Description", "value": "updated via cloudcontrol"}
  ]
}'
```

Supported ops: `add`, `remove`, `replace`, `move`, `copy`, `test`.
- `add` / `replace` / `test` require a `value`.
- `move` / `copy` require a `from`.

If an update fails because a targeted field is create-only, that field cannot be changed on the existing resource. `UpdateResource` always operates on the given `Identifier` — switching `TypeName` does **not** let you keep updating the same resource. To change a create-only field you must either recreate the resource with the new value, or use that product's dedicated update API if one exists.

### Delete

```bash
ve cloudcontrol DeleteResource --body '{
  "TypeName": "Volcengine::IAM::User",
  "Identifier": "my-user",
  "ClientToken": "delete-my-user-001"
}'
```

Deletion is destructive. In built-in mode, show the impact and require explicit confirmation before running; for multi-resource deletions, confirm each or the batch explicitly.

## Listing Resources

`ListResources` has two traps that make a naive call miss resources or fail outright.

**1. Required filters (parent-scoped resources).** Child resources cannot be listed account-wide — they must be scoped to a parent. The schema's `filterProperties.required` names the mandatory filter(s); omitting them fails with `MissingParameter` / `InvalidParameter`. For example `Volcengine::CLB::Rule` requires `ListenerId` and `Volcengine::CR::Repository` requires `Registry`. Read `filterProperties` first, then pass the filter via the `--body` JSON `Filter` object:

```bash
ve cloudcontrol ListResources --body '{
  "TypeName": "Volcengine::CLB::Rule",
  "MaxResults": 50,
  "Filter": {"ListenerId": "lsn-xxxxxxxx"}
}'
```

**2. Pagination.** `ListResources` is paginated just like `ListResourceTypes` — a single call returns at most one page plus a `NextToken`, not the whole list. Treating the first page as complete can wrongly conclude a resource does not exist (e.g. `Volcengine::ECS::Image` is 6 pages / 275 items, `Volcengine::IAM::Policy` is 17 pages / 806 items). Page through `NextToken` until it is empty, checking each call's exit code:

```bash
python3 - "Volcengine::ECS::Image" <<'PY'
import subprocess, json, sys
type_name = sys.argv[1]
req_filter = {}          # e.g. {"ListenerId": "lsn-xxxx"} for parent-scoped types; read filterProperties.required
next_tok, page, items = "", 0, []
while True:
    page += 1
    body = {"TypeName": type_name, "MaxResults": 50}
    if req_filter:
        body["Filter"] = req_filter
    if next_tok:
        body["NextToken"] = next_tok
    r = subprocess.run(["ve", "cloudcontrol", "ListResources", "--body", json.dumps(body)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"page {page} failed: {r.stderr.strip()}")
    result = json.loads(r.stdout, strict=False)["Result"]
    items += result.get("ResourceDescriptions", [])
    next_tok = result.get("NextToken", "") or ""
    if not next_tok:
        break
print(f"total: {len(items)} across {page} page(s)")
PY
```

## Identifiers

`GetResource`, `UpdateResource`, and `DeleteResource` all require the `Identifier`. **Use the exact `Identifier` string returned by `ListResources`, `GetResource`, `CreateResource`, or `GetTask` — do not construct or reformat it yourself.** Many resource types have a composite `primaryIdentifier` (for example `Volcengine::CLB::Rule` keys on `[ListenerId, RuleId]`), and the serialization of composite keys is service-defined. Passing the service-returned identifier verbatim is the only reliable way to cover the full range of resource types.

## Asynchronous Operations and Task Polling

Create/Update/Delete may complete synchronously or asynchronously. The response carries an `OperationStatus` and, for async work, a `TaskID`. Observed statuses are `IN_PROGRESS` (in flight), `SUCCESS`, and `FAILED`.

- If the response `OperationStatus` is already `SUCCESS`, the operation is done — do **not** call `GetTask`.
- If it is `FAILED`, report the error and stop.
- If it is `IN_PROGRESS` (or any non-terminal value), poll `GetTask --TaskId <id>` until `OperationStatus` becomes `SUCCESS` (done) or `FAILED` (report and stop). On `SUCCESS`, `GetTask` always returns the `Identifier`; create/update tasks also include a `ResourceModel` snapshot, but delete tasks typically return only the `Identifier` (no `ResourceModel`) — do not assume the field is present.

```bash
# Only when the create/update/delete response was not already terminal.
# Note the casing: the response field is "TaskID", but the GetTask parameter is --TaskId.
ve cloudcontrol GetTask --TaskId "<task-id>"
```

Treat `SUCCESS` and `FAILED` as the only terminal states. Bound the polling loop with a timeout / maximum attempt count instead of looping forever, and if the status is missing or unrecognized, stop and surface it rather than assuming it means "keep polling". Follow the "poll every ~30s until terminal" cadence used elsewhere in this skill, and for creates only report success once an `Identifier` is returned.

## Permissions

Cloud Control calls require both the Cloud Control permission and the permission for the underlying product. Holding `CloudControlFullAccess` alone does not grant the right to operate the target resource — the same identity must also have that product's action permissions. Read the target type's schema `handlers.<operation>.permissions` to see exactly which product actions the operation needs, and grant those. On `AccessDenied`/`NoPermission`/`Forbidden`, activate the `volcengine-troubleshooting` skill's account-permission diagnosis.

System preset policies (see IAM console → Policy Management → System policies):
- `CloudControlFullAccess` — full management of the Cloud Control API.
- `CloudControlReadOnlyAccess` — read-only access to the Cloud Control API.

See the official permissions guide: https://www.volcengine.com/docs/86682/1850846

## Resource Type Discovery

`ListResourceTypes` is paginated. Each page's `NextToken` is a long base64 string, and response bodies can contain unescaped control characters that break naive shell/`jq` parsing. To decide whether a type is supported, page through the full list (following `NextToken` until it is empty) and check whether your target `TypeName` appears — only if you reach the end without finding it can you conclude it is absent. Check every call's exit code and abort the loop on failure rather than silently treating it as "no more pages". Use a real JSON parser with lenient string handling. Region is optional — omit it to use the profile default; only pass `--region <region>` when you specifically want another region (the check is per-region):

```bash
python3 - "Volcengine::VPC::VPC" <<'PY'
import subprocess, json, sys
target = sys.argv[1] if len(sys.argv) > 1 else None
region = None            # e.g. "cn-shanghai"; leave None to use the profile default
next_tok, page, names = "", 0, []
while True:
    page += 1
    cmd = ["ve", "cloudcontrol", "ListResourceTypes", "--MaxResults", "100"]
    if next_tok:
        cmd += ["--NextToken", next_tok]
    if region:
        cmd += ["--region", region]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"page {page} failed: {r.stderr.strip()}")
    result = json.loads(r.stdout, strict=False)["Result"]   # strict=False tolerates control chars
    names += [t["TypeName"] for t in result.get("TypeList", [])]
    next_tok = result.get("NextToken", "") or ""
    if not next_tok:
        break
print(f"total types: {len(names)}")
if target:
    print(f"{target}: {'found' if target in names else 'NOT FOUND'}")
else:
    for n in sorted(names):
        print(n)
PY
```

## Gotchas

- **Type name casing is exact.** Use `Volcengine::Service::Resource` exactly as returned by `ListResourceTypes`; a wrong case or segment yields a not-found/validation error, not a formatting hint.
- **Schema is authoritative, not the docs in your head.** Re-run `DescribeResourceType` whenever a create/update fails validation; required fields and enums differ per type.
- **Region is optional and per-call.** Cloud Control is regional but region is not required — calls use the profile default when omitted. Pass `--region <region>` only to target another region; it does take effect — the response `Region` changes accordingly. Regional resources (VPC, ECS, etc.) are not visible across regions; global resources (e.g. IAM users, which list and read identically under any `--region`) are the exception.
- **Not every product is covered.** If `ListResourceTypes` (fully paginated) does not list the type you need, fall back to the product-specific `ve <svc>` API. Official supported list: https://www.volcengine.com/docs/86682/1850848
- **Complex resources may need several tries.** Some resources depend on others (e.g. an ECS instance needs a VPC/subnet/security group). Create dependencies first, poll them to ready, then create the dependent resource.
