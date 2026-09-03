# MLR RuleOps — Implementation Plan

AI-Assisted Regulatory Rule Change & Validation Platform.

## Philosophy

AI understands. AI proposes. Deterministic systems validate.
Authorized humans approve. Controlled services deploy. Everything is auditable.

## Architecture

```
Frontend (Vite/React) ──REST/SSE──► FastAPI
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                    PostgreSQL      Redis       Celery Worker
                    + pgvector                   (orchestration)
```

## Phases

### Phase 1 — Domain foundation
- Monorepo, Docker, PostgreSQL, Redis
- SQLAlchemy models + Alembic
- Auth/RBAC
- Rule repository, resolver, execution engine
- Seed + backend tests

### Phase 2 — Ticket → proposal
- Ticket ingestion (form, REST, webhook)
- LLM provider abstraction + deterministic fallback
- Interpretation, rule targeting, typed proposals
- Deterministic mutation engine + semantic diff

### Phase 3 — Validation & evidence
- Validators, sandbox, historical replay
- Regression, FP/FN, blast radius, risk engine

### Phase 4 — Governance
- Approval policies, deployment, rollback, audit ledger

### Phase 5 — Frontend
- Command Center, Change Intelligence Workspace
- Rule Explorer, Testing Lab, Approvals, Deployments, Audit, Analytics

### Phase 6 — Integrations & E2E
- ServiceNow/Jira adapters (NOT_CONFIGURED without credentials)
- pytest + Vitest + demo journey
- Documentation

## Demo journey (seeded ticket TKT-1001)

US Cardiovascular Disclaimer Citation Update → RULE-US-DRUGA-CV-014
→ REMOVE CIT-2020-001 / ADD CIT-2026-004 → validate → replay → risk
→ approve → deploy → smoke test → audit → rollback.

## Safety

- LLM never writes production rules
- LLM never approves deployment
- JSON DSL only (no executable rule code)
- Optimistic locking on base_rule_version_id
- SHA-256 checksums on rule versions
- Immutable audit events
