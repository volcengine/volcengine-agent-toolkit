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

variable "encoded_saml_metadata_document" {
  type        = string
  description = "Base64-encoded SAML IdP metadata XML. The metadata should contain a public signing certificate only."
}

resource "volcenginecc_iam_saml_provider" "main" {
  saml_provider_name             = "cc-iac-saml"
  description                    = "volcenginecc SAML provider example"
  encoded_saml_metadata_document = var.encoded_saml_metadata_document
  sso_type                       = 1
}

output "saml_provider_name" {
  value = volcenginecc_iam_saml_provider.main.saml_provider_name
}
