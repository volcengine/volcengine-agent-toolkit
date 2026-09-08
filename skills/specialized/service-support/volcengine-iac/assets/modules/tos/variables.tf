variable "bucket_name" {
  type        = string
  description = "TOS bucket name (must be globally unique within Volcengine; lowercase, no underscores, 3–63 chars)"
}

variable "project_name" {
  type        = string
  description = "Project allocation name; defaults to 'default'"
  default     = "default"
}

variable "public_acl" {
  type        = string
  description = "Bucket ACL: private, public-read, public-read-write, authenticated-read, or bucket-owner-read"
  default     = "private"
  validation {
    condition     = contains(["private", "public-read", "public-read-write", "authenticated-read", "bucket-owner-read"], var.public_acl)
    error_message = "public_acl must be one of: private, public-read, public-read-write, authenticated-read, bucket-owner-read."
  }
}

variable "storage_class" {
  type        = string
  description = "Storage tier: STANDARD or IA"
  default     = "STANDARD"
}

variable "az_redundancy" {
  type        = string
  description = "AZ redundancy: single-az or multi-az"
  default     = "single-az"
}

variable "versioning_enabled" {
  type        = bool
  description = "Enable object versioning"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Bucket tags"
  default     = {}
}
