variable "region" {
  description = "Volcengine region in which the baseline is deployed."
  type        = string
}

variable "account_id" {
  description = "Account ID of the member account into which this baseline is deployed. Decides which member account the provider assumes into."
  type        = string
}
