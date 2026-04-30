# Mobile App Integration — Action Plan

**System:** Association Kalamela Management System  
**Date authored:** April 2026  
**Status:** Planning — not yet implemented  
**Prepared by:** LKC Technical Team

---

## Background

The Kalamela Management System currently handles participant registration via public web forms. Users enter their LKC ID and email, the system verifies their LKC membership via the LKC API, and they can enrol in individual and group events.

The LKC mobile app (already in use) authenticates users via their LKC ID and email address. The goal is to allow app users to register for Kalamela events from within the app without re-entering credentials, and to manage their own registrations.

Two integration options are documented below. The recommended path is to **start with Option 1 (WebView)** to minimise mobile app changes, and **migrate to Option 2 (REST API)** when full native integration is required.

---

## Git Branching Strategy

> **All implementation work must be done on a feature branch — never directly on `main`.**

```
main                    ← stable, deployed to Azure
  └── feature/mobile-webview      ← Option 1 work
  └── feature/mobile-api          ← Option 2 work
```

Branch naming convention:
- `feature/mobile-webview` — WebView option
- `feature/mobile-api` — REST API option
- `fix/<description>` — any bug fixes during integration work

Create a branch before starting:
```bash
git checkout -b feature/mobile-webview
# or
git checkout -b feature/mobile-api
```

Merge to `main` only after testing on the branch and reviewing changes.

---

## Shared Prerequisite (Both Options)

Before starting either option, the shared authentication secret must be set up.

### API App Secret — Key Vault

A shared secret between the Kalamela server and the mobile app. Used to verify that requests genuinely come from the LKC app.

**Steps:**
1. Generate a strong secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Add it to Azure Key Vault manually (or via Terraform):
   - Secret name: `api-app-secret`
3. Add to Azure App Service app settings (`infra/azure/main.tf`):
   ```hcl
   API_APP_SECRET = "@Microsoft.KeyVault(VaultName=...;SecretName=api-app-secret)"
   ```
4. Add to `infra/azure/variables.tf` — add commented `api_app_secret` variable block
5. Share the secret value securely with the mobile app development team

**Note:** The mobile app must never expose this secret in client-side code. It should be stored in the app's secure backend or environment config.

---

## Option 1 — WebView Integration (Short-term)

### Summary

The mobile app opens the Kalamela web pages inside an embedded browser (WebView). The user's identity (LKC ID) is passed via a signed URL — the Kalamela system verifies the signature and creates a participant session automatically, so the user never sees a login form.

**Mobile app changes required: ~5–10 lines of code**
- Generate a HMAC signature from `lkc_id + timestamp + shared_secret`
- Open the signed URL in a WebView component

### How It Works

```
User opens Kalamela section in the LKC app
        │
        ▼
App constructs signed URL:
https://kalamela.lkc.org.uk/participant/entry
?lkc_id=LKC146&ts=1714435200&sig=<HMAC-SHA256>
        │
        ▼
Kalamela verifies:
  - Signature matches (shared secret)
  - Timestamp is within 5 minutes (prevents replay attacks)
  - LKC ID has an active membership (LKC API check)
        │
        ▼
Participant session cookie created
User lands on their personal registration dashboard
```

### Signed URL Format

```
GET /participant/entry?lkc_id=LKC146&ts=<unix_timestamp>&sig=<hex_digest>

sig = HMAC-SHA256(secret_key=API_APP_SECRET, message="LKC146:<timestamp>")
```

The timestamp must be within 300 seconds (5 minutes) of server time to be valid.

### What Works in WebView

| Feature | Status | Notes |
|---|---|---|
| Individual registration | ✅ Full | Pre-filled LKC ID, locked fields |
| Group registration | ✅ Full | AJAX member search works in WebView |
| View own registrations | ✅ Full | New page needed |
| Modify own event selections | ✅ Full | New edit page needed |
| Cancel own registration | ✅ Full | New cancel flow needed |
| Create / edit groups | ✅ Full | Existing pages adapted |
| Eligibility enforcement | ✅ Full | All existing rules reused |

### What WebView Cannot Accommodate

| Feature | Status | Notes |
|---|---|---|
| Native look and feel | ❌ | Looks like a browser, not native UI |
| Push notifications | ❌ | Not possible from a web page |
| Offline access | ❌ | Requires internet connection |
| Certificate save to device | ⚠️ Partial | Browser download only, not native share |
| Device camera / QR scan | ❌ | Cannot access device camera from web |
| Biometric re-auth | ❌ | e.g. Face ID before cancellation |
| App analytics integration | ❌ | Web events don't flow into app analytics |
| App back-button behaviour | ⚠️ Partial | Needs WebView back-navigation handling in app |
| Deep link to specific section | ⚠️ Partial | Possible via URL path, needs routing |
| Registration count badge | ❌ | App cannot read web page state |

---

### Implementation Phases — Option 1

**Branch:** `feature/mobile-webview`

---

#### Phase 1 — Authentication layer
*Estimated effort: 1 day*

- [ ] Add `API_APP_SECRET` to `app/__init__.py` config (read from env var)
- [ ] Add to `infra/azure/main.tf` app settings (Key Vault reference)
- [ ] Create `GET /participant/entry` route:
  - Accepts `lkc_id`, `ts`, `sig` query parameters
  - Verifies HMAC signature using `API_APP_SECRET`
  - Rejects if timestamp is older than 5 minutes
  - Calls LKC membership API to confirm active membership
  - On success: creates participant session cookie, redirects to participant home
  - On failure: shows clear error page (invalid link / expired / not a member)
- [ ] Create `@require_participant` decorator:
  - Reads participant identity from session cookie
  - Redirects to error page if no valid participant session
- [ ] Create `GET /participant/logout` — clears participant session

---

#### Phase 2 — Participant registration pages
*Estimated effort: 2–3 days*

- [ ] `GET /participant/home` — My Registrations dashboard
  - Shows: individual entries, groups, chest numbers
  - Links to: register / edit / cancel
- [ ] `GET /participant/register/individual` — Individual registration
  - LKC ID and email pre-filled from session and locked (not editable)
  - LKC membership check skipped (already verified at login)
  - DOB, gender, phone, events selection — same as public form
  - GDPR consent still required
- [ ] `GET/POST /participant/register/individual/edit` — Edit own event selections
  - Add or remove individual events
  - Eligibility rules enforced
  - Blocked if any events have scores entered
- [ ] `POST /participant/register/individual/cancel` — Cancel all own entries
  - Confirmation step required
  - Blocked if any entries have scores (show message to contact admin)
- [ ] `GET/POST /participant/groups/new` — Create group
  - Member search (AJAX — reuse existing API)
  - Logged-in user auto-added as a member option
- [ ] `GET/POST /participant/groups/<id>/edit` — Edit own group
  - Only accessible to group creator or admin
- [ ] `POST /participant/groups/<id>/cancel` — Remove own group
  - Blocked if group has scores entered

---

#### Phase 3 — Mobile UX polish
*Estimated effort: 1 day*

- [ ] Audit all participant pages for mobile responsiveness
  - Ensure touch-friendly button sizes (min 44px tap targets)
  - Test on narrow viewport (375px)
- [ ] Add `<meta name="viewport">` where missing
- [ ] Remove admin sidebar from participant-facing pages (clean, minimal layout)
- [ ] Handle WebView back-navigation:
  - Add "Back" links explicitly on all participant pages
  - Avoid relying on browser back button
- [ ] Add a dedicated participant page header / nav bar (separate from admin nav)

---

#### Phase 4 — Testing & deployment
*Estimated effort: 0.5 day*

- [ ] Test signed URL generation and verification end-to-end
- [ ] Test with expired timestamp (should reject)
- [ ] Test with tampered LKC ID (should reject)
- [ ] Test registration, edit, and cancel flows
- [ ] Merge `feature/mobile-webview` → `main` after review
- [ ] Share URL format and HMAC signing method with mobile app team

---

## Option 2 — Full REST API Integration (Long-term)

### Summary

The mobile app communicates with Kalamela via JSON REST API endpoints. The app displays native UI screens and calls the API for all data. This gives full native look and feel and supports all features, but requires significant work on both the Kalamela side and the mobile app side.

**Mobile app changes required: Significant**
- New API client / HTTP layer
- New screens: registration, groups, my-registrations
- Token storage and refresh logic
- Error handling for API responses

### How It Works

```
User opens Kalamela section in the LKC app
        │
        ▼
App calls POST /api/auth/login
  { lkc_id, email, app_secret }
        │
        ▼
Kalamela verifies app_secret + LKC membership
Returns: { token, expires_at, participant: { id, name, lkc_id, category } }
        │
        ▼
App stores token securely
All subsequent API calls include:
  Authorization: Bearer <token>
        │
        ▼
Native app screens call REST endpoints:
  GET  /api/my/registration
  POST /api/register/individual
  POST /api/groups
  etc.
```

### Token Format

Stateless signed token using `itsdangerous` (already a Flask dependency):
- Contains: `{ participant_id, lkc_id, issued_at }`
- Signed with Flask `SECRET_KEY`
- Expires after 24 hours (configurable)
- No database table required

### What REST API Adds Over WebView

| Feature | WebView | REST API |
|---|---|---|
| Native look and feel | ❌ | ✅ |
| Push notifications (registration confirmed etc.) | ❌ | ✅ |
| Offline read (cached registrations) | ❌ | ✅ |
| Certificate download to device | ❌ | ✅ |
| App analytics for registration events | ❌ | ✅ |
| Registration count badge on app icon | ❌ | ✅ |
| Biometric re-auth before cancel | ❌ | ✅ |
| Deep link to any screen | ⚠️ | ✅ |

---

### Implementation Phases — Option 2

**Branch:** `feature/mobile-api`

> Note: If Option 1 (WebView) was implemented first, the auth layer and participant ownership model from Phase 1 of that option are reused here. Start from Phase 2.

---

#### Phase 1 — Auth API
*Estimated effort: 1–2 days*

- [ ] `POST /api/auth/login`
  - Body: `{ lkc_id, email, app_secret }`
  - Validates `app_secret` against `API_APP_SECRET` config
  - Calls LKC membership API
  - Returns: `{ token, expires_at, participant }`
- [ ] `GET /api/auth/me` — returns current participant from token
- [ ] `@require_participant_token` decorator — validates Bearer token on all `/api/` routes
- [ ] CORS headers on all `/api/*` routes — allow mobile app origin
- [ ] Rate limiting on `/api/auth/login` — max 10 attempts per minute per IP

---

#### Phase 2 — Individual registration API
*Estimated effort: 2 days*

- [ ] `GET /api/events?dob=YYYY-MM-DD` — returns competition items filtered by age category
- [ ] `GET /api/my/registration` — own participant record + entered events + groups
- [ ] `POST /api/register/individual` — create participant + enrol in events
  - Same eligibility rules as web form
  - GDPR consent flag required in payload
- [ ] `PATCH /api/my/registration/events` — add/remove event entries
  - Body: `{ add: [item_id, ...], remove: [item_id, ...] }`
  - Blocks changes if affected entries have scores
- [ ] `DELETE /api/my/registration` — cancel all own entries (soft cancel)
  - Blocks if any entries have scores

---

#### Phase 3 — Group registration API
*Estimated effort: 2 days*

- [ ] `GET /api/participants/search?lkc_id=LKC101` — find registered participants
  - Returns: `{ found, candidates: [{ id, lkc_id, full_name, category, gender, chest_number }] }`
- [ ] `GET /api/my/groups` — groups the logged-in participant is a member of or created
- [ ] `POST /api/groups` — create group
  - Body: `{ group_name, item_id, member_ids: [...] }`
  - All existing eligibility checks enforced
- [ ] `PATCH /api/groups/<id>/members` — add/remove members
  - Only group creator or admin can call
  - Body: `{ add: [participant_id, ...], remove: [participant_id, ...] }`
- [ ] `DELETE /api/groups/<id>` — remove group
  - Only group creator or admin
  - Blocked if group has scores

---

#### Phase 4 — Ownership model
*Estimated effort: 1 day*

- [ ] Add `created_by_participant_id` column to `GroupEntry` model
  - Migration in `_apply_migrations()`
- [ ] Populate on group creation (web form and API)
- [ ] Enforce ownership checks on edit/delete endpoints

---

#### Phase 5 — Infrastructure & security
*Estimated effort: 0.5 day*

- [ ] CORS configuration — Flask-CORS or manual headers on `/api/*`
- [ ] Add `API_APP_SECRET` Key Vault secret and Terraform variable
- [ ] Document API contract (request/response shapes) for mobile app team
- [ ] Integration test: full flow — login → register → group → cancel

---

## Migration Path: Option 1 → Option 2

If WebView (Option 1) is built first, moving to REST API (Option 2) later is straightforward:

| Option 1 component | Reused in Option 2 |
|---|---|
| `API_APP_SECRET` Key Vault secret | ✅ Same secret, different verification method |
| Participant session / ownership model | ✅ Same identity, different transport (cookie → Bearer token) |
| `/participant/home` page | ✅ Can remain as fallback web view |
| Eligibility rule functions | ✅ Same functions called from API handlers |
| Member search AJAX endpoint | ✅ Exposed as `/api/participants/search` |

Estimated additional effort to move from Option 1 to Option 2: **3–4 days** (most groundwork already done).

---

## Open Questions (to resolve before implementation)

- [ ] **Group creation rule** — Can a user create a group without being individually registered themselves, or must they be a registered participant first?
- [ ] **Cancellation cascade** — If a participant cancels their individual registration, should they be automatically removed from groups they are in?
- [ ] **Token expiry** — Is 24 hours acceptable for session length, or would 7 days (persistent login between app sessions) be preferred?
- [ ] **Mobile app HTTP** — Confirm the mobile app can store and send an `Authorization: Bearer` header (relevant for Option 2 only).
- [ ] **CORS origin** — What is the mobile app's origin domain or bundle ID? Needed for CORS configuration in Option 2.

---

## Summary

| | Option 1 — WebView | Option 2 — REST API |
|---|---|---|
| **Mobile app effort** | ~10 lines | Significant (new screens + API client) |
| **Kalamela effort** | ~4–5 days | ~8–10 days |
| **Native UX** | ❌ | ✅ |
| **Push notifications** | ❌ | ✅ |
| **Offline support** | ❌ | ✅ |
| **Risk** | Low | Medium |
| **Recommended for** | Short-term / quick integration | Long-term / full product experience |
| **Git branch** | `feature/mobile-webview` | `feature/mobile-api` |
