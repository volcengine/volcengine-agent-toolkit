output "vpc_id" {
  value       = volcengine_vpc.main.id
  description = "ID of the VPC; consumed by vke / rds / redis modules"
}

output "vpc_cidr" {
  value       = var.vpc_cidr
  description = "VPC CIDR block; useful for security group rule reference"
}

output "subnet_ids" {
  value       = [volcengine_subnet.primary.id, volcengine_subnet.secondary.id]
  description = "All subnet IDs in this VPC; consumed by vke cluster_config.subnet_ids"
}

output "subnet_id_primary" {
  value       = volcengine_subnet.primary.id
  description = "Primary AZ subnet ID; default for single-AZ resources"
}

output "subnet_id_secondary" {
  value       = volcengine_subnet.secondary.id
  description = "Secondary AZ subnet ID; required for HA RDS"
}

output "security_group_id" {
  value       = volcengine_security_group.default.id
  description = "Default security group ID; consumed by node pools and ECS instances"
}
