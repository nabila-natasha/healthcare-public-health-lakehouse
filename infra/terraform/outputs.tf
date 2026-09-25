output "location" {
  description = "Configured Azure region for the healthcare lakehouse."
  value       = var.location
}

output "resource_group_name" {
  description = "Configured Azure resource group name."
  value       = var.resource_group_name
}

output "storage_account_name" {
  description = "Configured ADLS Gen2 storage account name."
  value       = var.storage_account_name
}

output "event_hubs_namespace_name" {
  description = "Configured Event Hubs namespace name."
  value       = var.event_hubs_namespace_name
}

output "event_hub_name" {
  description = "Configured Event Hub name."
  value       = var.event_hub_name
}

output "synapse_workspace_name" {
  description = "Configured Synapse workspace name."
  value       = var.synapse_workspace_name
}
