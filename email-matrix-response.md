Subject: Medical Affairs rule-change use case — built, not a slide

Hi,

This use case is not unaddressed. We built a working system for it. It is live, not a deck.

The **exam paper** is rules maintenance: a non-technical ticket, a TEXT-string or business-logic change, validation, MLR-admin sign-off, audit, rollback. Targeting in that document is the **5-tier hierarchy** (Universal / Market / Brand / Market-Brand / Scientific Accuracy). Hero script: update the US Drug A cardiovascular disclaimer, add the 2026 citation, remove the 2020 study.

The **78-configuration matrix, 20+ languages, and “NLP must resolve against the actual matrix”** are **not in the exam paper**. They are in this email. We built that on top of the exam.

**Pages 38–45 of the attached PDF are a different requirement.** They describe live Content Lab document review (promotional file in, AI review, result back). That is not the exam paper, and it is not the ticket-to-rule-change problem. This product is the exam plus the matrix ask from this email.

What you asked for here, and what is in the product:

- Non-technical request (incomplete, no rule ID)
- Text-string update **or** business-logic change
- Rollback
- NLP keys hit the **real 78-row matrix** (22 languages): Market, Brand, Therapeutic Area, String Type, Old Value, New Value
- Matrix first, then the exam’s 5-tier engine so mutation stays safe
- CSV daily-delta import/export on that same table — not a second product

Proof path (do this, do not take my word):

1. Open http://52.0.130.62:8081
2. Sign in: `mlr.admin@mlr-ruleops.local` / `ChangeMe!Mlr1`
3. Command Center: **Active configurations: 78**
4. **Configuration Matrix**: 78 rows, 22 languages, CSV in/out
5. Process **TKT-1001**
6. Workspace must show `CFG-US-DRUGA-CV-DISCLAIMER-EN` → `RULE-US-DRUGA-CV-014`
7. Approve, deploy, rollback. Audit stays.

Also in: form/API/webhook intake; ServiceNow/Jira adapters (not wired until credentials exist); sandbox; historical replay; impact/risk; HITL; immutable versions; checksums; RBAC; full ledger.

If the next ask is the pages 38–45 document-review path, that is a separate build. It was not in the exam document.

Code: https://github.com/saurabhdsh/mlr-ruleops

If AWS does not yet show the matrix, that box needs `git pull` and `./deploy.sh`. I can walk TKT-1001 live in 10 minutes.

Saurabh
