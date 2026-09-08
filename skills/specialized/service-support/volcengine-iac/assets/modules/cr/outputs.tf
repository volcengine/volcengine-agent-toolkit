output "registry_id" {
  value       = volcengine_cr_registry.main.id
  description = "CR registry resource ID"
}

output "registry_name" {
  value       = volcengine_cr_registry.main.name
  description = "Registry name; pass this to ve cr GetAuthorizationToken"
}

output "registry_endpoint" {
  value       = length(volcengine_cr_registry.main.domains) > 0 ? volcengine_cr_registry.main.domains[0].domain : ""
  description = "Registry domain (e.g. cr-xxxx.cr.volces.com); used for docker login"
}

output "registry_username" {
  value       = volcengine_cr_registry.main.username
  description = "CR username for docker login"
}

output "namespace" {
  value       = volcengine_cr_namespace.main.name
  description = "Namespace name"
}

output "repository_name" {
  value       = volcengine_cr_repository.main.name
  description = "Repository name"
}

output "repository_uri" {
  value       = "${length(volcengine_cr_registry.main.domains) > 0 ? volcengine_cr_registry.main.domains[0].domain : ""}/${volcengine_cr_namespace.main.name}/${volcengine_cr_repository.main.name}"
  description = "Full image URI (without tag); volcengine-deploy uses this with :<tag>"
}
