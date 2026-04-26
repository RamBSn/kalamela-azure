output "app_url" {
  description = "Public HTTPS URL of the web app"
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "app_name" {
  description = "Web App name"
  value       = azurerm_linux_web_app.main.name
}

output "resource_group" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "kudu_url" {
  description = "Kudu/SCM console URL — use for SSH access and browsing /home files"
  value       = "https://${azurerm_linux_web_app.main.name}.scm.azurewebsites.net/"
}

output "data_dir" {
  description = "Persistent data directory used for SQLite DB, uploads, and backups"
  value       = var.data_dir
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}
