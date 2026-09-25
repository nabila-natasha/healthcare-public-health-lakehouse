# Terraform Infrastructure Foundation


## Purpose

This directory provides the Terraform infrastructure-as-code foundation for the Healthcare Public Health Surveillance & Risk Analytics Lakehouse.

Terraform is included to establish a repeatable infrastructure-management pattern while keeping the current portfolio environment safe and reproducible.

## Current Scope

The current Azure environment was provisioned incrementally during project development using Azure Portal, Azure CLI, and service-specific configuration.

Terraform does **not** currently manage or recreate the existing Azure resources.

This is intentional.

The current Terraform configuration contains:

* AzureRM provider configuration
* Terraform and provider version constraints
* Variables describing the project environment
* Outputs exposing the configured environment values
* Documentation of the current infrastructure-management boundary

There are currently no Azure `resource` blocks in this configuration.

Therefore, running Terraform does not create, modify, or destroy the existing project infrastructure.

## Current Azure Environment

| Component            | Current Resource         |
| -------------------- | ------------------------ |
| Resource Group       | `rg-lakehouse-portfolio` |
| Region               | Southeast Asia           |
| ADLS Gen2            | `stlakehousebello`       |
| Event Hubs Namespace | `eh-lakehouse-bello`     |
| Event Hub            | `healthcare-events`      |
| Synapse Workspace    | `syn-lakehouse-bello`    |

These values document the existing environment. They do not indicate that Terraform currently owns these resources.

## Authentication

Terraform uses the AzureRM provider.

Authentication should use the developer's existing Azure CLI or supported Azure identity mechanism rather than storing credentials in the repository.

No subscription IDs, client secrets, passwords, connection strings, SAS tokens, or API keys are stored in this directory.

For future automated Terraform execution, credentials should be supplied through an appropriate secure CI/CD authentication mechanism.

## Validation

From this directory:

```bash
terraform init
terraform fmt
terraform validate
```

The expected result is a valid Terraform configuration with no Azure resources planned for creation.

A future resource-managed configuration should be introduced deliberately and validated with:

```bash
terraform plan
```

before any infrastructure change is applied.

## Infrastructure Management Boundary

The current project separates:

**Application and data-engineering validation**

* Python
* transformations
* tests
* GitHub Actions CI/CD

from:

**Infrastructure-as-code foundation**

* Terraform
* AzureRM provider
* future infrastructure management

This separation prevents the portfolio project from claiming infrastructure automation that has not actually been implemented.

## Future Evolution

If this project were extended into a more production-oriented environment, Terraform could progressively manage selected resources such as:

1. Resource group
2. ADLS Gen2 storage
3. Event Hubs namespace and Event Hub
4. Azure Data Factory
5. Synapse workspace
6. Role assignments
7. Diagnostic settings
8. Additional security and networking components

Existing resources should be imported or deliberately recreated under Terraform management rather than blindly redeployed.

Infrastructure changes should be reviewed with `terraform plan` before being applied.

## Design Principle

> Terraform is used as an infrastructure-as-code foundation, not as evidence of infrastructure automation that has not yet been implemented.
