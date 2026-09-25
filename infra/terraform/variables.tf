variable "location" {
  description = "Azure region for future Terraform-managed resources."
  type        = string
  default     = "Southeast Asia"
}

variable "resource_group_name" {
  description = "Azure resource group containing the healthcare lakehouse environment."
  type        = string
  default     = "rg-lakehouse-portfolio"
}

variable "storage_account_name" {
  description = "Azure Data Lake Storage Gen2 account used by the healthcare lakehouse."
  type        = string
  default     = "stlakehousebello"
}

variable "event_hubs_namespace_name" {
  description = "Azure Event Hubs namespace used for streaming ingestion."
  type        = string
  default     = "eh-lakehouse-bello"
}

variable "event_hub_name" {
  description = "Azure Event Hub used by the streaming ingestion pipeline."
  type        = string
  default     = "healthcare-events"
}

variable "synapse_workspace_name" {
  description = "Azure Synapse workspace used for serverless SQL serving."
  type        = string
  default     = "syn-lakehouse-bello"
}
