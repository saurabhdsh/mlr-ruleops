#!/usr/bin/env bash
# MLR RuleOps — Mac local setup (no Docker)
# Same pattern as the Biospecimen start-local.sh that already worked on the other Mac:
# runtimes land in .local-runtime/, Postgres uses a high local port (not 5432).
#
#   ./start-local.sh
#   ./start-local.sh --reset
#
# Claude: set LLM_PROVIDER=bedrock (default). Uses AWS CLI / ~/.aws like aws_agent.py.
# No Anthropic or OpenAI API keys required.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
RUNTIME="$ROOT/.local-runtime"
RESEED=0
PGPORT="${PGPORT:-54329}"
PGUSER="ruleops"
PGPASSWORD="ruleops"
PGDATABASE="ruleops"
export PGPASSWORD

PYTHON_BIN=""
NODE_BIN_DIR=""
PG_BIN=""
BACKEND_PID=""
FRONTEND_PID=""
PG_STARTED=0

for arg in "$@"; do
  case "$arg" in
    --reset) RESEED=1 ;;
    --no-brew) ;; # kept for compatibility; brew is never required
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

log() { printf '\n\033[0;36m==>\033[0m %s\n' "$*"; }
ok() { printf '\033[0;32m    %s\033[0m\n' "$*"; }
die() { printf '\033[0;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "macOS is missing '$1'. It is a built-in tool and should already be present."
}

cpu_triple() {
  case "$(uname -m)" in
    arm64) echo "aarch64-apple-darwin" ;;
    x86_64) echo "x86_64-apple-darwin" ;;
    *) die "Unsupported Mac CPU: $(uname -m)" ;;
  esac
}

node_arch() {
  case "$(uname -m)" in
    arm64) echo "darwin-arm64" ;;
    x86_64) echo "darwin-x64" ;;
    *) die "Unsupported Mac CPU: $(uname -m)" ;;
  esac
}

unquarantine() {
  xattr -dr com.apple.quarantine "$1" 2>/dev/null || true
}

download() {
  local url="$1" dest="$2"
  curl -fL --retry 3 --retry-delay 2 \
    --connect-timeout 20 --max-time 180 \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36" \
    -o "$dest" "$url"
}

try_download() {
  local url="$1" dest="$2"
  if download "$url" "$dest"; then
    return 0
  fi
  rm -f "$dest"
  return 1
}

zonky_classifier() {
  case "$(uname -m)" in
    arm64) echo "darwin-arm64v8" ;;
    x86_64) echo "darwin-amd64" ;;
    *) die "Unsupported Mac CPU: $(uname -m)" ;;
  esac
}

resolve_pg_bin() {
  if [[ -x "$RUNTIME/postgres/bin/pg_ctl" ]]; then
    PG_BIN="$RUNTIME/postgres/bin"
    return 0
  fi
  local found
  found="$(find "$RUNTIME/postgres" -type f -name pg_ctl 2>/dev/null | head -n 1 || true)"
  if [[ -n "$found" && -x "$found" ]]; then
    PG_BIN="$(dirname "$found")"
    return 0
  fi
  return 1
}

unpack_zonky_jar() {
  local jar="$1"
  local tmp="$RUNTIME/postgres-unpack"
  rm -rf "$tmp" "$RUNTIME/postgres"
  mkdir -p "$tmp" "$RUNTIME/postgres"
  unzip -qo "$jar" -d "$tmp"
  local archive
  archive="$(find "$tmp" -type f \( -name '*.txz' -o -name '*.tar.xz' -o -name '*.tar.gz' -o -name '*.tgz' \) | head -n 1 || true)"
  [[ -n "$archive" ]] || return 1
  tar -xf "$archive" -C "$RUNTIME/postgres"
  rm -rf "$tmp" "$jar"
}

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ "$PG_STARTED" -eq 1 && -n "$PG_BIN" && -x "$PG_BIN/pg_ctl" ]]; then
    "$PG_BIN/pg_ctl" -D "$RUNTIME/pgdata" -m fast stop >/dev/null 2>&1 || true
  fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

find_existing_python() {
  local candidate version
  for candidate in \
    "$BACKEND/.venv/bin/python" \
    "$(command -v python3.12 2>/dev/null || true)" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    version="$("$candidate" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    if [[ "$version" == "3.12" || "$version" == "3.13" ]]; then
      PYTHON_BIN="$candidate"
      return 0
    fi
  done
  return 1
}

ensure_python() {
  if find_existing_python; then
    ok "Using Python $($PYTHON_BIN --version) at $PYTHON_BIN"
    return
  fi

  log "Python 3.12 is not on this Mac. Installing a user-local copy (no Homebrew, no admin)"
  mkdir -p "$RUNTIME/uv"
  if [[ ! -x "$RUNTIME/uv/uv" ]]; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$RUNTIME/uv" UV_NO_MODIFY_PATH=1 sh
  fi
  unquarantine "$RUNTIME/uv"
  "$RUNTIME/uv/uv" python install 3.12
  PYTHON_BIN="$("$RUNTIME/uv/uv" python find 3.12)"
  [[ -x "$PYTHON_BIN" ]] || die "Failed to install a user-local Python 3.12"
  ok "User-local Python ready: $PYTHON_BIN"
}

ensure_node() {
  local node npm
  node="$(command -v node 2>/dev/null || true)"
  npm="$(command -v npm 2>/dev/null || true)"
  if [[ -n "$node" && -n "$npm" ]]; then
    NODE_BIN_DIR="$(dirname "$node")"
    ok "Using Node $($node -v) from $NODE_BIN_DIR"
    return
  fi

  local ver="v20.19.0"
  local arch name dir
  arch="$(node_arch)"
  name="node-${ver}-${arch}"
  dir="$RUNTIME/node"
  if [[ ! -x "$dir/bin/node" ]]; then
    log "Node.js is not on this Mac. Downloading $name into the project (no Homebrew)"
    mkdir -p "$RUNTIME"
    download "https://nodejs.org/dist/${ver}/${name}.tar.gz" "$RUNTIME/node.tar.gz"
    rm -rf "$dir"
    mkdir -p "$dir"
    tar -xzf "$RUNTIME/node.tar.gz" -C "$RUNTIME"
    mv "$RUNTIME/$name" "$dir"
    rm -f "$RUNTIME/node.tar.gz"
    unquarantine "$dir"
  fi
  NODE_BIN_DIR="$dir/bin"
  [[ -x "$NODE_BIN_DIR/node" && -x "$NODE_BIN_DIR/npm" ]] || die "Failed to install a user-local Node.js"
  export PATH="$NODE_BIN_DIR:$PATH"
  ok "User-local Node $($NODE_BIN_DIR/node -v) ready"
}

find_pg_bin_from() {
  local dir="$1"
  if [[ -x "$dir/initdb" && -x "$dir/pg_ctl" ]]; then
    PG_BIN="$dir"
    return 0
  fi
  return 1
}

use_pg_libs() {
  local libdir
  libdir="$(cd "$PG_BIN/.." && pwd)/lib"
  if [[ -d "$libdir" ]]; then
    export DYLD_LIBRARY_PATH="$libdir${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
  fi
}

locate_existing_postgres() {
  local dir
  if resolve_pg_bin; then
    return 0
  fi
  for dir in \
    /Applications/Postgres.app/Contents/Versions/latest/bin \
    /Applications/Postgres.app/Contents/Versions/16/bin \
    "$HOME/Applications/Postgres.app/Contents/Versions/latest/bin" \
    /opt/homebrew/opt/postgresql@16/bin \
    /opt/homebrew/opt/postgresql@17/bin \
    /opt/homebrew/opt/postgresql/bin \
    /usr/local/opt/postgresql@16/bin \
    /usr/local/opt/postgresql@17/bin \
    /usr/local/opt/postgresql/bin; do
    if find_pg_bin_from "$dir"; then
      return 0
    fi
  done
  if command -v initdb >/dev/null 2>&1 && command -v pg_ctl >/dev/null 2>&1; then
    PG_BIN="$(dirname "$(command -v pg_ctl)")"
    return 0
  fi
  return 1
}

ensure_postgres_binaries() {
  if locate_existing_postgres; then
    use_pg_libs
    ok "Using PostgreSQL tools in $PG_BIN"
    return
  fi

  local ver="16.15.0"
  local triple name classifier
  triple="$(cpu_triple)"
  name="postgresql-${ver}-${triple}"
  classifier="$(zonky_classifier)"
  mkdir -p "$RUNTIME"

  log "PostgreSQL is not on this Mac. Downloading a portable copy into the project"
  rm -rf "$RUNTIME/postgres"
  mkdir -p "$RUNTIME/postgres"

  if try_download "https://github.com/theseus-rs/postgresql-binaries/releases/download/${ver}/${name}.tar.gz" "$RUNTIME/postgres.tar.gz"; then
    tar -xzf "$RUNTIME/postgres.tar.gz" -C "$RUNTIME/postgres"
    rm -f "$RUNTIME/postgres.tar.gz"
  elif try_download "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-${classifier}/${ver}/embedded-postgres-binaries-${classifier}-${ver}.jar" "$RUNTIME/postgres.jar"; then
    ok "GitHub releases were blocked; using Maven Central instead"
    unpack_zonky_jar "$RUNTIME/postgres.jar" || die "Failed to unpack the Maven Central PostgreSQL archive"
  elif command -v brew >/dev/null 2>&1; then
    log "Portable download failed. Installing postgresql@16 with Homebrew"
    brew install postgresql@16
    locate_existing_postgres || die "Homebrew PostgreSQL installed, but pg_ctl was not found"
    ok "Using PostgreSQL tools in $PG_BIN"
    return
  else
    die "Could not download PostgreSQL (GitHub returned 403 and Maven Central was unavailable). Install Postgres.app from https://postgresapp.com, reopen the terminal, then run ./start-local.sh again."
  fi

  resolve_pg_bin || die "Failed to unpack user-local PostgreSQL"
  unquarantine "$RUNTIME/postgres"
  use_pg_libs
  ok "User-local PostgreSQL ready: $PG_BIN"
}

pg_listening() {
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$PGPORT" >/dev/null 2>&1; then
    return 0
  fi
  bash -c "echo >/dev/tcp/127.0.0.1/$PGPORT" >/dev/null 2>&1
}

wait_pg() {
  local i
  for i in $(seq 1 80); do
    if pg_listening; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

fail_pg() {
  if [[ -f "$RUNTIME/postgres.log" ]]; then
    printf '\n----- postgres.log (last 40 lines) -----\n' >&2
    tail -n 40 "$RUNTIME/postgres.log" >&2 || true
    printf '----------------------------------------\n' >&2
  fi
  die "Project-local PostgreSQL did not start. See $RUNTIME/postgres.log"
}

bootstrap_database() {
  local py="$BACKEND/.venv/bin/python"
  [[ -x "$py" ]] || die "Python venv is missing. API dependencies must be installed before the database is created."
  PGPORT="$PGPORT" PGUSER="$PGUSER" PGPASSWORD="$PGPASSWORD" PGDATABASE="$PGDATABASE" \
    "$py" <<'PY'
import os
import psycopg

port = int(os.environ["PGPORT"])
user = os.environ["PGUSER"]
password = os.environ["PGPASSWORD"]
name = os.environ["PGDATABASE"]
conn = psycopg.connect(
    host="127.0.0.1",
    port=port,
    user=user,
    password=password,
    dbname="postgres",
    autocommit=True,
)
exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone()
if not exists:
    conn.execute(f'CREATE DATABASE "{name}"')
    print("created")
else:
    print("exists")
conn.close()
conn = psycopg.connect(
    host="127.0.0.1",
    port=port,
    user=user,
    password=password,
    dbname=name,
    autocommit=True,
)
conn.execute(f"GRANT ALL ON SCHEMA public TO {user}")
conn.close()
PY
}

ensure_database() {
  local data="$RUNTIME/pgdata"
  local sock="$RUNTIME/pgsocket"
  mkdir -p "$sock"
  use_pg_libs

  log "Starting a project-local PostgreSQL on port $PGPORT (not system 5432)"
  if [[ ! -f "$data/PG_VERSION" ]]; then
    "$PG_BIN/initdb" -D "$data" -U "$PGUSER" --auth=trust --encoding=UTF8 --locale=C
    ok "Initialized project-local database cluster"
  fi

  if ! pg_listening; then
    if [[ -f "$data/postmaster.pid" ]] && ! "$PG_BIN/pg_ctl" -D "$data" status >/dev/null 2>&1; then
      rm -f "$data/postmaster.pid"
    fi
    if "$PG_BIN/pg_ctl" -D "$data" -l "$RUNTIME/postgres.log" -w start \
      -o "-p $PGPORT -k $sock --listen_addresses=127.0.0.1"; then
      PG_STARTED=1
    elif pg_listening; then
      ok "PostgreSQL already listening on $PGPORT"
    else
      fail_pg
    fi
  else
    ok "PostgreSQL already listening on $PGPORT"
  fi
  wait_pg || fail_pg

  local status
  status="$(bootstrap_database)"
  if [[ "$status" == *created* ]]; then
    ok "Created database $PGDATABASE"
  else
    ok "Database $PGDATABASE already exists"
  fi
}

env_get() {
  local key="$1" default="${2:-}"
  local file="$ROOT/.env"
  if [[ -f "$file" ]]; then
    local val
    val="$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 | sed "s/^${key}=//" | tr -d '\r' || true)"
    if [[ -n "$val" ]]; then
      printf '%s' "$val"
      return
    fi
  fi
  printf '%s' "$default"
}

write_backend_env() {
  local llm_provider aws_region aws_profile bedrock_model jwt_secret
  llm_provider="$(env_get LLM_PROVIDER bedrock)"
  aws_region="$(env_get AWS_REGION us-east-1)"
  aws_profile="$(env_get AWS_PROFILE default)"
  bedrock_model="$(env_get BEDROCK_MODEL anthropic.claude-3-haiku-20240307-v1:0)"
  jwt_secret="$(env_get JWT_SECRET change-me-jwt-secret-use-a-long-random-string)"

  cat > "$BACKEND/.env" <<EOF
APP_NAME=MLR RuleOps
APP_ENV=demo
DATABASE_URL=postgresql+psycopg://${PGUSER}:${PGPASSWORD}@127.0.0.1:${PGPORT}/${PGDATABASE}
REDIS_URL=redis://127.0.0.1:1/0
JWT_SECRET=${jwt_secret}
SECRET_KEY=${jwt_secret}
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
SEED_ON_STARTUP=true
SEED_REVIEWS=200
LLM_PROVIDER=${llm_provider}
LLM_CONFIDENCE_THRESHOLD=0.72
AWS_REGION=${aws_region}
AWS_PROFILE=${aws_profile}
BEDROCK_MODEL=${bedrock_model}
EOF
  mkdir -p "$FRONTEND"
  cat > "$FRONTEND/.env.local" <<EOF
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SSE_BASE_URL=http://127.0.0.1:8000
EOF
  ok "Wrote backend/.env → 127.0.0.1:${PGPORT} · LLM_PROVIDER=${llm_provider}"
}

setup_backend_deps() {
  log "Setting up Python API"
  if [[ ! -x "$BACKEND/.venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$BACKEND/.venv"
  fi
  "$BACKEND/.venv/bin/python" -m pip install --upgrade pip >/dev/null
  "$BACKEND/.venv/bin/python" -m pip install -r "$BACKEND/requirements.txt"
  ok "API dependencies are ready"
}

setup_backend_migrate() {
  (
    cd "$BACKEND"
    "$BACKEND/.venv/bin/alembic" upgrade head
    if [[ "$RESEED" -eq 1 ]]; then
      "$BACKEND/.venv/bin/python" <<'PY'
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.seed import seed_all
from app import models  # noqa: F401

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    seed_all(db, reviews=200)
    db.commit()
    print("Reseed complete")
finally:
    db.close()
PY
    else
      "$BACKEND/.venv/bin/python" -m app.db.seed
    fi
  )
  ok "Migrations and seed data are ready"
}

setup_frontend() {
  log "Setting up React UI"
  export PATH="${NODE_BIN_DIR}:$PATH"
  (
    cd "$FRONTEND"
    npm install
  )
  ok "UI dependencies are ready"
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http() {
  local url="$1"
  local i
  for i in $(seq 1 50); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.4
  done
  return 1
}

start_services() {
  if port_in_use 8000; then
    die "Port 8000 is already in use. Stop that process and run this script again."
  fi
  if port_in_use 5173; then
    die "Port 5173 is already in use. Stop that process and run this script again."
  fi

  export PATH="${NODE_BIN_DIR}:$PATH"

  log "Starting API on http://127.0.0.1:8000"
  (
    cd "$BACKEND"
    exec "$BACKEND/.venv/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000
  ) &
  BACKEND_PID=$!
  wait_http "http://127.0.0.1:8000/api/v1/health" || wait_http "http://127.0.0.1:8000/health" \
    || die "API did not start. Check the output above."
  ok "API is healthy"

  log "Starting UI on http://127.0.0.1:5173"
  (
    cd "$FRONTEND"
    exec npm run dev -- --host 127.0.0.1 --port 5173
  ) &
  FRONTEND_PID=$!
  wait_http "http://127.0.0.1:5173" || die "UI did not start. Check the output above."

  cat <<EOF

----------------------------------------------------------------------
MLR RuleOps is running
(no Docker — project-local Postgres on port ${PGPORT})

  UI:      http://localhost:5173
  API:     http://localhost:8000
  Swagger: http://localhost:8000/docs

  mlr.admin@mlr-ruleops.local  / ChangeMe!Mlr1
  admin@mlr-ruleops.local      / ChangeMe!Admin1
  medical@mlr-ruleops.local    / ChangeMe!Med1

  LLM: ${LLM_PROVIDER:-bedrock} via AWS CLI profile (aws sts get-caller-identity)
  Process ticket runs in-process (Redis/Celery not required)

Press Ctrl+C to stop the UI, API, and local database.
----------------------------------------------------------------------

EOF
  wait
}

[[ "$(uname -s)" == "Darwin" ]] || die "This script is for macOS."
need_cmd curl
need_cmd tar
need_cmd lsof
need_cmd unzip

mkdir -p "$RUNTIME"
log "Preparing a user-local environment (Homebrew is not required)"
ensure_python
ensure_node
ensure_postgres_binaries
setup_backend_deps
write_backend_env
ensure_database
setup_backend_migrate
setup_frontend
start_services
