terraform {
  required_version = ">= 1.0.7"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "~> 0.0.46"
    }
  }
}

provider "volcenginecc" {}

resource "volcenginecc_iam_oidc_provider" "github" {
  oidc_provider_name  = "cc-iac-oidc-github"
  issuer_url          = "https://token.actions.githubusercontent.com"
  client_ids          = ["sts.volcengine.example"]
  thumbprints         = ["b41ae0832808ebc94951437bf7e92b93ccb6479364daf894d46d6001bee7a486"]
  description         = "volcenginecc OIDC provider example"
  issuance_limit_time = 10
}

output "oidc_provider_name" {
  value = volcenginecc_iam_oidc_provider.github.oidc_provider_name
}
