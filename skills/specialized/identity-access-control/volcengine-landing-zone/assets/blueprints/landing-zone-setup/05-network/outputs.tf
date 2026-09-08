output "transit_router_id" {
  description = "中转路由器 (TR) ID"
  value       = volcenginecc_transitrouter_transit_router.this.id
}

output "transit_router_resource_trn" {
  description = "中转路由器 (TR) 资源 TRN，用于资源共享和后续对账"
  value       = local.transit_router_resource_trn
}

output "transit_router_resource_share_name" {
  description = "由网络账号持有、供后续成员账号逐个接入的 TR 共享单元名称"
  value       = local.transit_router_resource_share_name
}

output "network_vpc_id" {
  description = "网络底座 VPC ID"
  value       = volcenginecc_vpc_vpc.network.id
}

output "network_subnet_az_a_id" {
  description = "网络底座子网 ID (可用区 A)"
  value       = volcenginecc_vpc_subnet.network_az_a.id
}

output "network_subnet_az_b_id" {
  description = "网络底座子网 ID (可用区 B)"
  value       = volcenginecc_vpc_subnet.network_az_b.id
}

output "network_vpc_attachment_id" {
  description = "网络底座 VPC 与 TR 的连接 ID"
  value       = volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id
}

output "transit_router_dmz_public_route_table_name" {
  description = "中心 TR 中承载 DMZ / 公网出口方向的共享路由表名称"
  value       = local.tr_route_table_dmz_public_name
}

output "transit_router_egress_route_table_name" {
  description = "中心 TR 中承载成员账号默认出向能力的共享路由表名称"
  value       = local.tr_route_table_egress_name
}

output "nat_gateway_id" {
  description = "网络底座统一公网出口 NAT 网关 ID；未启用 NAT 时为 null"
  value       = try(volcenginecc_natgateway_ngw.network_public_egress[0].nat_gateway_id, null)
}

output "nat_eip_id" {
  description = "绑定到网络底座 NAT 网关的 EIP ID；未启用 NAT 时为 null"
  value       = try(volcenginecc_vpc_eip.network_nat[0].allocation_id, null)
}

output "nat_eip_address" {
  description = "绑定到网络底座 NAT 网关的公网地址；未启用 NAT 时为 null"
  value       = try(volcenginecc_vpc_eip.network_nat[0].eip_address, null)
}

output "nat_snat_entry_id" {
  description = "网络底座统一公网出口 SNAT 规则 ID；未启用 NAT 时为 null"
  value       = try(volcenginecc_natgateway_snatentry.network_public_egress[0].snat_entry_id, null)
}
