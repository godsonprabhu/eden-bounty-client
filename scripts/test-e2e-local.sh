#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

command -v docker >/dev/null || { echo "Docker is required for disposable E2E PostgreSQL." >&2; exit 2; }
[[ -x backend/.venv/bin/alembic && -x backend/.venv/bin/python3 ]] || { echo "Create the backend virtual environment and install backend requirements first." >&2; exit 2; }
[[ -x node_modules/.bin/playwright ]] || { echo "Install npm dependencies first (npm install)." >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is unavailable; refusing to use another database." >&2; exit 2; }

suffix="$(date +%s)_$$"
container="eb-playwright-${suffix}"
database="eb_playwright_test_${suffix}"
storage_dir="$(mktemp -d "${TMPDIR:-/tmp}/eb-playwright-storage.XXXXXX")"
frontend_dir="$(mktemp -d "${TMPDIR:-/tmp}/eb-playwright-frontend.XXXXXX")"
cleanup() {
  docker stop "$container" >/dev/null 2>&1 || true
  docker rm "$container" >/dev/null 2>&1 || true
  rm -rf -- "$storage_dir"
  rm -rf -- "$frontend_dir"
}
trap cleanup EXIT INT TERM

# An isolated Next working directory avoids sharing `.next` locks or build output with an
# already-running local development server. Copy only frontend runtime files; do not copy .env,
# private storage, backups, or Git metadata.
cp -a src public next.config.ts tsconfig.json postcss.config.mjs package.json package-lock.json "$frontend_dir/"
ln -s "$repo_root/node_modules" "$frontend_dir/node_modules"

if [[ "${PW_STANDALONE:-0}" == "1" ]]; then
  echo "Preparing standalone production build in isolated test directory..."
  cp -a .next "$frontend_dir/"
  mkdir -p "$frontend_dir/.next/standalone/.next/static"
  cp -a "$frontend_dir/.next/static/"* "$frontend_dir/.next/standalone/.next/static/"
  cp -a "$frontend_dir/public" "$frontend_dir/.next/standalone/"
fi

echo "Starting a fresh PostgreSQL test container on loopback only..."
docker run -d \
  --name "$container" \
  -e POSTGRES_USER=eb_playwright \
  -e POSTGRES_DB="$database" \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1::5432 \
  postgres:16-alpine >/dev/null

port="$(docker port "$container" 5432/tcp | sed 's/.*://')"
database_ready=false
for _ in $(seq 1 90); do
  if docker exec "$container" pg_isready -U eb_playwright -d "$database" >/dev/null 2>&1; then database_ready=true; break; fi
  sleep 1
done
if [[ "$database_ready" != true ]]; then
  echo "Disposable PostgreSQL did not become ready; container log follows:" >&2
  docker logs "$container" >&2 || true
  exit 2
fi
echo "Disposable PostgreSQL accepted connections on its loopback-only port."

export PW_LOCAL_TEST=1
pick_loopback_port() {
  backend/.venv/bin/python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}
export PW_BASE_URL="${PW_BASE_URL:-http://127.0.0.1:$(pick_loopback_port)}"
export PW_BACKEND_URL="${PW_BACKEND_URL:-http://127.0.0.1:$(pick_loopback_port)}"
export NEXT_PUBLIC_API_URL=""
export DATABASE_URL="postgresql+asyncpg://eb_playwright@127.0.0.1:${port}/${database}"
export APP_ENV=test
export DEBUG=false
export WORKERS=1
export SMTP_ENABLED=false
unset SMTP_USER SMTP_PASSWORD
export CORS_ORIGINS="[\"${PW_BASE_URL}\"]"
export PUBLIC_SITE_URL="$PW_BASE_URL"
export PRIVATE_STORAGE_DIR="$storage_dir"
export PYTHONPATH="$repo_root/backend${PYTHONPATH:+:$PYTHONPATH}"
export PW_FRONTEND_DIR="$frontend_dir"
export APP_SECRET_KEY="$(backend/.venv/bin/python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export PW_TEST_PASSWORD="$(backend/.venv/bin/python3 -c 'import secrets; print("E2e-" + secrets.token_urlsafe(24) + "-9!")')"
export PW_RESET_PASSWORD="$(backend/.venv/bin/python3 -c 'import secrets; print("Reset-" + secrets.token_urlsafe(24) + "-8!")')"
export PW_ADMIN_EMAIL="admin-${suffix}@example.com"
export PW_CUSTOMER_EMAIL="customer-a-${suffix}@example.com"
export PW_CUSTOMER_B_EMAIL="customer-b-${suffix}@example.com"
export PW_INVESTOR_EMAIL="investor-a-${suffix}@example.com"
export PW_INVESTOR_B_EMAIL="investor-b-${suffix}@example.com"
export PW_NEW_CUSTOMER_EMAIL="new-customer-${suffix}@example.com"
echo "Migrating the fresh disposable database to the active Alembic head..."
(cd backend && .venv/bin/python3 -m alembic upgrade head)
echo "Creating synthetic acceptance fixtures in the disposable database..."
fixture_ids="$(backend/.venv/bin/python3 e2e/seed_local.py)"
[[ -n "$fixture_ids" ]] || { echo "Synthetic E2E fixture setup failed; refusing to start browser tests." >&2; exit 2; }
export PW_FIXTURE_IDS="$fixture_ids"
echo "Running isolated Chromium acceptance tests..."
if (($#)); then
  npm run test:e2e -- "$@"
else
  npm run test:e2e
fi
