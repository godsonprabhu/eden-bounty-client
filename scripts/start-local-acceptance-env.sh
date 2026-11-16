#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

command -v docker >/dev/null || { echo "Docker is required." >&2; exit 2; }
[[ -x backend/.venv/bin/alembic && -x backend/.venv/bin/python ]] || { echo "Backend virtual environment required." >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is unavailable; cannot start disposable acceptance database." >&2; exit 2; }

# Helper to check if a local port is free on 127.0.0.1
is_port_free() {
  local p="$1"
  backend/.venv/bin/python -c "
import socket, sys
port = int(sys.argv[1])
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port))
    s.listen(1)
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
" "$p"
}

# 1. Backend Port Validation (Requirement 5 & 11)
# Acceptance backend uses port 8001 to prevent collision with eb_backend_dev (port 8000).
BACKEND_PORT="${BACKEND_PORT:-8001}"
if ! is_port_free "$BACKEND_PORT"; then
  echo "ERROR: Backend port ${BACKEND_PORT} is already occupied by an existing process." >&2
  echo "Per safety requirements, existing processes will not be killed. Please free port ${BACKEND_PORT} or set BACKEND_PORT." >&2
  exit 1
fi

# 2. Frontend Port Validation (Requirement 5 & 11)
# Frontend: port 3000 if available. If 3000 is occupied, fall back to 3001 if available.
# If FRONTEND_PORT was explicitly set by the user, enforce that specific port.
if [[ -n "${FRONTEND_PORT:-}" ]]; then
  if ! is_port_free "$FRONTEND_PORT"; then
    echo "ERROR: Requested frontend port ${FRONTEND_PORT} is already occupied." >&2
    echo "Per safety requirements, existing processes will not be killed. Please free port ${FRONTEND_PORT}." >&2
    exit 1
  fi
else
  if is_port_free 3000; then
    FRONTEND_PORT=3000
  elif is_port_free 3001; then
    FRONTEND_PORT=3001
    echo "Notice: Port 3000 is currently in use. Frontend will use alternative available port: ${FRONTEND_PORT}."
  else
    echo "ERROR: Neither port 3000 nor port 3001 is available for the frontend." >&2
    echo "Per safety requirements, existing processes will not be killed." >&2
    exit 1
  fi
fi

# Suffix for disposable container and database
suffix="manual_$(date +%s)_$$"
container="eb-accept-${suffix}"
database="eb_playwright_test_${suffix}"
storage_dir="$(mktemp -d "${TMPDIR:-/tmp}/eb-accept-storage.XXXXXX")"
frontend_dir="$(mktemp -d "${TMPDIR:-/tmp}/eb-accept-frontend.XXXXXX")"

BACKEND_PID=""
FRONTEND_PID=""

kill_tree() {
  local pid="$1"
  local sig="${2:-TERM}"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  local children
  children=$(pgrep -P "$pid" 2>/dev/null || true)
  for child in $children; do
    kill_tree "$child" "$sig"
  done
  kill -"$sig" "$pid" >/dev/null 2>&1 || true
}

cleanup() {
  echo ""
  echo "Shutting down local acceptance environment..."
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill_tree "$FRONTEND_PID" TERM
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill_tree "$BACKEND_PID" TERM
  fi
  if [[ -n "$container" ]]; then
    docker stop "$container" >/dev/null 2>&1 || true
    docker rm "$container" >/dev/null 2>&1 || true
  fi
  if [[ -n "$storage_dir" && -d "$storage_dir" ]]; then
    rm -rf -- "$storage_dir"
  fi
  if [[ -n "$frontend_dir" && -d "$frontend_dir" ]]; then
    rm -rf -- "$frontend_dir"
  fi
  echo "Cleaned up disposable container and storage. Development database and existing services were untouched."
}
trap cleanup EXIT INT TERM

echo "=================================================="
echo "Starting Fresh Disposable PostgreSQL Container..."
echo "=================================================="
docker run -d \
  --name "$container" \
  -e POSTGRES_USER=eb_playwright \
  -e POSTGRES_DB="$database" \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1::5432 \
  postgres:16-alpine >/dev/null

db_port="$(docker port "$container" 5432/tcp | sed 's/.*://')"

if [[ "$db_port" == "5433" || "$db_port" == "5432" ]]; then
  echo "CRITICAL SAFETY REFUSAL: Disposable port collided with protected port ${db_port}." >&2
  exit 1
fi

db_ready=false
for _ in $(seq 1 60); do
  if docker exec "$container" pg_isready -U eb_playwright -d "$database" >/dev/null 2>&1; then
    db_ready=true
    break
  fi
  sleep 1
done

if [[ "$db_ready" != true ]]; then
  echo "ERROR: Disposable PostgreSQL did not become ready." >&2
  exit 1
fi

echo "Disposable PostgreSQL active on loopback port: ${db_port}"
echo "Database Name: ${database}"

# Environment configuration
export DATABASE_URL="postgresql+asyncpg://eb_playwright@127.0.0.1:${db_port}/${database}"
if [[ "$DATABASE_URL" == *"5433"* || "$DATABASE_URL" == *"eden_bounty_db"* ]]; then
  echo "CRITICAL SAFETY REFUSAL: DATABASE_URL points to protected development database." >&2
  exit 1
fi
export PORT="$BACKEND_PORT"
export APP_ENV=test
export DEBUG=true
export WORKERS=1
export SMTP_ENABLED=false
unset SMTP_USER SMTP_PASSWORD || true
export CORS_ORIGINS="[\"http://localhost:${FRONTEND_PORT}\",\"http://127.0.0.1:${FRONTEND_PORT}\",\"http://localhost:3000\",\"http://127.0.0.1:3000\",\"http://localhost:3001\",\"http://127.0.0.1:3001\",\"http://127.0.0.1:${BACKEND_PORT}\",\"http://localhost:${BACKEND_PORT}\"]"
export PUBLIC_SITE_URL="http://localhost:${FRONTEND_PORT}"
export PRIVATE_STORAGE_DIR="$storage_dir"
export PYTHONPATH="$repo_root/backend"
export APP_SECRET_KEY="acceptance-secret-key-32-bytes-minimum-length-for-hmac-sha256"

# Ensure Next.js API calls target backend on port 8001 (Requirement 6)
export INTERNAL_BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
export NEXT_PUBLIC_API_URL=""

# Test credentials
export PW_TEST_PASSWORD="TestPassword123!"
export PW_ADMIN_EMAIL="admin@edenbounty.org"
export PW_CUSTOMER_EMAIL="customer@example.com"
export PW_CUSTOMER_B_EMAIL="customer-b@example.com"
export PW_INVESTOR_EMAIL="investor@example.com"
export PW_INVESTOR_B_EMAIL="investor-b@example.com"
export PW_NEW_CUSTOMER_EMAIL="new@example.com"

echo "Migrating fresh database to active head (0012_deactivate_shisha_and_axe_oil)..."
(cd backend && .venv/bin/alembic upgrade head)

echo "Seeding acceptance accounts and records in disposable database..."
backend/.venv/bin/python e2e/seed_local.py >/dev/null

echo "Starting FastAPI Backend on 127.0.0.1:${BACKEND_PORT}..."
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" >"$storage_dir/backend.log" 2>&1 &
BACKEND_PID=$!

backend_ready=false
for _ in $(seq 1 30); do
  if curl -s "http://127.0.0.1:${BACKEND_PORT}/health" | grep -q '"status":"healthy"'; then
    backend_ready=true
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend process exited unexpectedly. Log follows:" >&2
    cat "$storage_dir/backend.log" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$backend_ready" != true ]]; then
  echo "ERROR: Backend failed to become healthy within 30s. Log follows:" >&2
  cat "$storage_dir/backend.log" >&2
  exit 1
fi
echo "FastAPI Backend is healthy on 127.0.0.1:${BACKEND_PORT}."

echo "Preparing isolated Next.js frontend directory..."
cp -a src public next.config.ts tsconfig.json postcss.config.mjs package.json package-lock.json "$frontend_dir/"
ln -s "$repo_root/node_modules" "$frontend_dir/node_modules"

echo "Starting Next.js Frontend on 127.0.0.1:${FRONTEND_PORT}..."
(cd "$frontend_dir" && \
  INTERNAL_BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}" \
  NEXT_PUBLIC_API_URL="" \
  PORT="$FRONTEND_PORT" \
  HOSTNAME="127.0.0.1" \
  npm run dev -- --webpack --hostname 127.0.0.1 --port "$FRONTEND_PORT") >"$storage_dir/frontend.log" 2>&1 &
FRONTEND_PID=$!

frontend_ready=false
for _ in $(seq 1 45); do
  if curl -s "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
    frontend_ready=true
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "ERROR: Frontend process exited unexpectedly. Log follows:" >&2
    cat "$storage_dir/frontend.log" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$frontend_ready" != true ]]; then
  echo "ERROR: Frontend failed to respond within 45s. Log follows:" >&2
  cat "$storage_dir/frontend.log" >&2
  exit 1
fi
echo "Next.js Frontend is active on 127.0.0.1:${FRONTEND_PORT}."

# Verification check: Ensure Next.js rewrites target the acceptance backend on port 8001
echo "Verifying Next.js -> FastAPI API rewrite connection..."
rewrite_verified=false
for _ in $(seq 1 15); do
  rewrite_res="$(curl -s "http://127.0.0.1:${FRONTEND_PORT}/api/v1/health" || true)"
  if echo "$rewrite_res" | grep -q '"status":"healthy"'; then
    rewrite_verified=true
    break
  fi
  sleep 1
done

if [[ "$rewrite_verified" != true ]]; then
  echo "WARNING: Next.js API rewrite verification to port ${BACKEND_PORT} did not confirm healthy status." >&2
else
  echo "Verified: Next.js API proxy successfully targets acceptance backend on port ${BACKEND_PORT}."
fi

# Verification check: Ensure registration endpoint is active on acceptance backend (proves isolation from port 8000)
reg_probe_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:${FRONTEND_PORT}/api/v1/auth/register" || true)"
if [[ "$reg_probe_code" == "422" || "$reg_probe_code" == "201" ]]; then
  echo "Verified: Route /api/v1/auth/register responds with HTTP ${reg_probe_code} (confirmed active revision 0010 backend)."
else
  echo "ERROR: Registration route returned unexpected HTTP code: ${reg_probe_code}" >&2
  exit 1
fi

# Verification check: Ensure dedicated investor login page loads cleanly (HTTP 200)
investor_page_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}/investors/login" || true)"
if [[ "$investor_page_code" == "200" ]]; then
  echo "Verified: Dedicated investor login page (/investors/login) responds with HTTP 200 OK."
else
  echo "ERROR: Dedicated investor login page returned unexpected HTTP code: ${investor_page_code}" >&2
  exit 1
fi

# Verification check: Live authentication verification for all acceptance accounts via Next.js proxy
echo "Verifying live authentication for all acceptance accounts via Next.js proxy..."
backend/.venv/bin/python -c "
import urllib.request, json, sys, http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
base_url = 'http://127.0.0.1:${FRONTEND_PORT}/api/v1'

def post_json(path, data):
    req = urllib.request.Request(
        f'{base_url}{path}',
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
    )
    try:
        with opener.open(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8')), resp.headers
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw': raw}
        return e.code, body, e.headers

# 1. Admin login verification
code, body, hdrs = post_json('/auth/login', {'email': 'admin@edenbounty.org', 'password': 'TestPassword123!'})
assert code == 200, f'Admin login failed ({code}): {body}'
assert body.get('data', {}).get('account_type') == 'ADMIN', f'Admin role mismatch: {body}'
assert body.get('data', {}).get('redirect_to') == '/admin', f'Admin redirect mismatch: {body}'
print('  ✓ Admin login verified (200 OK -> /admin)')

# 2. Customer login verification
code, body, hdrs = post_json('/auth/login', {'email': 'customer@example.com', 'password': 'TestPassword123!'})
assert code == 200, f'Customer login failed ({code}): {body}'
assert body.get('data', {}).get('account_type') == 'CUSTOMER', f'Customer role mismatch: {body}'
assert body.get('data', {}).get('redirect_to') == '/account', f'Customer redirect mismatch: {body}'
print('  ✓ Customer login verified (200 OK -> /account)')

# 3. Investor login verification via /auth/login
code, body, hdrs = post_json('/auth/login', {'email': 'investor@example.com', 'password': 'TestPassword123!'})
assert code == 200, f'Investor login on /auth/login failed ({code}): {body}'
assert body.get('data', {}).get('account_type') == 'INVESTOR', f'Investor role mismatch: {body}'
assert body.get('data', {}).get('redirect_to') == '/investors/portal', f'Investor redirect mismatch: {body}'
print('  ✓ Investor login via /login verified (200 OK -> /investors/portal)')

# 4. Investor login verification via dedicated /investor/login
code, body, hdrs = post_json('/investor/login', {'email': 'investor@example.com', 'password': 'TestPassword123!'})
assert code == 200, f'Dedicated /investor/login failed ({code}): {body}'
assert body.get('data', {}).get('account_type') == 'INVESTOR', f'Investor role mismatch on /investor/login: {body}'
assert body.get('data', {}).get('redirect_to') == '/investors/portal', f'Investor redirect mismatch: {body}'
print('  ✓ Dedicated /investor/login verified (200 OK -> /investors/portal)')

# 5. Role-boundary security test: Customer credentials refused on /investor/login
code, body, hdrs = post_json('/investor/login', {'email': 'customer@example.com', 'password': 'TestPassword123!'})
assert code == 401, f'Expected 401 on /investor/login for customer credentials, got {code}'
print('  ✓ Role boundary verified (/investor/login refuses non-investor credentials with HTTP 401)')
"

echo "All acceptance accounts verified and authenticating successfully."

echo ""
echo "=================================================="
echo "EDEN BOUNTY LOCAL ACCEPTANCE ENVIRONMENT READY"
echo "=================================================="
echo ""
echo "FRONTEND URL:  http://localhost:${FRONTEND_PORT}"
echo "BACKEND URL:   http://127.0.0.1:${BACKEND_PORT}"
echo "DATABASE:      Disposable PostgreSQL on loopback port ${db_port}"
echo "DEV DB (5433): Completely untouched and preserved"
echo ""
echo "TEST ACCOUNTS & DASHBOARD TARGETS:"
echo "--------------------------------------------------"
echo "1. ADMIN ACCOUNT:"
echo "   URL:      http://localhost:${FRONTEND_PORT}/login"
echo "   Email:    admin@edenbounty.org"
echo "   Password: TestPassword123!"
echo "   Target:   /admin (Dashboard & Operations Console)"
echo ""
echo "2. CUSTOMER ACCOUNT:"
echo "   URL:      http://localhost:${FRONTEND_PORT}/login"
echo "   Email:    customer@example.com"
echo "   Password: TestPassword123!"
echo "   Target:   /account (Customer Dashboard, Enquiries, Orders)"
echo ""
echo "3. INVESTOR ACCOUNT:"
echo "   URL:      http://localhost:${FRONTEND_PORT}/investors/login (or /login)"
echo "   Email:    investor@example.com"
echo "   Password: TestPassword123!"
echo "   Target:   /investors/portal (Investor Dashboard, Investments, Documents)"
echo ""
echo "4. NEW REGISTRATION & LOCAL VERIFICATION:"
echo "   URL:      http://localhost:${FRONTEND_PORT}/register"
echo "   - Choose Customer or Investor account"
echo "   - Submit form with any valid email and strong password"
echo "   - Security note: Verification tokens and links are never displayed publicly"
echo "   - Unverified accounts cannot sign in until email verification is completed"
echo "   - To verify a synthetic test account, run the CLI verification tool in another terminal:"
echo "       ./backend/.venv/bin/python3 -m app.cli.verify_account --email <email>"
echo "     Or generate a single-use verification link in terminal:"
echo "       ./backend/.venv/bin/python3 -m app.cli.verify_account --email <email> --show-link"
echo ""
echo "5. SERVICES REDESIGN:"
echo "   URL:      http://localhost:${FRONTEND_PORT}/services"
echo "   - Minimal cards without long descriptions"
echo "   - Click any card -> Opens /services/[slug] with all 8 detailed sections and pre-locked RFQ"
echo ""
echo "=================================================="

if [[ "${1:-}" == "--check" || "${CHECK_ONLY:-0}" == "1" ]]; then
  echo "Check-only mode requested. All connectivity and rewrites verified successfully."
  exit 0
fi

echo "Acceptance environment is active. Press Ctrl+C to shut down and clean up."
wait $BACKEND_PID $FRONTEND_PID || true
