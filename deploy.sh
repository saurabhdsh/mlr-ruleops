#!/bin/bash
set -e

EC2_HOST="${EC2_HOST:-52.0.130.62}"
APP_PORT="${APP_PORT:-8081}"

echo "=== MLR RuleOps — EC2 Deploy Script ==="
echo "    Host port ${APP_PORT} (SEAL stays on 80/8080/3000)"

# ── 1. Install dependencies if missing ───────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  sudo yum update -y
  sudo yum install -y docker git
  sudo systemctl start docker
  sudo systemctl enable docker
  sudo usermod -aG docker ec2-user
  echo "Docker installed. Please run: newgrp docker && ./deploy.sh"
  exit 0
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
  echo "Installing Docker Compose..."
  sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi

# ── 2. Create .env if it doesn't exist ───────────────────────────────────────
if [ ! -f .env ]; then
  echo ""
  echo "Creating .env file..."

  JWT_SECRET=$(openssl rand -hex 32)
  SECRET_KEY=$(openssl rand -hex 32)

  cat > .env <<EOF
APP_NAME=MLR RuleOps
APP_ENV=demo
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}
JWT_EXPIRY_MINUTES=480
JWT_ALGORITHM=HS256

DATABASE_URL=postgresql+psycopg://ruleops:ruleops@postgres:5432/ruleops
REDIS_URL=redis://redis:6379/0

CORS_ORIGINS=http://${EC2_HOST}:${APP_PORT},http://127.0.0.1:${APP_PORT}

# AWS Bedrock — uses EC2 IAM role (same as SEAL), no keys needed
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_PROFILE=
BEDROCK_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0

SEED_ON_STARTUP=true
SEED_REVIEWS=200
EOF

  echo ".env created with auto-generated JWT secrets."
fi

# ── 3. Pull latest code ───────────────────────────────────────────────────────
echo ""
echo "Pulling latest code..."
git pull origin main 2>/dev/null || true

# ── 4. Build and start containers ────────────────────────────────────────────
echo ""
echo "Building and starting containers (this takes 3-5 minutes first time)..."
docker compose -f docker-compose.aws.yml down 2>/dev/null || docker-compose -f docker-compose.aws.yml down 2>/dev/null || true
docker compose -f docker-compose.aws.yml up -d --build 2>/dev/null || docker-compose -f docker-compose.aws.yml up -d --build

# ── 5. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  MLR RuleOps is deploying!"
echo "  URL:      http://${EC2_HOST}:${APP_PORT}"
echo "  Login:    mlr.admin@mlr-ruleops.local"
echo "  Password: ChangeMe!Mlr1"
echo "============================================"
echo ""
echo "SEAL is unchanged on http://${EC2_HOST} (and 8080/3000)."
echo "Check logs: docker compose -f docker-compose.aws.yml logs -f backend"
