# Association Kalamela Management System — Architecture

## 1. Application Overview

**Name:** Association Kalamela Management System  
**Purpose:** Manage a single-association pre-regional Kalamela (arts competition) — participant registration, event planning, scheduling, score entry, awards calculation, judge score sheets, certificate generation, and chest number printing.  
**Reference:** UUKMA Kalamela Manual 2026  

Two deployment targets:
- **Local** (`kalamela/`): run on a Mac/Windows laptop on event day at `http://localhost:5000`
- **Azure** (`kalamela-azure/`): deployed to Azure App Service, accessible publicly via HTTPS

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Web Framework | Flask 3.0 |
| Database | SQLite via Flask-SQLAlchemy / SQLAlchemy 2.0 |
| Frontend | Jinja2 templates + Bootstrap 5 + Bootstrap Icons |
| PDF Generation | ReportLab 4.2 + Pillow |
| WSGI Server | Gunicorn 22 (Azure) / Flask dev server (local) |
| Auth | Werkzeug session-based |
| Secrets (Azure) | Azure Key Vault (referenced via managed identity) |
| Infrastructure | Terraform (azurerm ~3.0) |
| Packaging | requirements.txt |

---

## 3. Project Structure

```
kalamela-azure/
├── app/
│   ├── __init__.py              # Flask app factory; DATA_DIR / SECRET_KEY env var handling
│   ├── auth.py                  # Auth blueprint + login_required decorator
│   ├── models.py                # All SQLAlchemy models
│   ├── routes/
│   │   ├── main.py              # Welcome page (/), Dashboard (/dashboard)
│   │   ├── setup.py             # Event config, stages, items (admin only)
│   │   ├── participants.py      # Registration (public + admin); LKC ID lookup API
│   │   ├── schedule.py          # Stage assignment, running order, status, chest numbers
│   │   ├── planning.py          # Event planning order per stage + printable schedule (admin)
│   │   ├── scores.py            # Score entry, cancel/restore entries (admin only)
│   │   ├── results.py           # Live results and awards (public)
│   │   ├── certificates.py      # Certificate template and generation (admin)
│   │   ├── scoresheets.py       # Judge score sheet PDF generation (admin)
│   │   └── data.py              # Backup, restore, reset, export (admin)
│   ├── templates/
│   │   ├── base.html            # Sidebar: hidden for public; full nav for admin
│   │   ├── welcome.html         # Standalone public welcome page (extends nothing)
│   │   ├── dashboard.html       # Admin dashboard
│   │   ├── auth/
│   │   ├── setup/
│   │   ├── participants/
│   │   │   ├── register_individual.html # LKC membership check; GDPR consent; auto-fill parent
│   │   │   ├── register_group.html      # LKC prefix pre-filled; eligibility API check; candidate selection
│   │   │   ├── edit_group.html          # Edit group members (admin); read-only event; same eligibility checks
│   │   │   ├── groups.html              # Group list + admin edit/delete buttons
│   │   │   ├── list.html
│   │   │   └── edit.html
│   │   ├── schedule/
│   │   │   ├── index.html
│   │   │   ├── stage.html
│   │   │   ├── print.html
│   │   │   └── chest_numbers.html       # Config + A4 preview; 2 per page
│   │   ├── planning/
│   │   │   ├── index.html               # All stages overview
│   │   │   ├── stage.html               # Per-stage reorder view
│   │   │   └── print.html               # Standalone printable schedule
│   │   ├── scores/
│   │   ├── results/
│   │   ├── certificates/
│   │   ├── scoresheets/
│   │   └── data/
│   ├── static/
│   │   └── uploads/             # Logo, certificate backgrounds (local fallback)
│   ├── pdf/
│   │   ├── certificate.py       # Certificate PDF builder
│   │   ├── scoresheet.py        # Judge score sheet PDF builder (ReportLab, landscape A4)
│   │   ├── chest_numbers.py     # Chest number cards (2 per A4, auto-sized font)
│   │   └── planning.py          # Planning schedule PDF (A4 table with category headers)
│   └── seed_data.py             # Pre-load items and criteria from manual
├── infra/
│   └── azure/
│       ├── main.tf              # Provider, resource group, app service plan, web app
│       ├── keyvault.tf          # Key Vault, secrets, role assignments
│       ├── variables.tf         # Input variables (app_name, sku, secret_key, etc.)
│       ├── outputs.tf           # app_url, kudu_url, key_vault_uri
│       ├── terraform.tfvars     # Local values (gitignored)
│       └── .gitignore           # Excludes state and tfvars
├── tests/
├── instance/                    # Local SQLite DB (gitignored)
├── backups/                     # Auto and manual backups (gitignored)
├── wsgi.py                      # Gunicorn entry point: wsgi:app
├── startup.txt                  # Azure startup command
├── run.py                       # Local entry point (port 5000)
├── requirements.txt             # Includes gunicorn
├── DEPLOYMENT.md                # Step-by-step Azure deployment guide
├── .gitignore
└── architecture.md
```

---

## 4. Environment & Configuration

### Local
All paths default to `instance/` and `app/static/uploads/`. No environment variables required.

### Azure
Set these in **Azure App Settings** (or `.env` for local testing):

| Variable | Purpose |
|---|---|
| `DATA_DIR` | `/home/kalamela` — persistent SQLite, uploads, backups on Azure Files mount |
| `SECRET_KEY` | Flask session secret — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | Initial admin password (plain text; hashed on startup) |

`DATA_DIR` controls all runtime paths:

```
/home/kalamela/
├── kalamela.db      ← SQLite database
├── admin.hash       ← persisted bcrypt hash after password change
├── uploads/         ← welcome logo, certificate background images
└── backups/         ← manual and auto backups
```

### Secrets management (Azure)
`SECRET_KEY` and `ADMIN_PASSWORD` are stored in **Azure Key Vault** and referenced by the App Service via a system-assigned managed identity. App settings use Key Vault reference syntax:
```
@Microsoft.KeyVault(VaultName=<vault>;SecretName=<name>)
```

---

## 5. Database Models

### EventConfig *(single row)*

| Field | Type | Notes |
|---|---|---|
| event_name | String | e.g. "LKC Kalamela 2026" |
| event_date | Date | |
| venue | String | |
| welcome_logo | String | Filename in uploads folder |
| welcome_tagline | String | Shown below event name on welcome page |
| cert_bg_image | String | Certificate background image filename |
| cert_title_text | String | Default: "Certificate of Achievement" |
| cert_font | String | Default: "Helvetica" |
| cert_font_size | Integer | Default: 24 |
| cert_font_colour | String | Hex colour, default: "#000000" |
| cert_body_text | Text | Template with `{name}`, `{position}`, `{item}`, etc. |
| scoresheet_blank_rows | Integer | Extra blank rows for late entries, default: 3 |
| default_num_judges | Integer | Default: 3; overridable per item |

---

### Stage

| Field | Type | Notes |
|---|---|---|
| name | String | e.g. "Stage A" |
| display_order | Integer | |

---

### StagePlanItem *(new)*
Stores the organiser-defined ordering of competition items within a stage for planning purposes.

| Field | Type | Notes |
|---|---|---|
| stage_id | FK → Stage | |
| item_id | FK → CompetitionItem | |
| display_order | Integer | |
| *unique constraint* | (stage_id, item_id) | |

Auto-synced when the planning page is loaded: all CompetitionItems assigned to the stage are synced (not just those with entries); items removed from the stage assignment are deleted. Items can also be manually removed/restored from the planning UI.

---

### CompetitionItem

| Field | Type | Notes |
|---|---|---|
| name | String | |
| category | String | Kids / Sub-Junior / Junior / Senior / Super Senior / Common |
| item_type | String | solo / group |
| max_duration_mins | Integer | |
| min_members | Integer | Null for solo |
| max_members | Integer | Null for solo |
| gender_restriction | String | None / Female |
| is_custom | Boolean | True if admin-added |
| num_judges | Integer | 0 = use EventConfig.default_num_judges; 1–3 = item override |

---

### Criteria

| Field | Type | Notes |
|---|---|---|
| item_id | FK → CompetitionItem | |
| name | String | e.g. "Costume and visual appeal" |
| max_marks | Integer | |
| display_order | Integer | |

---

### Participant

| Field | Type | Notes |
|---|---|---|
| chest_number | Integer | Auto-assigned, unique, sequential from 101 |
| full_name | String | |
| date_of_birth | Date | |
| category | String | Derived from DOB via `derive_category()` |
| lkc_id | String | Format: `LKC###` or `LKC####` |
| gender | String | Male / Female |
| phone | String | Format: `07XXXXXXXXX` (11 digits) |
| email | String | Optional |
| parent_name | String | Optional |

---

### GroupEntry

| Field | Type | Notes |
|---|---|---|
| group_name | String | |
| item_id | FK → CompetitionItem | |
| chest_number | Integer | Auto-assigned, shared pool with Participant |

### group_members *(association table)*
`group_id` ↔ `participant_id`

---

### Entry
One competitor (individual or group) in one event.

| Field | Type | Notes |
|---|---|---|
| participant_id | FK → Participant | Null if group |
| group_id | FK → GroupEntry | Null if individual |
| item_id | FK → CompetitionItem | |
| stage_id | FK → Stage | Null until assigned |
| running_order | Integer | Order within stage |
| status | String | waiting / performing / completed |
| is_cancelled | Boolean | Default False; withdrawn entries excluded from scoring and results |

Key computed properties:
- `display_name` — participant full name or group name
- `chest_number` — from participant or group entry
- `active_judges` — set of judge numbers with any saved score
- `final_score` — sum of all Score.marks
- `scores_complete()` — True when all active judges have scores for all criteria

---

### Score

| Field | Type | Notes |
|---|---|---|
| entry_id | FK → Entry | |
| judge_number | Integer | 1 / 2 / 3 |
| criteria_id | FK → Criteria | |
| marks | Float | |
| *unique constraint* | (entry_id, judge_number, criteria_id) | |

---

### AuditLog

| Field | Type | Notes |
|---|---|---|
| timestamp | DateTime | |
| entry_id | FK → Entry | |
| judge_number | Integer | |
| criteria_id | FK → Criteria | |
| old_value | Float | |
| new_value | Float | |
| reason | String | Optional |

---

## 6. Modules

### 6.1 Welcome Page & Dashboard

**Welcome page** (`/`) — public, standalone (does not extend `base.html`):
- Full-screen dark gradient layout
- Event logo (uploaded via Event Settings), event name, date, venue, tagline
- Two large buttons: Register Individual / Register Group
- Admin bar: Dashboard + Logout shown only when logged in; no Admin button shown to public
- `/admin` route: redirects to login page (or dashboard if already logged in)

**Dashboard** (`/dashboard`) — admin only:
- Counts: participants, entries, scored, pending, stages, items

**Event Settings** (admin) — extends welcome page config:
- Upload/remove `welcome_logo` (PNG/JPG/SVG/WebP, saved to uploads)
- Set `welcome_tagline`
- Set default judges count, blank scoresheet rows

---

### 6.2 Participant Registration

**Individual** (`/participants/register`) — 3-step wizard:

**Step 1 — Verify LKC Membership:**
- LKC ID (`LKC###` or `LKC####`, pre-filled with `LKC`) + email address
- "Verify" button triggers AJAX POST to `/participants/api/verify-membership`; also fires on email blur
- Step 2 is hidden until membership passes; editing LKC ID or email re-hides Step 2
- `status: 'error'` (API unavailable) is treated as a soft pass

**Step 2 — Participant Details** (revealed after verification):
- Participant Name, DOB, Gender, Phone, Parent/Guardian
- DOB: `type="date"`, `min=1900-01-01`, `max=today`; resolves category via API
- Phone: `07XXXXXXXXX` format, pre-filled with `07`
- **Parent/Guardian auto-fill**: if membership returns `holder_name` and category is Kids/Sub-Junior/Junior, field is auto-filled (only if blank)
- "Next: Choose Events" validates all required fields before advancing to Step 3

**Step 3 — Enrol in Events** (revealed after DOB resolves a category):
- Shows only events eligible for the resolved age category
- Hard-block on event count: (≤ 3 solo + ≤ 1 group) or (≤ 2 solo + ≤ 2 group), total ≤ 4
- Hard-block on eligibility (gender restrictions, category mismatch)
- **GDPR consent checkbox** (required): links to LKC GDPR Policy
- Cancel button on all 3 steps returns to welcome page
- On server validation error, form re-displays at Step 3 with all data restored

**Group** (`/participants/groups/register`):
- LKC ID lookup field pre-filled with `LKC`; cursor positioned after prefix on focus
- **Duplicate group name check**: case-insensitive; if name already exists, hard error — "this group is already registered, please contact LKC kalamela co-ordinator to modify the group"
- Member eligibility checked via API *at the time of adding* (before form submit):
  1. Participant's category must match the selected event's category (or event is Common; Super Senior may enter Senior events unless a Super Senior variant exists)
  2. Participant must have an individual `Entry` for this group event
  3. Participant must not already be a member of another group for the same event — **one group per event per participant**
- **Multiple participants per LKC ID**: if lookup returns >1 match, a candidate selection panel appears; already-added members and members in another group for this event are excluded from the list; if exactly 1 match, adds directly
- **Ineligible candidates**: shown in candidate panel with issues listed; Select button is disabled — cannot be added
- **Participants in another group for same event**: excluded entirely from lookup results; if all matches for an LKC ID are in other groups, a warning is shown instead
- **Ineligible error message** includes list of group events the participant *can* be added to (cross-referenced via `_eligible_group_items_for()` helper)
- **Not found message**: "No participant found with LKC ID '…'. Please use the Register Individual form before adding them to a group."
- **Member list** shows chest number, LKC ID, full name, category, gender; ineligible members shown with amber warning badge and issue list
- **Re-validation on event change**: when the selected event is changed after members have been added, all existing members are re-validated against the new event via `/api/participant-by-id`; ineligible members are flagged but not removed
- All eligibility checks enforced server-side on POST — **hard block, no admin override**
- After successful registration, stays on group registration page (success flash shown); admin can immediately register another group
- No GDPR section (GDPR consent is only on individual registration)

**Group list** (`/participants/groups`) — admin only:
- Edit (pencil) button links to edit_group page

**Group edit** (`/participants/groups/<id>/edit`) — admin only:
- Pre-populated with existing members; event is **read-only** (cannot be changed)
- Admins can add or remove members; same eligibility checks as registration
- Hard block on eligibility — no override option
- No GDPR section

---

### 6.3 Participant Lookup API

**`GET /participants/api/by-lkc-id?id=LKC101[&item_id=N]`**

Single match returns:
```json
{
  "found": true, "id": 1, "lkc_id": "LKC101",
  "full_name": "...", "category": "Junior", "gender": "Female",
  "chest_number": 101, "eligible": true, "eligibility_issues": []
}
```

Multiple participants share the same LKC ID — returns candidate list:
```json
{
  "found": true, "multiple": true,
  "candidates": [
    {"lkc_id": "LKC101", "full_name": "...", "eligible": true, ...},
    {"lkc_id": "LKC101", "full_name": "...", "eligible": false,
     "eligibility_issues": [...], "eligible_group_items": [...]}
  ]
}
```

When `eligible: false`, the response includes:
```json
{
  "eligibility_issues": [
    "Category mismatch: participant is Kids, this event is for Junior.",
    "Not individually registered for \"Group Song\".",
    "Already a member of group \"Team A\" for \"Group Song\". A participant can only be in one group per event."
  ],
  "eligible_group_items": [
    {"id": 5, "name": "Group Song", "category": "Kids"}
  ]
}
```
`eligible_group_items` lists group events the participant is individually registered for AND category-eligible to enter (computed by `_eligible_group_items_for()` helper).

**One-group-per-event rule**: participants already in another `GroupEntry` for the same `item_id` are assigned `in_other_group: true` and filtered out of the returned candidates entirely. If all candidates for an LKC ID are in other groups, the API returns `{"found": false, "in_other_group": true}`.

---

**`GET /participants/api/participant-by-id?id=<db_id>[&item_id=N]`**

Lookup by database participant ID; same response shape as `by-lkc-id` single match.  
Used by the group registration form to re-validate already-added members when the selected event changes.

---

**`POST /participants/api/verify-membership`**  
Body: `{"lkc_id": "LKC101", "email": "user@example.com"}`

Server-side proxy to the LKC membership API (bypasses Cloudflare by sending `User-Agent: Mozilla/5.0`).

Response:
```json
{
  "status": "active",       // or "inactive" or "error"
  "message": "Active member: Ramesh Babu",
  "holder_name": "Ramesh Babu",   // present when status=active
  "join_url": "https://..."        // present when status=inactive
}
```

---

### 6.4 Event Planning (`/planning`)

New section that sits *above* the Schedule in the workflow — organise the order of competition events per stage before the day.

| Route | Description |
|---|---|
| `GET /planning/` | All stages overview with item/participant counts |
| `GET /planning/stage/<id>` | Per-stage event order with ↑/↓ reorder buttons |
| `POST /planning/stage/<id>/reorder` | Move item up or down |
| `POST /planning/stage/<id>/sort-by-category` | Reset to standard category order |
| `GET /planning/stage/<id>/print` | Standalone printable HTML schedule |
| `GET /planning/stage/<id>/pdf` | ReportLab PDF download |

**Auto-sync**: on every planning page visit, `StagePlanItem` rows are synced with entries — newly assigned items are appended, removed items are deleted.

**Standard category order**: Kids → Sub-Junior → Junior → Senior → Super Senior → Common

**Print / PDF output** shows:
- Event name, date, stage name header
- Items in planned order; category divider row when category changes
- Each row: sequence #, event name, category, participant list (chest # + name)
- Summary: total events, total participants, print timestamp

---

### 6.5 Schedule & Stage Management

| Route | Description |
|---|---|
| `GET /schedule/` | All stages overview + unassigned entries |
| `POST /schedule/assign` | Assign entry to a stage |
| `GET /schedule/stage/<id>` | Live running order view with status |
| `POST /schedule/entry/<id>/status` | Update status: waiting / performing / completed |
| `POST /schedule/entry/<id>/reorder` | Move entry up/down within stage |
| `GET /schedule/print` | Printable schedule (optional category filter) |
| `GET /schedule/chest-numbers` | Chest number print config + A4 preview |
| `GET /schedule/chest-numbers/pdf` | ReportLab PDF of chest number cards |

---

### 6.6 Chest Number Printing

Config options:
- **Registered participants** (toggle): all individual + group chest numbers with names
- **Extra range** (`from` / `to`): unregistered numbers for blank cards

PDF (`app/pdf/chest_numbers.py`):
- A4 portrait, 2 cards per page
- Font auto-sized to fill card width (220pt max → scales down for 4-digit numbers)
- Dashed cut line between the two cards on each page
- Registered numbers: dark navy; unregistered extras: grey

---

### 6.7 Score Entry

- Progress summary on index: scored / pending per event; progress bar; All done / In progress / Not started badge
- Per-event entries page: scored / pending / withdrawn counts + progress bar
- **Entry cancellation**: admin can mark any entry as withdrawn (`is_cancelled = True`); withdrawn entries excluded from results and scoring; can be restored
- **Client-side zero validation** on submit:
  - Hard block if all criteria for an active judge are 0
  - Soft `confirm()` if any single criterion is 0

---

### 6.8 Score Review & Audit
- Full score grid for any event (all entries, all judges, all criteria)
- Edit marks with mandatory reason; change written to AuditLog

---

### 6.9 Results & Awards
- Cancelled entries excluded from ranking
- Live leaderboard, event results (1st/2nd/3rd)
- Special awards: Kalathilakam, Kalaprathibha, Malayalam Bhasha Kesari

---

### 6.10 Judge Score Sheets (PDF)
- ReportLab, landscape A4, 3 copies per event
- Per-judge header: name blank, signature blank, max marks, sheet number
- Score table with entries pre-filled; blank rows for late entries

---

### 6.11 PDF Certificates
- Template: upload background, configure font/size/colour/position
- Auto-populated fields: participant name, event, category, position, date

---

### 6.12 Data Management
| Feature | Detail |
|---|---|
| Backup | Manual; auto-triggered before reset/restore; saved with timestamp |
| Restore | Upload `.db` file; auto-backup first |
| Reset | Wipes participants/entries/scores; preserves config, stages, items |
| Export | CSV or JSON |

---

## 7. Schema Migrations

`_apply_migrations()` in `__init__.py` runs on every startup and applies lightweight `ALTER TABLE` migrations for columns added after the initial schema. Current migrations:

| Table | Column added |
|---|---|
| `competition_item` | `num_judges` |
| `event_config` | `default_num_judges` |
| `event_config` | `welcome_logo` |
| `event_config` | `welcome_tagline` |
| `entry` | `is_cancelled` |

New tables (e.g. `stage_plan_item`) are created automatically by `db.create_all()`.

---

## 8. Navigation / Sitemap

`[P]` = public, `[A]` = admin login required

```
[P] /                          Welcome Page (logo, event info, registration buttons)
[P] /admin                     Redirects to login (or dashboard if already logged in)
[A] /dashboard                 Admin dashboard (stats)

[P] Participants
│   ├── [A]  /participants/              Individual list + search
│   ├── [A]  /participants/groups        Group list
│   ├── [P]  /participants/register      Register individual (3-step wizard)
│   ├── [P]  /participants/groups/register  Register group
│   ├── [A]  /participants/<id>/edit     Edit individual
│   ├── [A]  /participants/groups/<id>/edit  Edit group
│   └── [A]  Delete (individual + group)

[A] Setup
│   ├── /setup/                Event settings (name, date, venue, logo, judges)
│   ├── /setup/stages          Manage stages + assign items
│   └── /setup/items           Manage competition items + criteria

[A] On the Day
│   ├── /planning/             Event Planning (order events per stage, print/PDF)
│   ├── /schedule/             Schedule (running order, live status)
│   ├── /scores/               Score Entry (with cancellation support)
│   └── /results/              Results & Awards (public read)

[A] Print
│   ├── /schedule/chest-numbers   Chest number cards (HTML preview + PDF)
│   ├── /scoresheets/             Judge score sheets (PDF)
│   └── /certificates/            Certificates (PDF)

[A] Data
│   └── /data/                 Backup / Restore / Reset / Export
```

---

## 9. Authentication & Access Control

### Password storage
- Hashed with `pbkdf2:sha256` via Werkzeug
- Initial hash from `ADMIN_PASSWORD` env var (default: `password`)
- After admin changes password via UI: new hash persisted to `admin.hash` file in `DATA_DIR` (or `instance/` locally), loaded on next startup

### Session
- `session['admin_logged_in'] = True` on login
- Logout redirects to welcome page (`/`)
- All admin blueprints (`setup`, `schedule`, `planning`, `scores`, `results`, `scoresheets`, `data`, `certificates`) use `@blueprint.before_request` guard
- Individual admin routes in `participants` blueprint use `@login_required` decorator
- `is_admin` context variable injected into all templates via `inject_auth` context processor
- Admin Login button not shown on public pages; admin accesses via `/admin`

### Azure Key Vault
- `SECRET_KEY` and `ADMIN_PASSWORD` stored in Key Vault
- Web App identity assigned `Key Vault Secrets User` role
- Deployer identity assigned `Key Vault Secrets Officer` role (to write secrets via Terraform)

---

## 10. Validation Rules

### Individual registration (hard blocks, no override)
| Check | Rule |
|---|---|
| DOB | Valid date, year ≥ 1900, not in the future |
| Phone | `07XXXXXXXXX` — 11 digits, starts with `07` |
| LKC ID | Regex `LKC\d{3,4}` |
| LKC Membership | AJAX check on LKC ID + email; inactive membership blocks submit; API error is soft pass |
| GDPR consent | Checkbox must be ticked |
| Event count | (≤ 3 solo + ≤ 1 group) or (≤ 2 solo + ≤ 2 group), total ≤ 4 |
| Eligibility | Category match, gender restriction |

### Group registration (hard block, no admin override)
| Check | Rule |
|---|---|
| Duplicate name | Group name must be unique (case-insensitive); hard error with contact message |
| Member count | Between `min_members` and `max_members` |
| Gender | Female-only events reject male members |
| Category | Each member's category must match the event's category (unless Common); Super Senior may enter Senior events unless a Super Senior variant of the same event exists |
| Individual registration | Each member must have an individual `Entry` for this group event |
| One group per event | A participant can only be a member of one group per event; blocked at API lookup and POST |

### Custom item management (admin)
- Adding or editing a competition item checks for duplicate `name + category`; hard error shown, form data preserved

---

## 11. Age Category Cutoffs (September 2026)

| Category | DOB Range |
|---|---|
| Kids | 01/09/2018 or after |
| Sub-Junior | 01/09/2014 – 31/08/2018 |
| Junior | 01/09/2009 – 31/08/2014 |
| Senior | 01/09/1991 – 31/08/2009 |
| Super Senior | 31/08/1991 or before |
| Common | No restriction |

---

## 12. Scoring & Awards

**Score structure:** 3 judges × N criteria per judge; max per criterion defined in `Criteria.max_marks`; final = sum of all judges' all criteria marks.

**Points for awards:**

| Result | Solo | Group |
|---|---|---|
| 1st | 5 pts | 1 pt |
| 2nd | 3 pts | 0.5 pt |
| 3rd | 1 pt | 0.25 pt |

**Special awards:**

| Award | Criteria |
|---|---|
| Individual Champion (per category) | Highest solo points; group points as tiebreaker |
| Kalathilakam (female) | 1st in a Dance solo AND 1st in a Non-Dance solo; fallback to 1st in either |
| Kalaprathibha (male) | Same as Kalathilakam |
| Malayalam Bhasha Kesari | Most points across Elocution (Mal), Poem Recitation, Monoact, Story Telling |

---

## 13. Azure Infrastructure

Managed by Terraform in `infra/azure/`.

| Resource | Details |
|---|---|
| Resource Group | `kalamela-rg`, region `uksouth` |
| App Service Plan | Linux, configurable SKU (default `B1`; use `S1` if Basic quota blocked) |
| Web App | Python 3.11, system-assigned managed identity, `https_only = true`, `always_on = true` |
| Key Vault | Standard SKU, RBAC auth, 7-day soft delete |
| KV Secrets | `flask-secret-key`, `admin-password` |
| Role assignments | Deployer → `Key Vault Secrets Officer`; Web App → `Key Vault Secrets User` |

**Deployment (ZIP deploy):**
```bash
cd infra/azure && terraform init && terraform apply
# then from repo root:
zip -r deploy.zip . --exclude "*.pyc" --exclude "__pycache__/*" \
  --exclude ".git/*" --exclude "instance/*" --exclude "venv/*"
az webapp deployment source config-zip \
  --name <app_name> --resource-group kalamela-rg --src deploy.zip
```

See `DEPLOYMENT.md` for full step-by-step instructions including custom domain, CI/CD, and cost breakdown.
