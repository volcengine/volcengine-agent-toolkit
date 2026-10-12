# IAM Service Notes

## UpdateUser does not support Tags

`UpdateUser` can only modify basic attributes such as Description and DisplayName. It cannot manage tags.

**Correct approach:** use `TagResources` to tag users separately:

```bash
ve iam TagResources --ResourceType "User" --ResourceNames.1 "<UserName>" --Tags.1.Key "key" --Tags.1.Value "value"
```

The same applies to roles — use `TagResources` with `ResourceType` set to `Role`.

---

## Verified temporary user tag flow

For testing IAM user tagging, create a disposable user and delete it in the same run. `CreateUser` can set initial tags, and `TagResources` adds more tags afterward.

Run the write commands below one per call and check each result before the next: if one is blocked or held for confirmation (`SKILL.md` §2), the shell still runs the commands after it.

```bash
user_name="cli-skill-test-user"

ve iam CreateUser \
  --UserName "$user_name" \
  --Description "cli-skill-test" \
  --Tags.1.Key "publish-by" \
  --Tags.1.Value "deploy-skill"

ve iam TagResources \
  --ResourceType "User" \
  --ResourceNames.1 "$user_name" \
  --Tags.1.Key "purpose2" \
  --Tags.1.Value "cli-skill-test"

ve iam GetUser --UserName "$user_name"

ve iam UntagResources \
  --ResourceType "User" \
  --ResourceNames.1 "$user_name" \
  --TagKeys.1 "purpose2"

ve iam DeleteUser --UserName "$user_name"
```

After deletion, `ve iam GetUser --UserName "$user_name"` should fail with `UserNotExist`; use that as the release confirmation for disposable IAM users.
