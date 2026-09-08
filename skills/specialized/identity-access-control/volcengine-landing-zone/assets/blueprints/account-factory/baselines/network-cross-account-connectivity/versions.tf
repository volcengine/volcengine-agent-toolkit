terraform {
  required_version = ">= 1.5.0"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = ">= 0.0.41"
    }
  }
}
