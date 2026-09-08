variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "network_availability_zone_a" {
  description = "网络底座子网与 TR 连接点使用的可用区 A；为空时默认使用 <region>-a"
  type        = string
  default     = null
}

variable "network_availability_zone_b" {
  description = "网络底座子网与 TR 连接点使用的可用区 B；为空时默认使用 <region>-b"
  type        = string
  default     = null
}

variable "prefix" {
  description = "企业名称前缀"
  type        = string
}

variable "management_account_id" {
  description = "管理账号 ID；用于在组织级 CLI 写操作前校验当前 ve 登录态是否处于正确的组织管理员上下文"
  type        = string
}

variable "network_account_id" {
  description = "网络账号 ID（来自阶段 1 输出）"
  type        = string
}

variable "network_vpc_cidr" {
  description = "网络底座 VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "network_subnet_cidr_az_a" {
  description = "网络底座子网 CIDR (可用区 A)"
  type        = string
  default     = "10.0.1.0/24"
}

variable "network_subnet_cidr_az_b" {
  description = "网络底座子网 CIDR (可用区 B)"
  type        = string
  default     = "10.0.2.0/24"
}

variable "create_nat" {
  description = "是否默认在网络底座中创建公网 NAT、EIP 与 SNAT 出向能力"
  type        = bool
  default     = true
}

variable "nat_gateway_name" {
  description = "NAT 网关名称；为空时默认使用 <prefix>-nat"
  type        = string
  default     = null
}

variable "nat_network_type" {
  description = "NAT 网关类型：internet（公网）或 intranet（私网）"
  type        = string
  default     = "internet"
}

variable "nat_spec" {
  description = "NAT 网关规格"
  type        = string
  default     = "Small"
}

variable "eip_name" {
  description = "NAT 绑定 EIP 名称；为空时默认使用 <prefix>-nat-eip"
  type        = string
  default     = null
}

variable "eip_isp" {
  description = "EIP 线路类型"
  type        = string
  default     = "BGP"
}

variable "eip_billing_type" {
  description = "EIP 计费类型：1-包年包月，2-按流量计费，3-按带宽计费"
  type        = number
  default     = 2
}

variable "eip_bandwidth" {
  description = "EIP 带宽（Mbps）"
  type        = number
  default     = 1
}

variable "eip_period" {
  description = "EIP 包年包月购买时长（月）；非包年包月模式下通常被忽略"
  type        = number
  default     = 1
}

variable "eip_direct_mode" {
  description = "EIP 是否启用直通模式"
  type        = bool
  default     = true
}

variable "snat_entry_name" {
  description = "SNAT 规则名称；为空时默认使用 <prefix>-default-snat"
  type        = string
  default     = null
}

variable "snat_source_cidr" {
  description = "通过 NAT 网关访问公网的源网段"
  type        = string
  default     = "172.16.0.0/12"
}
