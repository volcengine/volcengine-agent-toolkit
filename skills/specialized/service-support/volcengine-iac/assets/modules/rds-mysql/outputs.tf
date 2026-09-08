output "instance_id" {
  value       = volcengine_rds_mysql_instance.main.id
  description = "RDS MySQL instance ID"
}

output "endpoints" {
  value       = volcengine_rds_mysql_instance.main.endpoints
  description = "Full endpoints list (Cluster/Primary/Custom; each has address, port, network_type). volcengine-deploy parses this to extract the Private/Cluster endpoint."
}
