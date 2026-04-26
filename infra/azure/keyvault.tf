# ── Key Vault ──────────────────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = var.key_vault_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Use Azure RBAC for access control (modern approach, replaces access policies)
  enable_rbac_authorization = true

  # Soft-delete keeps secrets recoverable for 7 days after deletion
  soft_delete_retention_days = 7
  purge_protection_enabled   = false  # set true in production if accidental purge is a concern
}

# # ── Secrets ────────────────────────────────────────────────────────────────────

# resource "azurerm_key_vault_secret" "secret_key" {
#   name         = "flask-secret-key"
#   value        = var.secret_key
#   key_vault_id = azurerm_key_vault.main.id

#   depends_on = [azurerm_role_assignment.deployer_kv_officer]
# }

# resource "azurerm_key_vault_secret" "admin_password" {
#   name         = "admin-password"
#   value        = var.admin_password
#   key_vault_id = azurerm_key_vault.main.id

#   depends_on = [azurerm_role_assignment.deployer_kv_officer]
# }

# ── Role assignments ───────────────────────────────────────────────────────────

# The identity running `terraform apply` needs Secrets Officer to create/update secrets.
resource "azurerm_role_assignment" "deployer_kv_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# The web app's managed identity needs Secrets User to read secrets at runtime.
# This is created after the web app so we can reference its principal_id.
resource "azurerm_role_assignment" "webapp_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.main.identity[0].principal_id
}
