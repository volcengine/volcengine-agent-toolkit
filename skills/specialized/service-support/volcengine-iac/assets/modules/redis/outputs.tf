output "instance_id" {
  value       = volcengine_redis_instance.main.id
  description = "Redis instance ID; volcengine-deploy reads connection details via `ve redis DescribeDBInstanceDetail` since the provider does not export endpoints directly"
}

output "port" {
  value       = var.port
  description = "Redis port (configured value; same as instance unless overridden)"
}
