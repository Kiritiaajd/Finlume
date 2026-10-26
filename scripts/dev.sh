#!/usr/bin/env bash
# Start the Finlume backend (Django) and web frontend (Vite) together for development.
#
#   ./scripts/dev.sh                      start both; Ctrl+C stops both
#   ./scripts/dev.sh --backend-port 8001  use another backend port (Vite's /api proxy follows)
#   ./scripts/dev.sh --check              prerequisite and port checks only
#   ./scripts/dev.sh --smoke              start, wait until both answer, then stop
#
# It never installs packages, runs migrations, changes data, or starts Docker
# or the mobile app. Output is prefixed [api] / [web] and kept in .dev/logs/.
# Before starting, the read-only "manage.py dbstatus" must reach the database.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
WEB_DIR="$ROOT/apps/web"
LOG_DIR="$ROOT/.dev/logs"
HEALTH_PATH="/api/v1/health/"
BACKEND_PORT=8000
WEB_PORT=5173
READY_TIMEOUT=60
MODE="run"

usage() {
    sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    echo "Options: --backend-port N  --web-port N  --timeout SECONDS  --check  --smoke  -h|--help"
}

is_port() { [[ "$1" =~ ^[0-9]+$ ]] && (( $1 >= 1024 && $1 <= 65535 )); }

while (( $# > 0 )); do
    case "$1" in
        --backend-port) BACKEND_PORT="${2:-}"; shift 2 ;;
        --web-port) WEB_PORT="${2:-}"; shift 2 ;;
        --timeout) READY_TIMEOUT="${2:-}"; shift 2 ;;
        --check) MODE="check"; shift ;;
        --smoke) MODE="smoke"; shift ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -t 1 ]]; then
    RED=$'\e[31m' GREEN=$'\e[32m' YELLOW=$'\e[33m' CYAN=$'\e[36m' MAGENTA=$'\e[35m' RESET=$'\e[0m'
else
    RED="" GREEN="" YELLOW="" CYAN="" MAGENTA="" RESET=""
fi
say() { printf '[dev] %s\n' "$*"; }
good() { printf '%s[dev] %s%s\n' "$GREEN" "$*" "$RESET"; }
caution() { printf '%s[dev] WARNING: %s%s\n' "$YELLOW" "$*" "$RESET"; }
problem() { printf '%s[dev] ERROR: %s%s\n' "$RED" "$*" "$RESET" >&2; }

BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
WEB_URL="http://127.0.0.1:$WEB_PORT"

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
PROBLEMS=()
PYTHON=""
NODE=""

port_is_free() {
    # Bind test with SO_REUSEADDR: a live listener blocks it, a TIME_WAIT
    # socket left by a server that just stopped does not.
    "$PYTHON" - "$1" <<'EOF'
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
EOF
}

port_owner() {
    local owner=""
    if command -v ss >/dev/null 2>&1; then
        owner="$(ss -H -ltnp "sport = :$1" 2>/dev/null | grep -o 'users:(([^)]*' | head -n 1 | sed 's/users:((//')"
    elif command -v lsof >/dev/null 2>&1; then
        owner="$(lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1 ", pid=" $2}')"
    fi
    printf '%s' "${owner:-another process}"
}

check_prerequisites() {
    is_port "$BACKEND_PORT" || PROBLEMS+=("--backend-port must be a number from 1024 to 65535 (got '$BACKEND_PORT').")
    is_port "$WEB_PORT" || PROBLEMS+=("--web-port must be a number from 1024 to 65535 (got '$WEB_PORT').")
    [[ "$READY_TIMEOUT" =~ ^[0-9]+$ ]] || PROBLEMS+=("--timeout must be a whole number of seconds.")
    [[ "$BACKEND_PORT" != "$WEB_PORT" ]] || PROBLEMS+=("--backend-port and --web-port must differ (both are $BACKEND_PORT).")

    local file
    for file in "$BACKEND_DIR/manage.py" "$WEB_DIR/package.json" "$WEB_DIR/vite.config.ts"; do
        [[ -f "$file" ]] || PROBLEMS+=("Missing $file. Run this script from a complete Finlume checkout.")
    done

    # Python: the repository's .venv first, then an activated virtual environment.
    if [[ -x "$ROOT/.venv/bin/python" ]]; then
        PYTHON="$ROOT/.venv/bin/python"
    elif [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
        PYTHON="$VIRTUAL_ENV/bin/python"
    fi
    if [[ -z "$PYTHON" ]]; then
        if [[ -d "$ROOT/.venv/Scripts" ]]; then
            PROBLEMS+=(".venv was created on Windows (it has Scripts/, not bin/). Create a Linux one: python3 -m venv .venv && .venv/bin/python -m pip install --require-hashes -r backend/requirements/dev.txt")
        else
            PROBLEMS+=("No Python virtual environment found at .venv. Create it: python3 -m venv .venv && .venv/bin/python -m pip install --require-hashes -r backend/requirements/dev.txt")
        fi
    else
        local django_version
        if django_version="$("$PYTHON" -c 'import django, rest_framework; print(django.get_version())' 2>/dev/null)"; then
            good "Python: $PYTHON (Django $django_version)"
        else
            PROBLEMS+=("Django is not installed in $PYTHON. Run: \"$PYTHON\" -m pip install --require-hashes -r backend/requirements/dev.txt")
            PYTHON_BROKEN=1
        fi
    fi

    # Node.js, matching apps/web/package.json engines (^22.13.0 || >=24.0.0).
    if ! NODE="$(command -v node)"; then
        PROBLEMS+=("Node.js was not found on PATH. Install Node.js 22 LTS (22.13 or newer) or 24 LTS.")
        NODE=""
    else
        local version major minor
        version="$("$NODE" --version)"; version="${version#v}"
        IFS=. read -r major minor _ <<<"$version"
        if (( major < 22 || (major == 22 && minor < 13) )); then
            PROBLEMS+=("Node.js $version is too old for apps/web; install 22.13+ or 24 LTS.")
        else
            (( major == 23 )) && caution "Node.js $version is not an LTS release; apps/web supports 22.13+ and 24+."
            good "Node.js: v$version"
        fi
    fi

    # Web dependencies must already be installed; this script never installs them.
    if [[ ! -f "$WEB_DIR/node_modules/vite/bin/vite.js" ]]; then
        PROBLEMS+=("Web dependencies are not installed. Run: (cd apps/web && npm ci)")
    elif [[ "$WEB_DIR/package-lock.json" -nt "$WEB_DIR/node_modules/.package-lock.json" ]]; then
        caution "apps/web/package-lock.json changed since the last install; run 'npm ci' in apps/web if the app fails to start."
    fi

    # Ports: report the owner instead of silently picking another port.
    if [[ -n "$PYTHON" && -z "${PYTHON_BROKEN:-}" ]] && is_port "$BACKEND_PORT" && is_port "$WEB_PORT"; then
        local entry name port flag
        for entry in "Backend:$BACKEND_PORT:--backend-port" "Web:$WEB_PORT:--web-port"; do
            IFS=: read -r name port flag <<<"$entry"
            if ! port_is_free "$port"; then
                PROBLEMS+=("Port $port ($name) is already in use by $(port_owner "$port"). Stop that process (it may be an earlier Finlume server), or choose another port with $flag <port>.")
            fi
        done
    fi

    if [[ -f "$ROOT/.env" ]]; then
        say "Configuration: .env found and used by Django (values not shown)."
    else
        say "Configuration: no .env found. Development expects PostgreSQL settings from .env (copy .env.example)."
    fi
    local settings="${DJANGO_SETTINGS_MODULE:-config.settings.development}"
    say "Django settings: $settings"
    [[ "$settings" == "config.settings.development" ]] ||
        caution "DJANGO_SETTINGS_MODULE is set to $settings; this launcher is meant for config.settings.development."

    [[ -n "$PYTHON" && -z "${PYTHON_BROKEN:-}" ]] && check_database
}

check_database() {
    # Read-only: shows the target, connects, and lists pending migrations.
    # It never migrates or writes (see backend/apps/core/management/commands/dbstatus.py).
    local output code line details command_error reason
    output="$(cd "$BACKEND_DIR" && "$PYTHON" manage.py dbstatus 2>&1)"
    code=$?
    details="$(grep -E '^(Database|Connection|Migrations):' <<<"$output")"
    command_error="$(grep -E '^CommandError: ' <<<"$output" | tail -n 1 | sed 's/^CommandError: //')"

    case "$code" in
        0)
            while IFS= read -r line; do good "$line"; done <<<"$details"
            ;;
        3)
            while IFS= read -r line; do good "$line"; done <<<"$details"
            caution "$command_error The launcher never migrates."
            ;;
        2)
            while IFS= read -r line; do [[ -n "$line" ]] && say "$line"; done <<<"$details"
            PROBLEMS+=("$command_error Start PostgreSQL (for the Docker option: 'docker compose up -d db' in the repository root), or correct POSTGRES_HOST / POSTGRES_PORT in .env. See docs/development/LOCAL_SETUP.md.")
            ;;
        *)
            reason="$(grep -o 'ImproperlyConfigured: .*' <<<"$output" | tail -n 1 | sed 's/^ImproperlyConfigured: //')"
            PROBLEMS+=("Database configuration: ${reason:-$(tail -n 1 <<<"$output")}")
            ;;
    esac
    if grep -q '^Database: SQLite' <<<"$details"; then
        caution "Using SQLite because FINLUME_DB_ENGINE=sqlite is set. Throwaway trials only: PostgreSQL is Finlume's database."
    fi
}

# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
STARTED=0
SERVICE_PID=""
BACKEND_PID=""
WEB_PID=""

prefix_output() {
    # Shows each line with a prefix and appends it to the log. It ignores
    # Ctrl+C so shutdown messages still appear, and ends when the service's
    # output closes.
    local prefix="$1" log="$2" line
    trap '' INT
    while IFS= read -r line || [[ -n "$line" ]]; do
        printf '%s\n' "$line" >>"$log"
        [[ -n "${line//[[:space:]]/}" ]] && printf '%s %s\n' "$prefix" "$line"
    done
}

start_service() {
    # start_service NAME PREFIX DIR ENV_ASSIGNMENT COMMAND...  -> sets SERVICE_PID
    # Must run in the main shell (not inside $(...)) so the service and its log
    # prefixer are children of this script and the prefixer's output is the terminal.
    local name="$1" prefix="$2" dir="$3" env_assignment="$4"
    shift 4
    local log="$LOG_DIR/$name.log" pidfile="$LOG_DIR/$name.pid"
    [[ -f "$log" ]] && mv -f "$log" "$LOG_DIR/$name.previous.log"
    : >"$log"
    rm -f "$pidfile"
    # The service gets its own session and process group (os.setsid) so that
    # shutdown can signal the whole group, including Django's autoreloader
    # child, without relying on job control or util-linux setsid.
    (
        cd "$dir" || exit 1
        exec env "$env_assignment" "$PYTHON" -c '
import os, sys
os.setsid()
with open(sys.argv[1], "w") as handle:
    handle.write(str(os.getpid()))
os.execvp(sys.argv[2], sys.argv[2:])
' "$pidfile" "$@"
    ) </dev/null 2>&1 | prefix_output "$prefix" "$log" &

    for _ in $(seq 1 50); do
        [[ -s "$pidfile" ]] && break
        sleep 0.1
    done
    if [[ ! -s "$pidfile" ]]; then
        problem "The $name process did not start. See $log."
        return 1
    fi
    SERVICE_PID="$(<"$pidfile")"
}

group_alive() { kill -0 -- "-$1" 2>/dev/null; }

stop_group() {
    local pid="$1"
    [[ -n "$pid" ]] || return 0
    group_alive "$pid" || return 0
    kill -TERM -- "-$pid" 2>/dev/null
    for _ in $(seq 1 50); do
        group_alive "$pid" || return 0
        sleep 0.2
    done
    caution "Process group $pid did not stop after 10 s; sending SIGKILL."
    kill -KILL -- "-$pid" 2>/dev/null
}

cleanup() {
    local status=$?
    (( STARTED )) || exit "$status"
    STARTED=0
    say "Stopping services..."
    stop_group "$BACKEND_PID"
    stop_group "$WEB_PID"
    wait 2>/dev/null  # let the log prefixers print the last lines
    local busy=() port
    for port in "$BACKEND_PORT" "$WEB_PORT"; do
        local free=0
        for _ in $(seq 1 20); do
            if port_is_free "$port"; then free=1; break; fi
            sleep 0.25
        done
        (( free )) || busy+=("port $port is still used by $(port_owner "$port")")
    done
    if (( ${#busy[@]} > 0 )); then
        caution "After shutdown, ${busy[*]}. Stop it manually."
        (( status == 0 )) && status=1
    else
        good "Stopped. Ports $BACKEND_PORT and $WEB_PORT are free. Logs kept in $LOG_DIR."
    fi
    exit "$status"
}

http_status() {
    if command -v curl >/dev/null 2>&1; then
        curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$1" 2>/dev/null || true
    else
        "$PYTHON" - "$1" <<'EOF' 2>/dev/null || echo 0
import sys, urllib.error, urllib.request
try:
    print(urllib.request.urlopen(sys.argv[1], timeout=3).status)
except urllib.error.HTTPError as error:
    print(error.code)
except Exception:
    print(0)
EOF
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
say "Finlume development launcher (repository: $ROOT)"
check_prerequisites
if (( ${#PROBLEMS[@]} > 0 )); then
    for message in "${PROBLEMS[@]}"; do problem "$message"; done
    problem "Nothing was started."
    exit 1
fi
if [[ "$MODE" == "check" ]]; then
    good "All checks passed. Backend would use $BACKEND_URL, web $WEB_URL."
    exit 0
fi

mkdir -p "$LOG_DIR"
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
STARTED=1

say "Starting backend: python manage.py runserver 127.0.0.1:$BACKEND_PORT"
start_service backend "${CYAN}[api]${RESET}" "$BACKEND_DIR" PYTHONUNBUFFERED=1 \
    "$PYTHON" manage.py runserver "127.0.0.1:$BACKEND_PORT" || exit 1
BACKEND_PID="$SERVICE_PID"
say "Starting web: vite --host 127.0.0.1 --port $WEB_PORT --strictPort"
start_service web "${MAGENTA}[web]${RESET}" "$WEB_DIR" "FINLUME_API_PROXY_TARGET=$BACKEND_URL" \
    "$NODE" node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEB_PORT" --strictPort || exit 1
WEB_PID="$SERVICE_PID"

deadline=$((SECONDS + READY_TIMEOUT))
backend_status=0
web_status=0
ready=0
while true; do
    for entry in "backend:$BACKEND_PID" "web:$WEB_PID"; do
        if ! kill -0 "${entry#*:}" 2>/dev/null; then
            problem "The ${entry%%:*} process exited unexpectedly. See the output above and $LOG_DIR/${entry%%:*}.log."
            exit 1
        fi
    done

    if (( ! ready )); then
        [[ "$backend_status" == 200 || "$backend_status" == 503 ]] || backend_status="$(http_status "$BACKEND_URL$HEALTH_PATH")"
        [[ "$web_status" == 200 ]] || web_status="$(http_status "$WEB_URL/")"
        if [[ ("$backend_status" == 200 || "$backend_status" == 503) && "$web_status" == 200 ]]; then
            ready=1
            proxy_status="$(http_status "$WEB_URL$HEALTH_PATH")"
            echo
            good "Finlume is running."
            good "  Web frontend:  $WEB_URL"
            good "  Backend API:   $BACKEND_URL/api/v1/   (health: $BACKEND_URL$HEALTH_PATH)"
            good "  Django admin:  $BACKEND_URL/admin/"
            [[ "$backend_status" == 503 ]] &&
                caution "The backend is up but cannot reach its database (health 503). Check PostgreSQL and the POSTGRES_* settings in .env."
            [[ "$proxy_status" == 200 || "$proxy_status" == 503 ]] ||
                caution "The web app's /api proxy did not reach the backend (HTTP $proxy_status). Check FINLUME_API_PROXY_TARGET in apps/web/.env.local."
            say "Logs: $LOG_DIR"
            say "Press Ctrl+C to stop both services."
            echo
            if [[ "$MODE" == "smoke" ]]; then
                say "Smoke test: services answered; shutting down."
                exit 0
            fi
        elif (( SECONDS >= deadline )); then
            problem "Timed out after $READY_TIMEOUT s waiting for the services (backend health: HTTP $backend_status, web: HTTP $web_status). See the output above and $LOG_DIR."
            exit 1
        fi
    fi
    sleep 1
done
