# main.tf — every resource pins the member provider so it lands in the assumed member account.
#
# resource "volcenginecc_vpc_vpc" "example" {
#   provider = volcenginecc.member
#   # ...
# }
#
# Any `local-exec` here starts from the current `ve` identity validated in
# preflight. Use it only for actions `volcenginecc` has no resource for (see the
# guidebook "Cross-account execution model"). For provider-supported objects,
# prefer Terraform resources pinned to the alias that owns the object rather than
# self-assuming inside `local-exec`.
