variable "region" {
  description = "Volcengine region in which the baseline is deployed."
  type        = string
}

variable "account_id" {
  description = "Account ID of the member account into which this baseline is deployed."
  type        = string
}

variable "network_account_id" {
  description = "Enterprise shared-network account ID that owns the shared transit router."
  type        = string
}

variable "transit_router_id" {
  description = "Shared-network transit router ID."
  type        = string
}

variable "transit_router_resource_share_name" {
  description = "Existing transit-router resource share name created by 05-network and updated by this baseline."
  type        = string
}

variable "transit_router_dmz_public_route_table_name" {
  description = "Shared TR route table name created by 05-network for DMZ/public egress learning."
  type        = string
}

variable "transit_router_egress_route_table_name" {
  description = "Shared TR route table name created by 05-network for workload-account default egress association."
  type        = string
}

variable "network_vpc_attachment_id" {
  description = "Output from 05-network: the shared network-foundation VPC attachment ID that serves as the egress next hop."
  type        = string
}

variable "workload_vpc_cidr" {
  description = "Workload account VPC CIDR."
  type        = string
}

variable "workload_subnet_cidr_az_a" {
  description = "Workload account subnet CIDR in availability zone A."
  type        = string
}

variable "workload_subnet_cidr_az_b" {
  description = "Workload account subnet CIDR in availability zone B."
  type        = string
}

variable "availability_zone_a" {
  description = "Availability zone A used by the workload account. Required; must belong to var.region (e.g. region suffixed with -a). No default, to avoid silently deploying into a wrong-region zone."
  type        = string
}

variable "availability_zone_b" {
  description = "Availability zone B used by the workload account. Required; must belong to var.region (e.g. region suffixed with -b). No default, to avoid silently deploying into a wrong-region zone."
  type        = string
}

variable "attach_to_shared_network" {
  description = "Whether to attach the workload VPC to the shared transit router."
  type        = bool
  default     = true
}
