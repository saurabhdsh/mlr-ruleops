Subject: MLR RuleOps is live — please try the AI-assisted Medical Affairs rule-change demo

Hi,

MLR RuleOps is now available for you to use. It is a working application (not a slide-ware prototype) for AI-assisted regulatory rule change and validation in Medical Affairs / MLR operations.

The design is simple: AI understands the request and proposes a change. Deterministic systems validate it. Authorized humans approve it. Controlled services deploy it. Everything is auditable.

Please use the hosted demo below. Data is synthetic. Demo logins are included.

---

HOW TO ACCESS

URL: http://52.0.130.62:8081

Use Chrome or Safari. No VPN, VPN client, or install is required. Open the link, sign in, and you are in.

Recommended login (full access to run the demo end to end):

Role: MLR Admin
Email: mlr.admin@mlr-ruleops.local
Password: ChangeMe!Mlr1
Name in app: Priya Shah

Other demo accounts if you want to see role differences:

Admin — admin@mlr-ruleops.local / ChangeMe!Admin1
Medical Reviewer — medical@mlr-ruleops.local / ChangeMe!Med1
Regulatory Reviewer — regulatory@mlr-ruleops.local / ChangeMe!Reg1
Business Requester — requester@mlr-ruleops.local / ChangeMe!Req1
Auditor — auditor@mlr-ruleops.local / ChangeMe!Aud1
Viewer — viewer@mlr-ruleops.local / ChangeMe!View1

These passwords are for the demo environment only.

Code (public): https://github.com/saurabhdsh/mlr-ruleops

---

WHAT TO DO IN 5–10 MINUTES (recommended path)

1. Sign in as MLR Admin (credentials above).
2. You land on Command Center — live counts from the database (open tickets, processing, awaiting approval, high risk, rules in production, deployments, regression pass rate).
3. Open Tickets and find TKT-1001 — “US Cardiovascular Disclaimer Citation Update”.
   Ticket wording: Update the US cardiovascular disclaimer for Drug A to include the new 2026 clinical trial citation and remove reference to the 2020 study.
4. Open Change Workspace (or click through from the ticket). Confirm TKT-1001 is selected in the header.
5. Click Process ticket. A live overlay shows each pipeline stage as it actually runs (interpretation → rule resolution → proposal → validation → testing → impact → risk → approval routing). This is not a fake timer; it is streamed from the server.
6. Walk the workspace tabs:
   - Interpretation — what AI understood from the ticket
   - Rule Resolution — target rule RULE-US-DRUGA-CV-014 in the hierarchy (Universal / Market / Brand / Market-Brand / Scientific Accuracy)
   - Proposed Change — swap citation CIT-2020-001 → CIT-2026-004 (typed operations, not free-text overwrite of production)
   - Validation / Testing / Impact / Risk — deterministic checks, sandbox, historical MLR replay, blast radius
7. Go to Approvals, approve TKT-1001 (optionally approve and deploy).
8. Open Deployments — confirm the new immutable rule version is in production.
9. Open Audit & Governance — every step is on the ledger.
10. Optional: use Rollback on the deployment to restore the previous production pointer. Versions are never deleted.

You can process other seeded tickets the same way (TKT-1002 through TKT-1010 cover UK routing, DE/JP/FR/CA/AU/ES/IT disclosure updates, and universal claim language).

---

WHAT YOU WILL SEE IN THE MENU

- Command Center — operational posture
- Tickets — intake queue
- Change Workspace — the end-to-end change intelligence workspace
- Rule Explorer — catalog, hierarchy, inheritance
- Testing Lab — sandbox / regression
- Approvals — human-in-the-loop
- Deployments — promote and rollback
- Rule Versions — immutable version history
- Audit & Governance — ledger
- Analytics — workflow and risk distribution
- Administration — users, roles, integrations

Integrations: ServiceNow and Jira adapters exist in the product. They show NOT_CONFIGURED until credentials are supplied. Redis/Postgres are live in this environment.

---

WHAT WE HAVE BUILT

This is a full-stack MLR rule-operations platform:

1. Ticket intake — natural-language requests (internal form, REST, webhook; ServiceNow/Jira when configured).
2. AI interpretation — Claude on AWS Bedrock (same IAM pattern as SEAL). Output is structured JSON only, validated before anything is applied. If the model is unavailable, a deterministic parser still runs so the demo never silently “fakes” a result.
3. Deterministic rule targeting — hierarchy resolver finds the correct rule (hero demo: RULE-US-DRUGA-CV-014).
4. Typed change proposals — mutate a copy of a specific base version. Production is never edited in place.
5. Validation and evidence — citation/year validators, sandbox execution, historical review replay (~200 seeded MLR reviews), regression, false-positive/false-negative style checks, impact and risk scoring.
6. Human approval — policy-based routing. AI cannot approve or deploy.
7. Controlled deploy and rollback — new immutable RuleVersion, SHA-256 checksums, optimistic locking so a stale base cannot overwrite a newer production pointer. Rollback moves the production pointer; history remains.
8. Audit — every material action is written to an immutable ledger.
9. Security — JWT + RBAC (Admin, MLR Admin, Medical Reviewer, Regulatory Reviewer, Business Requester, Auditor, Viewer). Secrets are not returned to the browser.

Architecture (short): React UI → FastAPI → PostgreSQL. Redis/Celery for background work; the API can also run the pipeline in-process. Hosted on the same AWS EC2 as SEAL, on port 8081 so the two products do not collide (SEAL remains at http://52.0.130.62:3000).

Safety constraints we enforced on purpose:
- LLM never writes production rules
- LLM never approves deployment
- Rules are TEXT or a JSON logic DSL — never executable code
- Approvals are invalidated if the proposal checksum changes after review

---

WHAT THIS IS / IS NOT

This is a working demo environment with synthetic brands, tickets, citations, and users, intended for leadership walkthrough and Medical Affairs DT discussion.

This is not a production GSK Brand Guardian instance, not connected to live 60-market / 35-brand catalogs, and not wired to client ServiceNow/Jira until those systems are configured.

---

If anything does not load, try a hard refresh or another browser. I can walk anyone through TKT-1001 live in 10–15 minutes.

Thanks,
Saurabh
