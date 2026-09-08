output "workload_vpc_id" {
  description = "Workload account VPC ID."
  value       = volcenginecc_vpc_vpc.workload.id
}

output "workload_subnet_az_a_id" {
  description = "Workload account subnet ID in availability zone A."
  value       = volcenginecc_vpc_subnet.workload_az_a.id
}

output "workload_subnet_az_b_id" {
  description = "Workload account subnet ID in availability zone B."
  value       = volcenginecc_vpc_subnet.workload_az_b.id
}

output "workload_vpc_attachment_id" {
  description = "Attachment ID used to connect the workload VPC to the shared transit router."
  value       = try(volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id, null)
}
