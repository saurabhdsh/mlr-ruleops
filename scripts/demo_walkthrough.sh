#!/usr/bin/env bash
set -euo pipefail
BASE="${API_BASE:-http://localhost:8000/api/v1}"

echo "Logging in as MLR admin..."
TOKEN=$(curl -s "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"mlr.admin@mlr-ruleops.local","password":"ChangeMe!Mlr1"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

AUTH=(-H "Authorization: Bearer $TOKEN")

echo "Fetching TKT-1001..."
curl -s "${AUTH[@]}" "$BASE/tickets/TKT-1001" | python -m json.tool | head -40

echo "Processing TKT-1001..."
curl -s -X POST "${AUTH[@]}" "$BASE/tickets/TKT-1001/process" | python -c "import sys,json; d=json.load(sys.stdin); print(d['ticket']['status'], d['proposal']['target_rule_id'] if d.get('proposal') else None)"

echo "Done. Open the Change Workspace for TKT-1001."
