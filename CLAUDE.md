# CLAUDE.md — Leicester Kerala Community Kalamela Management System

## Project Overview

A Python/Flask web application to manage the LKC pre-regional Kalamela (Kerala arts competition).
Handles participant registration, scheduling, score entry, results, awards, and certificate generation.
Deployed on Azure App Service with persistent SQLite on an Azure Files mount.

Reference manual: `UUKMA - Kalamela- Manual 2026.pdf`
Full architecture: `architecture.md`

---

## Tech Stack

- **Python 3.11+**, **Flask**, **SQLAlchemy**, **SQLite**
- **Jinja2** templates with **Bootstrap 5**
- **ReportLab** — PDF certificates and judge scoresheets
- **Pillow** — Social certificate PNG generation (1080×1920)
- **gunicorn** — WSGI server on Azure
- No heavy JS framework — standard page refresh + minimal inline JS

---

## Project Layout

```
kalamela-azure/
├── app/
│   ├── __init__.py          # Flask app factory + lightweight schema migrations
│   ├── models.py            # All SQLAlchemy models (single file)
│   ├── seed_data.py         # Pre-loads competition items/criteria on first run
│   ├── auth.py              # Login / logout blueprint
│   ├── routes/
│   │   ├── main.py          # Welcome page
│   │   ├── setup.py         # Event settings, stage management
│   │   ├── participants.py  # Registration (individual + group)
│   │   ├── schedule.py      # Running order, live status
│   │   ├── planning.py      # Stage planning / ordering
│   │   ├── scores.py        # Judge score entry
│   │   ├── results.py       # Results, awards, Kalathilakam/Kalaprathibha
│   │   ├── certificates.py  # PDF + social cert generation and template setup
│   │   ├── scoresheets.py   # Judge scoresheet PDFs
│   │   └── data.py          # Backup / restore / reset / export
│   ├── pdf/
│   │   ├── fonts.py         # Font scanner: get_font_choices(), resolve_pillow_font(), resolve_pdf_fonts()
│   │   ├── certificate.py   # ReportLab PDF certificate builder
│   │   ├── social_certificate.py  # Pillow PNG 1080×1920 social cert builder
│   │   ├── scoresheet.py    # ReportLab judge scoresheet builder
│   │   ├── chest_numbers.py # Chest number card PDFs
│   │   └── planning.py      # Planning schedule PDF
│   ├── templates/
│   │   ├── base.html
│   │   ├── certificates/    # index, template (PDF), social_template
│   │   └── ...              # one folder per blueprint
│   └── static/
│       ├── lkc-logo.jpeg    # Fallback logo (always present)
│       └── uploads/         # User-uploaded logos, backgrounds (local dev)
├── instance/
│   └── kalamela.db          # SQLite DB (local dev only)
├── backups/                 # Timestamped .db backup files
├── run.py                   # Dev entry point: python run.py
├── requirements.txt
├── architecture.md
└── CLAUDE.md
```

---

## Running Locally

```bash
pip install -r requirements.txt
python run.py          # http://localhost:5000
```

Default admin password: `password` (override via `ADMIN_PASSWORD` env var).

---

## Azure Deployment

Key environment variables (sourced from Key Vault):

| Variable | Purpose |
|---|---|
| `DATA_DIR` | `/home/kalamela` — persistent mount for DB + uploads |
| `SECRET_KEY` | Flask session secret |
| `ADMIN_PASSWORD` | Initial admin password hash seed |
| `DATA_RESET_PASSWORD` | Guards destructive reset/restore operations |

When `DATA_DIR` is set, the app stores the DB, uploads, backups, and `admin.hash` under that path instead of `instance/` and `static/uploads/`.

---

## Schema Migrations

There is no Alembic. New columns are added in `_apply_migrations()` in `app/__init__.py` using raw `ALTER TABLE` via SQLAlchemy `text()`. Always add a migration there when adding a model column, and set a safe default.

---

## Key Domain Rules (always enforce)

1. **Max 4 events per individual**: 3 single + 1 group, OR 2 single + 2 group.
2. **Age category** auto-assigned from DOB using September 2026 cutoffs.
3. **Thiruvathira, Oppana, Margamkali**: females only — hard restriction.
4. **Group size limits**: enforced per event (e.g. Mime 4–6, Group Song 3–10).
5. **3 judges per event**: each scores each criterion; final score = J1 + J2 + J3 (max 300).
6. **Score edits** must be logged to `AuditLog` with old value, new value, and reason.
7. **Auto-backup** must run before any data reset.
8. **Ties**: all tied participants are declared joint winners.
9. **Kalathilakam** (female) / **Kalaprathibha** (male): requires 1st in a Dance single AND a Non-Dance single (fallback rules apply).

---

## Scoring Points

| Result | Single Item | Group Item |
|---|---|---|
| 1st | 5 pts | 1 pt |
| 2nd | 3 pts | 0.5 pt |
| 3rd | 1 pt | 0.25 pt |

---

## Age Category DOB Cutoffs (September 2026)

| Category | DOB Range |
|---|---|
| Kids | 01/09/2018 or after |
| Sub-Junior | 01/09/2014 – 31/08/2018 |
| Junior | 01/09/2009 – 31/08/2014 |
| Senior | 01/09/1991 – 31/08/2009 |
| Super Senior | 31/08/1991 or before |
| Common | No restriction |

---

## Certificates

### PDF Certificate (`app/pdf/certificate.py`)
- Built with **ReportLab**
- Configurable: background image, logo, font (built-in or TTF), colours for heading/title/name/body
- Logo priority: `cert_logo` upload → `welcome_logo` → `static/lkc-logo.jpeg`

### Social Certificate (`app/pdf/social_certificate.py`)
- **Pillow** PNG, 1080×1920 px (Instagram/WhatsApp Stories format)
- Layout: logo → gold divider → position label → item name → category → thin divider → participant name → "at [Event]"
- Content blocks are pre-measured; gaps distributed evenly to fill the full canvas
- Optional footer bar (90 px, pinned to bottom); toggled via `show_footer`
- Configurable: background image, font, colours per element, overlay darkness, footer text
- Download as PNG or email via SMTP (configured in Event Settings)

### Font System (`app/pdf/fonts.py`)
- `get_font_choices()`: returns built-in ReportLab fonts + scanned system TTF fonts
- `resolve_pdf_fonts(value)`: registers TTF with ReportLab, returns (base_name, bold_name)
- `resolve_pillow_font(value, size, bold)`: returns `ImageFont` for Pillow

---

## Development Notes

- One blueprint per route module; all admin blueprints guard with `@blueprint.before_request`.
- All models in `models.py` — do not split.
- Seed data loaded once via `seed_data.py`; guard with existence check before inserting.
- Keep UI simple — this is used under event-day pressure.
- Do not add Alembic, Celery, or other heavy dependencies without a clear need.

---

## Out of Scope

- Multi-user roles (single admin only)
- Regional/National Kalamela points tally
- Complaint fee payment processing
