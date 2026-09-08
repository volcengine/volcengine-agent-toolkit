output "cluster_id" {
  value       = volcengine_vke_cluster.main.id
  description = "VKE cluster resource ID"
}

output "kubeconfig_private" {
  value       = volcengine_vke_cluster.main.kubeconfig_private
  description = "BASE64-encoded kubeconfig for private network access; pipe through `base64 -d > ~/.kube/config`"
  sensitive   = true
}

output "kubeconfig_public" {
  value       = volcengine_vke_cluster.main.kubeconfig_public
  description = "BASE64-encoded kubeconfig for public access (only set when enable_public_api=true)"
  sensitive   = true
}

output "node_pool_id" {
  value       = volcengine_vke_node_pool.main.id
  description = "Default node pool ID; useful for manual scaling overrides"
}
