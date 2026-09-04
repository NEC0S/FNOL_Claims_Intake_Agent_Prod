-- ============================================================================
-- FNOL Claims Intake -- full schema
-- Run once in the Supabase SQL editor (Project -> SQL Editor -> New query)
-- before starting the backend. Safe to re-run (all statements are
-- idempotent via IF NOT EXISTS / ON CONFLICT).
-- ============================================================================

-- ---- Original domain tables ------------------------------------------------

create table if not exists customers (
    email text primary key,
    name text
);

create table if not exists policies (
    policy_number text primary key,
    holder_name text not null,
    holder_email text references customers(email),
    address text,
    coverage_limit numeric not null,
    deductible numeric not null,
    start_date date not null,
    end_date date not null
);

create table if not exists claims (
    claim_id text primary key,
    policy_number text references policies(policy_number),
    claimant_email text,
    incident_date date,
    location text,
    description text,
    fault_claimed text,
    damage_type text,
    damage_estimate numeric,
    payout numeric,
    status text,
    decision jsonb,
    coverage_check jsonb,
    risk_notes jsonb,
    weather_check jsonb,
    report text,
    is_duplicate boolean default false,
    superseded_by text,
    source text default 'manual',
    followup_count integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- ---- App layer: users, roles, auth -----------------------------------------

create table if not exists app_users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    password_hash text not null,
    full_name text,
    role text not null default 'checker' check (role in ('admin', 'manager', 'checker')),
    is_active boolean default true,
    created_at timestamptz default now()
);

-- ---- App layer: runtime-editable settings (SMTP / IMAP / LLM / thresholds) -

create table if not exists app_settings (
    key text primary key,
    value jsonb not null,
    updated_by text,
    updated_at timestamptz default now()
);

-- ---- App layer: per-claim audit / activity timeline ------------------------

create table if not exists claim_events (
    id bigserial primary key,
    claim_id text not null,
    event_type text not null,      -- e.g. extract, completeness_gate, followup,
                                    -- policy_checks, weather_agent, risk_agent,
                                    -- decision, adjudicator, manual_override,
                                    -- email_sent, email_received
    actor text default 'system',   -- 'system' or a manager/checker email
    payload jsonb,
    created_at timestamptz default now()
);

create index if not exists idx_claim_events_claim_id on claim_events(claim_id);
create index if not exists idx_claims_status on claims(status);
create index if not exists idx_claims_claimant_email on claims(claimant_email);

-- ---- App layer: manual reviewer decisions on escalated claims -------------

create table if not exists claim_reviews (
    id bigserial primary key,
    claim_id text not null references claims(claim_id),
    reviewer_email text not null,
    action text not null check (action in ('approve', 'reject', 'request_info', 'escalate', 'note')),
    notes text,
    created_at timestamptz default now()
);

-- ---- App layer: inbound/outbound email log ---------------------------------

create table if not exists email_log (
    id bigserial primary key,
    claim_id text,
    direction text not null check (direction in ('inbound', 'outbound')),
    from_addr text,
    to_addr text,
    subject text,
    body text,
    created_at timestamptz default now()
);

-- ---- Poller run history -----------------------------------------------------

create table if not exists poll_runs (
    id bigserial primary key,
    started_at timestamptz default now(),
    finished_at timestamptz,
    emails_seen integer default 0,
    claims_processed integer default 0,
    status text default 'running',
    error text
);
