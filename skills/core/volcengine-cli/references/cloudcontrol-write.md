# Cloud Control API: create, update, delete

Read [cloudcontrol.md](cloudcontrol.md) first for what Cloud Control is, the command shapes, listing and type discovery. Confirmation follows the mode chosen in [safety.md](safety.md).

## Schema-First Workflow (mandatory for Create/Update)

Cloud Control validates against the resource schema, so **always fetch the schema first** and build properties strictly from it. Never invent or guess property values.

1. `DescribeResourceType --TypeName ...` → read the schema.
2. From the schema, note:
   - `required` — must be present on create.
   - `createOnlyProperties` — settable only at create time; immutable afterward.
   - `readOnlyProperties` — returned by the service, never sent.
   - `writeOnlyProperties` — can be sent but never read back (e.g. passwords).
   - `primaryIdentifier` — which property path(s) form the `Identifier` for Get/Update/Delete.
   - `filterProperties` — for listing: `filterableProperties` are the property paths you may filter on, and `required` lists filters that **must** be supplied to `ListResources` (see "Listing Resources" in [cloudcontrol.md](cloudcontrol.md)).
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
