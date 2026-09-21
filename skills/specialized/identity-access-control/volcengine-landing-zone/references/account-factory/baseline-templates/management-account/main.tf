# main.tf — uses the default provider, no `provider = ...` needed.
#
# resource "volcenginecc_vpc_vpc" "example" {
#   # ...
# }
#
# Any `local-exec` here calls `ve` through the `ve` credential path validated in
# preflight.
