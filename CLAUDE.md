# CLAUDE.md — Association Kalamela Management System

## Project Overview

A locally-run Python/Flask web application to manage a single-association pre-regional Kalamela (Kerala arts competition). Run by a single admin on event day at `http://localhost:5000`.

Reference manual: `UUKMA - Kalamela- Manual 2026.pdf`  
Full architecture and spec: `architecture.md`

---

## Tech Stack

- **Python 3.11+**, **Flask**, **SQLAlchemy**, **SQLite**
- **Jinja2** templates with **Bootstrap 5**
- **WeasyPrint** for PDF generation (certificates + judge score sheets)
- No external services required — fully offline

---

## Project Layout

```
kalamela/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # All SQLAlchemy models
│   ├── routes/              # One blueprint per module
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS, JS, uploaded images
│   ├── pdf/                 # PDF builders (certificate, scoresheet)
│   └── seed_data.py         # Pre-load items/criteria from manual
├── instance/
│   └── kalamela.db          # SQLite database
├── backups/                 # Timestamped backup files
├── run.py                   # Entry point: python run.py
├── requirements.txt
├── architecture.md
└── CLAUDE.md
```

---

## Running the App

```bash
cd kalamela
pip install -r requirements.txt
python run.py
```

Open `http://localhost:5000` in a browser.

---

## Key Domain Rules (always enforce)

1. **Max 4 events per individual**: 3 single + 1 group, OR 2 single + 2 group.
2. **Age category** auto-assigned from DOB using September 2026 cutoffs.
3. **Thiruvathira, Oppana, Margamkali**: females only — hard restriction.
4. **Group size limits**: enforced per event (e.g. Mime 4–6, Group Song 3–10).
5. **3 judges per event**: each scores each criterion; final score = J1 + J2 + J3 (max 300).
6. **Score edits** must be logged to AuditLog with old value, new value, and reason.
7. **Auto-backup** must run before any data reset.
8. **Ties**: all tied participants are declared joint winners.
9. **Kalathilakam** (female) / **Kalaprathibha** (male): requires 1st in a Dance single AND a Non-Dance single (fallback rules apply).

---

## Scoring Points (used for all awards)

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
| Senior | 31/08/2009 or before |
| Super Senior | 31/08/1991 or before |
| Common | No restriction |

---

## Development Notes

- Use Flask blueprints — one per module (setup, participants, schedule, scores, results, certificates, scoresheets, data).
- All models in a single `models.py`.
- Seed data (competition items and judging criteria) loaded via `seed_data.py` on first run — do not re-seed if data exists.
- PDF generation via WeasyPrint — templates in `app/templates/pdf/`.
- Certificate background image stored in `app/static/uploads/`.
- Backup files saved to `backups/` as `backup_YYYYMMDD_HHMMSS.db`.
- Admin override is available for eligibility warnings — log the override but allow it.
- Real-time score updates use standard page refresh or lightweight HTMX — no heavy JS framework.
- Keep the UI simple and fast — this is used under event-day pressure.

---

## Out of Scope

- Multi-user / authentication (single admin only)
- Regional or National Kalamela logic (association points tally not needed)
- Online/cloud deployment
- Complaint fee processing (review is tracked, no payment integration)
