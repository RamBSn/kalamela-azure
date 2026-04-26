terraform {
  required_version = ">= 1.3"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  subscription_id  = "a6b13bec-fcd8-4d93-bebe-d1e3688208e4"
  features {}
}

# ── Resource Group ─────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

# ── App Service Plan (B1 Linux) ────────────────────────────────────────────────

resource "azurerm_service_plan" "main" {
  name                = var.app_service_plan_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = var.app_service_sku
}

# ── Web App ────────────────────────────────────────────────────────────────────

resource "azurerm_linux_web_app" "main" {
  name                = var.app_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true

  site_config {
    application_stack {
      python_version = "3.11"
    }
    # Gunicorn startup command
    app_command_line = "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:app"

    # always_on is not available on the Free tier (F1)
    always_on = var.app_service_sku == "F1" ? false : true
  }

  # Managed identity — required for Key Vault references to work
  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    # Key Vault references: Azure resolves these at runtime using the managed identity.
    # Format: @Microsoft.KeyVault(VaultName=...;SecretName=...) always fetches the latest version.
    SECRET_KEY                     = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=flask-secret-key)"
    ADMIN_PASSWORD                 = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=admin-password)"
    DATA_DIR                       = var.data_dir
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    # Tells pip to install from requirements.txt on each deploy
    ENABLE_ORYX_BUILD              = "true"
  }

  # Stream app logs to Log Stream in the portal
  logs {
    http_logs {
      file_system {
        retention_in_days = 7
        retention_in_mb   = 35
      }
    }
    application_logs {
      file_system_level = "Warning"
    }
    detailed_error_messages = true
    failed_request_tracing  = false
  }
}

# ── Optional: custom domain ────────────────────────────────────────────────────
# Uncomment and set var.custom_hostname to bind your own domain.
# DNS must already have a CNAME pointing to the azurewebsites.net hostname.

# resource "azurerm_app_service_custom_hostname_binding" "main" {
#   hostname            = var.custom_hostname
#   app_service_name    = azurerm_linux_web_app.main.name
#   resource_group_name = azurerm_resource_group.main.name
# }

# resource "azurerm_app_service_managed_certificate" "main" {
#   custom_hostname_binding_id = azurerm_app_service_custom_hostname_binding.main.id
# }

# resource "azurerm_app_service_certificate_binding" "main" {
#   hostname_binding_id = azurerm_app_service_custom_hostname_binding.main.id
#   certificate_id      = azurerm_app_service_managed_certificate.main.id
#   ssl_state           = "SniEnabled"
# }
