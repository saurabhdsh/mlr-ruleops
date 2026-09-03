# MLR RuleOps

AI-Assisted Regulatory Rule Change & Validation Platform for Medical Affairs / MLR operations.

AI understands. AI proposes. Deterministic systems validate. Authorized humans approve. Controlled services deploy. Everything is auditable.

This is a working application, not a UI prototype. Tickets, rules, versions, validation, historical replay, approvals, deployment, rollback, and audit events are persisted in PostgreSQL and served through FastAPI.

## Solution overview

Operations teams receive natural-language tickets (internal form, REST, webhook, or ServiceNow/Jira when configured). The platform:

1. Interprets the request (LLM when credentials exist, otherwise an explicit local deterministic parser)
2. Resolves the target rule in a deterministic hierarchy
3. Generates a typed change proposal
4. Mutates a copy of a specific base version (never production)
5. Validates, sandboxes, replays historical MLR reviews, scores impact and risk
6. Routes for human approval
7. Deploys an immutable new `RuleVersion` and can roll back by pointer

## Architecture

```
React (Vite) ── REST + SSE ── FastAPI
                                 │
                    PostgreSQL   Redis   Celery worker
```

- **Frontend:** React, TypeScript, Vite, TanStack Query, Tailwind, Radix, Monaco, Recharts
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, JWT RBAC
- **Worker:** Celery on Redis (orchestration also runs in-process from the API for the demo path)
- **Data:** PostgreSQL (pgvector image in Docker; embeddings stored portably as JSON)

## Deterministic safety model

- LLM output is structured JSON only, validated by Pydantic
- Rules are TEXT or a JSON logic DSL — never executable code
- Mutation engine applies typed operations to a base version
- Validators, regression, risk, and approval policy are deterministic
- Deployment requires matching `base_rule_version_id` to the current production pointer (optimistic locking)
- SHA-256 checksums are stored on every rule version
- Approvals are invalidated if the proposal checksum changes

## Data model (core)

Users/roles · tickets + analysis · rule definitions/versions/scopes/dependencies · proposals/operations · validation · historical reviews/test runs · impact/risk · approvals · deployments/rollbacks · audit ledger · scientific citations · integrations

## Security

JWT local/demo auth (OIDC-ready shape), bcrypt passwords, RBAC (`ADMIN`, `MLR_ADMIN`, `MEDICAL_REVIEWER`, `REGULATORY_REVIEWER`, `BUSINESS_REQUESTER`, `AUDITOR`, `VIEWER`), CORS, security headers, ORM parameterization, secrets never returned to the client.

## Setup

```bash
cp .env.example .env
docker compose up --build
```

On backend start: `alembic upgrade head` then seed.

UI: http://localhost:5173  
API: http://localhost:8000/docs  
Health: http://localhost:8000/api/v1/health

### AWS (same EC2 as SEAL)

SEAL stays on **80 / 8080 / 3000**. MLR RuleOps publishes only **8081**.

On the instance (`52.0.130.62`):

```bash
git clone https://github.com/saurabhdsh/mlr-ruleops.git
cd mlr-ruleops
chmod +x deploy.sh
./deploy.sh
```

Then open **http://52.0.130.62:8081**. Security group must allow inbound TCP **8081**. Bedrock uses the instance IAM role (no API keys), same as SEAL.

### Mac without Docker (recommended on a laptop)

Same approach as the Biospecimen `start-local.sh` that already worked: project-local Postgres on port **54329** (avoids the system Postgres on 5432).

```bash
chmod +x start-local.sh
./start-local.sh
```

Wipe and reseed:

```bash
./start-local.sh --reset
```

Ctrl+C stops the UI, API, and local database. Claude uses **AWS Bedrock / IAM** (`aws configure`), not API keys. Default `LLM_PROVIDER=bedrock`.

### Local (without Docker)

You do **not** need Docker. On another Mac:

1. Python 3.12+, Node 20+, and `aws` CLI already working (`aws sts get-caller-identity`).
2. Database: Homebrew Postgres **or** SQLite (simplest).
3. Redis is optional. If Redis is missing, Process ticket still runs in-process.

**SQLite + AWS Bedrock (Claude via IAM, no API keys):**

```bash
cp .env.example .env
```

In `.env`:

```
DATABASE_URL=sqlite:///./ruleops.db
REDIS_URL=redis://127.0.0.1:1/0
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_PROFILE=default
BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0
```

Do not set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Bedrock uses the same credential chain as `aws_agent.py`: `~/.aws/credentials` / `aws configure`, then STS + `bedrock-runtime converse`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python -m app.db.seed && uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Command Center → Integrations should show **LLM provider bedrock ACTIVE**.

If Bedrock model access is denied, enable the model in AWS Console → Bedrock → Model access. The app then falls back to the local deterministic parser for that call.

**Homebrew Postgres/Redis (closer to Docker):**

```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis
createdb ruleops
# DATABASE_URL=postgresql+psycopg://YOURUSER@localhost:5432/ruleops
# REDIS_URL=redis://localhost:6379/0
```

Then the same `uvicorn` / `npm run dev` commands. Celery worker is optional:

```bash
cd worker && PYTHONPATH=../backend:. celery -A celery_app worker --loglevel=info
```

## Environment variables

See `.env.example`. Important:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL |
| `REDIS_URL` | Redis / Celery / pub-sub |
| `JWT_SECRET` | Signing key |
| `LLM_PROVIDER` | `openai` \| `azure_openai` \| `anthropic` \| `bedrock` \| `deterministic` |
| `AWS_REGION` / `AWS_PROFILE` / `BEDROCK_MODEL` | Bedrock via IAM/CLI (no API keys) |
| `OPENAI_*` / `AZURE_OPENAI_*` / `ANTHROPIC_*` | Remote LLM API keys (not used for Bedrock) |
| `SERVICENOW_*` / `JIRA_*` | External ticket adapters |

If `LLM_PROVIDER=bedrock`, credentials come from the AWS CLI (IAM role or `~/.aws`), not from an API key. If a Bedrock call fails, that call falls back to the deterministic parser.

If OpenAI/Anthropic keys are missing (and you are not on Bedrock), the effective provider is `deterministic` and the UI shows **Local deterministic interpretation mode**. It never pretends a remote model was called.

ServiceNow/Jira adapters remain **NOT_CONFIGURED** until credentials are supplied. The internal webhook is always available:

```bash
curl -X POST http://localhost:8000/api/v1/integrations/webhook/ticket \
  -H 'Content-Type: application/json' \
  -d '{
    "external_id": "INC001234",
    "source_system": "WEBHOOK",
    "title": "US Cardiovascular Disclaimer Citation Update",
    "description": "Update the US cardiovascular disclaimer for Drug A to include the new 2026 clinical trial citation and remove reference to the 2020 study."
  }'
```

## Seed data

Synthetic Demo Data: 50+ rules including `RULE-US-DRUGA-CV-014`, citations `CIT-2020-001` / `CIT-2026-004`, 10 tickets including **TKT-1001**, 200 historical reviews, policies, users.

Larger corpus:

```bash
python scripts/generate_demo_data.py --reviews 2000
```

## Demo credentials

| Role | Email | Password |
|---|---|---|
| ADMIN | admin@mlr-ruleops.local | ChangeMe!Admin1 |
| MLR_ADMIN | mlr.admin@mlr-ruleops.local | ChangeMe!Mlr1 |
| MEDICAL_REVIEWER | medical@mlr-ruleops.local | ChangeMe!Med1 |
| REGULATORY_REVIEWER | regulatory@mlr-ruleops.local | ChangeMe!Reg1 |
| BUSINESS_REQUESTER | requester@mlr-ruleops.local | ChangeMe!Req1 |
| AUDITOR | auditor@mlr-ruleops.local | ChangeMe!Aud1 |
| VIEWER | viewer@mlr-ruleops.local | ChangeMe!View1 |

## Demo walkthrough

1. Sign in as MLR Admin
2. Open **Tickets** → **TKT-1001** (US Cardiovascular Disclaimer Citation Update)
3. Click **Process ticket**
4. Watch workflow events: interpret → resolve `RULE-US-DRUGA-CV-014` → propose citation swap → validate → replay → risk → awaiting approval
5. Inspect before/after, blast radius, FP/FN, risk matrix
6. **Approve & Deploy**
7. Confirm a new production version and checksum
8. **Rollback to base version**
9. Refresh the browser — state remains (it is in PostgreSQL)

CLI helper: `make demo` (API must be running).

## Testing

```bash
cd backend && python -m pytest ../tests/backend -q
cd frontend && npm test -- --run
cd frontend && npm run build
```

## Rollback instructions

In Change Workspace → Deployment, or:

`POST /api/v1/deployments/{id}/rollback` with `target_version_id`, `reason`. Versions are never deleted; only the production pointer moves.
