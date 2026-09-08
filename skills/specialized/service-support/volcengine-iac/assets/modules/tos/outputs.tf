output "bucket_name" {
  value       = volcengine_tos_bucket.main.bucket_name
  description = "Bucket name; consumed by volcengine-deploy as TOS_BUCKET env var"
}

output "intranet_endpoint" {
  value       = volcengine_tos_bucket.main.intranet_endpoint
  description = "Internal-network endpoint (preferred when accessing from Volcengine compute)"
}

output "extranet_endpoint" {
  value       = volcengine_tos_bucket.main.extranet_endpoint
  description = "Public-internet endpoint"
}

output "location" {
  value       = volcengine_tos_bucket.main.location
  description = "Bucket geographic location (region)"
}
