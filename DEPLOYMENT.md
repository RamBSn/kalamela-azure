# Azure Web App Deployment Guide — LKC Kalamela

## Architecture

- **Runtime**: Python 3.11, Linux App Service
- **WSGI server**: Gunicorn
- **Database**: SQLite stored on Azure Files persistent mount (`/home`)
- **Storage**: Uploads and backups also stored on `/home`

## Why SQLite on Azure is fine here

Azure App Service Linux mounts `/home` as a persistent Azure Files share — it survives restarts and slot swaps. SQLite is ideal for a single-user, single-region admin app with low concurrent writes. No extra database cost.

---

## Cost estimate (cheapest viable option)

| Resource | Tier | Est. monthly cost |
|---|---|---|
| App Service Plan | B1 (Basic, 1 core, 1.75 GB RAM) | ~£11 / $13 |
| Azure Files (via /home) | Included with App Service | £0 |
| Total | | ~£11/month |

> **Free tier (F1)** exists but has no custom domain/SSL and only 60 CPU minutes/day — not suitable for event-day use. B1 is the minimum recommended.

---

## Step-by-step deployment

### 1. Install Azure CLI

```bash
brew install azure-cli        # macOS
# or https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
az login
```

### 2. Create resources

```bash
# Set your preferred values
RESOURCE_GROUP=kalamela-rg
LOCATION=uksouth
APP_SERVICE_PLAN=kalamela-plan
APP_NAME=lkc-kalamela          # must be globally unique on azurewebsites.net

az group create --name $RESOURCE_GROUP --location $LOCATION

az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --sku B1 \
  --is-linux

az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --runtime "PYTHON:3.11"
```

### 3. Configure environment variables (App Settings)

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
    ADMIN_PASSWORD="choose-a-strong-password" \
    DATA_DIR="/home/kalamela" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

> **Important**: copy the generated `SECRET_KEY` somewhere safe. Changing it later will invalidate all existing sessions.

### 4. Set the startup command

```bash
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:app"
```

### 5. Deploy the code

#### Option A — ZIP deploy (simplest, no Git required)

```bash
cd /path/to/kalamela-azure

# Create a zip excluding local-only files
zip -r deploy.zip . \
  --exclude "*.pyc" \
  --exclude "__pycache__/*" \
  --exclude ".git/*" \
  --exclude "instance/*" \
  --exclude "backups/*" \
  --exclude "venv/*" \
  --exclude ".env"

az webapp deployment source config-zip \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --src deploy.zip
```

#### Option B — GitHub Actions (CI/CD)

1. In the Azure portal, go to your Web App → Deployment Center.
2. Select GitHub, authorise, choose your repo and branch.
3. Azure generates a workflow file automatically — commit it to your repo.
4. Every push to that branch auto-deploys.

### 6. Create the persistent data directory

The first deploy will create `/home/kalamela` automatically (the app calls `os.makedirs` on startup). If you need to pre-create it:

```bash
az webapp ssh --name $APP_NAME --resource-group $RESOURCE_GROUP
# inside the SSH session:
mkdir -p /home/kalamela/uploads /home/kalamela/backups
```

### 7. Verify

```bash
az webapp browse --name $APP_NAME --resource-group $RESOURCE_GROUP
```

The app will be available at `https://<APP_NAME>.azurewebsites.net`.

---

## Custom domain & HTTPS

Azure provides a free `*.azurewebsites.net` HTTPS certificate automatically. For a custom domain (e.g. `kalamela.lkc.org.uk`):

```bash
az webapp custom-hostname add \
  --webapp-name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --hostname kalamela.lkc.org.uk

az webapp managed-ssl create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --hostname kalamela.lkc.org.uk
```

---

## Backup strategy

The built-in Backup / Restore page in the app creates `.db` snapshots to `/home/kalamela/backups/`. To also download these off-server periodically, use the Download button in the Data section, or automate with:

```bash
az webapp ssh --name $APP_NAME --resource-group $RESOURCE_GROUP
# copy a backup file to your machine via scp or the Kudu console
```

Access the Kudu console at: `https://<APP_NAME>.scm.azurewebsites.net/`

---

## Changing the admin password after deployment

Log in as admin and use the **Change Password** link in the top navbar. The new hash is persisted to `/home/kalamela/admin.hash` and survives restarts.

---

## Updating the app

Re-run the ZIP deploy step (Step 5) with an updated zip. The database and uploads on `/home` are not touched by deployments.

---

## Tearing down

```bash
az group delete --name $RESOURCE_GROUP --yes
```

This deletes everything including the App Service Plan and all data. Download a backup first.
