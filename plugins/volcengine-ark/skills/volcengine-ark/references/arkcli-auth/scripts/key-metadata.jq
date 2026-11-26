# Input: complete apikey.list JSON, --arg id <observed numeric Id as text>.
# Fail closed on incomplete pages, duplicate IDs or integers jq cannot represent safely.
def safe_id: type == "number" and . > 0 and . <= 9007199254740991 and floor == .;
.Result as $r
| if ($r | type) != "object" or ($r.Items | type) != "array" then
    error("expected complete Result.Items")
  elif ($r.TotalCount | type) != "number" then
    error("expected numeric TotalCount")
  elif $r.TotalCount != ($r.Items | length) then
    error("incomplete inventory: item count differs from TotalCount")
  elif any($r.Items[]; (.Id | safe_id | not)) then
    error("invalid or unsafe Id: use an exact-integer parser")
  elif ([$r.Items[].Id] | unique | length) != $r.TotalCount then
    error("duplicate Id in inventory")
  else $r end
| . as $inventory
| [.Items[] | select((.Id | tostring) == $id)] as $matches
| if ($matches | length) != 1 then error("expected one exact numeric Id match") else
    ($matches[0] | {
      Id, SID: (.SID // null), Name: (.Name // null),
      ProjectName: (.ProjectName // null), Status: (.Status // null),
      LastAccessTime: (.LastAccessTime // null), AccessControlInfo: (.AccessControlInfo // null)
    }) as $selected
    | {
        total_count: $inventory.TotalCount,
        status_counts: ($inventory.Items
          | map(if (.Status | type) == "string" and (.Status | length) > 0
                then .Status else "__unknown__" end)
          | group_by(.) | map({status: .[0], count: length})),
        selected: $selected,
        missing_fields: ($selected | to_entries
          | map(select(.value == null or .value == "") | .key))
      }
  end
