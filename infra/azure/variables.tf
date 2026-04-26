variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
  default     = "kalamela-rg"
}

variable "location" {
  description = "Azure region. uksouth is nearest to UK users."
  type        = string
  default     = "uksouth"
}

variable "app_service_plan_name" {
  description = "Name of the App Service Plan"
  type        = string
  default     = "kalamela-plan"
}

variable "app_service_sku" {
  description = <<-EOT
    App Service Plan SKU. Common options:
      F1  — Free (no custom domain/SSL, 60 CPU min/day — testing only)
      B1  — Basic  (~£11/mo, requires Basic VM quota on subscription)
      S1  — Standard (~£14/mo, different quota pool — use if B1 is blocked)
      P1v2 — Premium v2 (~£18/mo, best performance per £)
  EOT
  type        = string
  default     = "B1"

  # validation {
  #   condition     = contains(["F1", "B1", "S1", "B2", "S2", "P1v2", "P2v2"], var.app_service_sku)
  #   error_message = "app_service_sku must be one of: F1, B1, S1, B2, S2, P1v2, P2v2."
  # }
}

variable "app_name" {
  description = "Web App name — must be globally unique across Azure (becomes <app_name>.azurewebsites.net)"
  type        = string
}

variable "secret_key" {
  description = "Flask SECRET_KEY. Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
  type        = string
  sensitive   = true
}

variable "admin_password" {
  description = "Password for the single admin login"
  type        = string
  sensitive   = true
}

variable "key_vault_name" {
  description = "Key Vault name — must be globally unique across Azure, 3-24 chars, alphanumerics and hyphens only"
  type        = string
}

variable "data_dir" {
  description = "Persistent directory on Azure App Service for the SQLite DB, uploads, and backups. /home is an Azure Files mount that survives restarts."
  type        = string
  default     = "/home/kalamela"
}

# Uncomment if using a custom domain
# variable "custom_hostname" {
#   description = "Custom domain to bind, e.g. kalamela.lkc.org.uk"
#   type        = string
#   default     = ""
# }
