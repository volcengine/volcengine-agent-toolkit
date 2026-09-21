# Template B — deploy into the current management account (no AssumeRole).
#
# Bare default provider: no alias, no assume_role, only region. The base
# credential from the run's Terraform runtime environment acts directly on the
# current management account, so resources need no `provider =` line.

provider "volcenginecc" {
  region = var.region
}
