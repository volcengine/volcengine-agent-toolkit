# Template A — deploy into a newly created member account (needs cross-account AssumeRole).
#
# The provider carries `assume_role` and every managed resource pins this alias.
# Base credential (the identity that initiates AssumeRole) is NOT declared here:
# it comes from the run's Terraform runtime environment. `account_id` decides
# which member account; a wrong account_id fails at AssumeRole during plan/apply
# and never lands resources in the wrong account.
#
# Copy the built-in `network-cross-account-connectivity` package as the canonical
# working reference; this file is the minimal skeleton.

provider "volcenginecc" {
  alias  = "member"
  region = var.region

  assume_role = {
    assume_role_trn          = "trn:iam::${var.account_id}:role/OrganizationAccessControlRole"
    assume_role_session_name = "af-member-baseline"
    duration_seconds         = 3600
  }
}
