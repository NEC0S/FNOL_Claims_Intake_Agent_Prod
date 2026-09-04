# FNOL Claims Intake — Operations Console

A production app built around your original LangGraph multi-agent claims
pipeline (extraction → completeness gate → follow-up → policy checks →
weather cross-check → fraud-language risk → decision → adjudicator report).
Same agent logic and prompts as the notebook, wrapped in:

- **FastAPI backend** with JWT auth (admin / manager / checker roles),
  Supabase (Postgres) persistence, IMAP polling control, and a read-only
  SQL query tool.
- **React frontend** (manager + checker console): dashboard, claims list &
  detail, manual claim submission, policy management, inbox poller
  controls, a SQL query page, and a Settings page for API keys / SMTP /
  IMAP — editable at runtime, no redeploy needed.
- **Docker** for both services, ready for `docker-compose` locally or
  Render in production.

## 1. Feature list

- Multi-agent pipeline: identical logic to the notebook (extraction,
  completeness gate, automated follow-up emails with a retry cap, policy
  lookup, coverage-window check, duplicate/prior-claim detection, weather
  cross-check via Open-Meteo, LLM fraud-language risk scoring, hardcoded
  decision thresholds, LLM-written adjudicator report).
- **Runtime-editable Settings page**: enter your own Google/LLM API key,
  SMTP credentials, and IMAP credentials from the UI. Anything left blank
  falls back to the backend's `.env` values automatically — no code
  changes or redeploys needed either way. Secrets are encrypted at rest.
- **Manager dashboard**: three buckets (waiting on customer / escalated to
  you / auto-approved) plus charts (claims by status, by damage type,
  total approved payout, duplicate count).
- **Claims list & detail**: search/filter, full automated-check breakdown
  (coverage window, weather match, risk score), decision reasons,
  adjudicator report, per-claim activity timeline (every agent step is
  logged), email log, manual review actions (approve / reject / request
  info / escalate / note), inline field editing, and a "resume with reply"
  box to manually feed in a follow-up email and re-run the pipeline.
- **New claim** page: paste any free-text claim report and it runs through
  the same extraction pipeline as an inbound email.
- **Policies** page: onboard/edit policyholder records (coverage limit,
  deductible, active window) that the pipeline checks claims against.
- **Inbox poller**: start/stop background IMAP polling, trigger a poll
  immediately, see run history. Runs entirely server-side (APScheduler),
  so it keeps working even with the browser closed.
- **Query database** page: a locked-down SQL editor (SELECT / WITH only —
  everything else is rejected before it reaches Postgres) with example
  queries, a table browser, and CSV export.
- **Users** page (admin only): create manager/checker/admin accounts,
  change roles, activate/deactivate.

## 2. One-time setup

### 2.1 Supabase project

1. Create a project at [supabase.com](https://supabase.com).
2. Go to **Project Settings → API** and copy the **Project URL** and the
   **service_role key** (not the anon key — the backend needs to bypass
   row-level security to do its job).
3. Go to **Project Settings → Database → Connection string → URI** and
   copy it. This becomes `DATABASE_URL` and powers the SQL query tool and
   automatic schema setup.
4. Either let the backend apply the schema automatically on first boot
   (it will, if `DATABASE_URL` is set), or run
   `backend/app/schema.sql` yourself once in the Supabase SQL editor.

### 2.2 Backend environment

```
cp backend/.env.example backend/.env
```

Fill in `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`, a `JWT_SECRET`, an
`ADMIN_EMAIL` / `ADMIN_PASSWORD` (the bootstrap manager account — change
the password after first login), and a `SETTINGS_ENCRYPTION_KEY`
(generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

Everything else in `.env.example` (LLM/Google API key, SMTP, IMAP,
thresholds) is **optional** — leave it blank and configure it later from
the Settings page in the app, or fill it in now as a fallback. Either
way works; whichever is set in the UI always wins.

## 3. Run locally with Docker Compose

```
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:8080

Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `backend/.env`, then
create manager/checker accounts under **Users**, and enter your API keys
under **Settings** if you didn't put them in `.env`.

## 4. Run locally without Docker (dev mode)

```
# backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000/api
npm install
npm run dev
```

## 5. Deploy to Render

**Option A — Blueprint (recommended):** push this repo to GitHub, then in
Render click **New → Blueprint** and point it at the repo. `render.yaml`
defines both services. You'll be prompted for the secret env vars
(`SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD`, etc).

After the backend's first deploy, copy its public URL
(`https://fnol-backend-xxxx.onrender.com`) into the frontend service's
`BACKEND_URL` env var, then redeploy the frontend so nginx proxies `/api`
to the right place.

**Option B — Manual:** create two **Web Services**, both "Docker" runtime:

- `fnol-backend` → root `backend/`, uses `backend/Dockerfile`. Set the env
  vars from `backend/.env.example`.
- `fnol-frontend` → root `frontend/`, uses `frontend/Dockerfile`. Set
  `BACKEND_URL` to the backend service's public URL.

Both Dockerfiles respect Render's `$PORT` automatically.

## 6. Architecture notes

```
backend/
  app/
    main.py              FastAPI app, router wiring, startup (schema + admin bootstrap)
    config.py             Env bootstrap (Supabase creds, JWT secret) — everything else is a fallback
    auth.py                JWT auth, password hashing, role guards
    database.py            Supabase client + direct Postgres pool (for the SQL tool)
    db_ops.py               Claim/policy CRUD, event logging
    email_utils.py           SMTP send + IMAP fetch (dynamic settings, test-connection helpers)
    llm.py                    OpenAI-compatible client wrapper (dynamic settings)
    weather.py                 Open-Meteo cross-check
    schema.sql                  Full DB schema (original + app tables)
    graph/
      state.py                   Shared LangGraph state
      nodes.py                    All seven pipeline nodes (same logic as the notebook)
      graph_builder.py             LangGraph wiring + mermaid export
      orchestration.py              process_claim / resume_claim / dashboard queries
    services/
      settings_service.py          DB-backed settings, encrypted, env-fallback
      inbox_service.py              IMAP correlation logic (reply matching, relevance filter)
      poller_service.py              Background polling control (APScheduler)
    routers/                         One file per API area (auth, claims, dashboard, settings, sql, poller, policies, misc)

frontend/
  src/
    api/client.js            Axios instance, JWT header injection, 401 handling
    context/AuthContext.jsx   Login/logout/current-user state
    components/               Layout (sidebar nav), StatusBadge
    pages/                     One file per screen
```

## 7. Security notes

- The SQL query tool only accepts `SELECT`/`WITH` statements, blocks a
  keyword denylist (INSERT/UPDATE/DELETE/DROP/ALTER/...), rejects
  multiple statements, wraps every query with a defensive `LIMIT`, and
  runs it inside a read-only transaction with a 10-second timeout. It's
  still direct database access — restrict it to manager/admin roles (done
  by default) and treat it like any other production DB console.
- Secrets entered on the Settings page (API keys, SMTP/IMAP passwords)
  are encrypted at rest with Fernet before being stored in
  `app_settings`. Set `SETTINGS_ENCRYPTION_KEY` explicitly in production
  so a restart doesn't invalidate them.
- Change `ADMIN_PASSWORD` immediately after first login.
- Use an **app password**, not your real mailbox password, for SMTP/IMAP
  (Gmail: Google Account → Security → App passwords).
