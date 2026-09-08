variable "project" {
  type        = string
  description = "Project name; assigned to namespace.project for cost allocation"
}

variable "registry_name" {
  type        = string
  description = "CR registry name (also instance identifier); must be unique in account"
}

variable "registry_type" {
  type        = string
  description = "Registry tier: Enterprise (default) or Micro"
  default     = "Enterprise"
  validation {
    condition     = contains(["Enterprise", "Micro"], var.registry_type)
    error_message = "registry_type must be Enterprise or Micro."
  }
}

variable "namespace" {
  type        = string
  description = "CR namespace inside the registry; usually equals project name"
}

variable "repository_name" {
  type        = string
  description = "Image repository name; the full image URI will be <registry-domain>/<namespace>/<repository_name>"
}

variable "access_level" {
  type        = string
  description = "Repository access: Private or Public"
  default     = "Private"
  validation {
    condition     = contains(["Private", "Public"], var.access_level)
    error_message = "access_level must be Private or Public."
  }
}
