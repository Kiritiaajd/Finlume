# Local setup

How to run the Finlume backend on your machine. The web and mobile clients have
their own setup: see [Frontend applications](FRONTEND.md).

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Git | any recent | |
| Python | **3.12 or 3.13** | See [Python versions](#python-versions). |
| PostgreSQL | 14 or newer | The development database. Run it with Docker Compose (§3a) or use your own server (§3b). |
| Docker (optional) | Docker Desktop or Engine with Compose v2 | Only for the Compose PostgreSQL option. |
| Node.js (frontends only) | `^22.13` or `>=24`, with npm 10+ | For `apps/web` and `apps/mobile`; not needed for the backend. |

## Python versions

- The backend declares `requires-python = ">=3.12"`, and CI tests on **3.12 and 3.13** ([ADR-0002](../decisions/ADR-0002-backend-stack.md#update-2026-10-27-python-floor-raised-to-312)).
- Python 3.10 and 3.11 are not supported. An existing `.venv` built on them must be recreated (step 1).
- If no suitable interpreter is installed, [uv](https://docs.astral.sh/uv/) can provide one without administrator rights: `uv python install 3.13`, then `uv venv .venv --python 3.13 --seed` from the repository root.

## 1. Create and activate the virtual environment

The virtual environment lives at the repository root in `.venv/`, which Git ignores.

```powershell
# Windows (PowerShell), from the repository root
python -m venv .venv            # skip if .venv already exists
.\.venv\Scripts\Activate.ps1
```

If PowerShell refuses with "running scripts is disabled on this system":

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Leave the environment with `deactivate`.

## 2. Install the locked dependencies

```powershell
cd backend
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements/dev.txt
```

`requirements/dev.txt` is a generated lock file that pins every package and its hash. Never edit it by hand. To change dependencies, see [Changing dependencies](#changing-dependencies).

## 3. Database: PostgreSQL (the development default)

Development settings use **PostgreSQL**. If the `POSTGRES_*` settings are missing, Django stops
at startup with a message listing every missing variable. It never falls back to SQLite on its
own.

### 3a. PostgreSQL via Docker Compose (documented option)

You need Docker Desktop or Docker Engine with Compose v2.

```powershell
# from the repository root
Copy-Item .env.example .env        # macOS/Linux: cp .env.example .env
# edit .env: set POSTGRES_PASSWORD to a local value of your choice; keep POSTGRES_PORT=55432
docker compose up -d db            # first start creates the finlume database and user
cd backend
python manage.py dbstatus          # read-only: target, connection and pending migrations
python manage.py migrate           # only against this Finlume database
python manage.py runserver
```

[`compose.yaml`](../../compose.yaml) runs PostgreSQL 17 on **`127.0.0.1:55432`** (loopback only)
and keeps its data in the `postgres-data` volume. It is for local development only.

- **Port 55432** avoids PostgreSQL servers that installers commonly place on 5432 and 5433. `POSTGRES_PORT` in `.env` sets both the container's host port and Django's connection. If you change it, make sure nothing else listens there (`Get-NetTCPConnection -State Listen -LocalPort 55432` in PowerShell, `ss -ltn 'sport = :55432'` on Linux). Otherwise Django would talk to that unrelated server.
- **Stopping:** `docker compose stop db`, or `docker compose down`, both keep the data. `docker compose down -v` **deletes** the database volume.

### 3b. Your own PostgreSQL server

Any PostgreSQL **14 or newer** works. Create a dedicated user and database for Finlume, then
put the server's host, port, database, user and password in `.env`. To run the tests on
PostgreSQL ([§5](#5-run-the-checks)), the user also needs the `CREATEDB` privilege. Never point
Finlume at a database that holds other data.

### 3c. SQLite (explicit opt-in, throwaway trials only)

```powershell
$env:FINLUME_DB_ENGINE = "sqlite"   # or FINLUME_DB_ENGINE=sqlite in .env
python manage.py migrate
python manage.py runserver
```

This uses `backend/var/local.sqlite3` (git-ignored). Django shows warning `finlume.W001` on
every start. SQLite does not preserve decimal precision the way PostgreSQL `numeric` does:
never use it for real financial data or for work that touches persistence.

### Checking the database

`python manage.py dbstatus` (in `backend/`) prints the database the settings point to (never
the password), confirms the server is reachable and supported, and lists pending migrations.
It is read-only. Exit codes: 0 means OK, 2 means unreachable, 3 means pending migrations.

When the server is running, open <http://127.0.0.1:8000/api/v1/health/>. The expected response is:

```json
{"status": "ok", "checks": {"database": "ok"}}
```

Base settings load the root `.env` automatically, and variables already set in your shell take precedence over it.

## 4. Admin user

```powershell
python manage.py createsuperuser
```

The Django admin is at <http://127.0.0.1:8000/admin/>. Change its path with `FINLUME_ADMIN_URL_PATH`.

## 5. Run the checks

```powershell
python -m pytest                 # tests
..\scripts\check.ps1             # every CI gate (macOS/Linux: ../scripts/check.sh)
```

Tests use `config.settings.test`. Their database is chosen by **`FINLUME_TEST_DB_ENGINE`**, independently of the development database:

- **`sqlite`** (default): an isolated in-memory database. It never touches your PostgreSQL server, even when `.env` selects PostgreSQL for development.
- **`postgresql`**: uses the `POSTGRES_*` server, creating and then **dropping** a database named `test_<POSTGRES_DB>`. Use it only against the Finlume development container or a server you own:

  ```powershell
  $env:FINLUME_TEST_DB_ENGINE = "postgresql"; python -m pytest; Remove-Item Env:FINLUME_TEST_DB_ENGINE
  ```

CI always runs the suite on PostgreSQL 17 and is the authoritative result. There,
`FINLUME_REQUIRE_POSTGRES_TESTS=1` makes pytest fail outright rather than run on SQLite.
Tests marked `@pytest.mark.postgres` are skipped on SQLite. See [QUALITY_GATES.md](QUALITY_GATES.md).

## 6. Start the backend and web app with one command

From the repository root:

```powershell
.\scripts\dev.ps1          # Windows (PowerShell 5.1 or 7)
```

```bash
./scripts/dev.sh           # Linux (bash). Also works as: bash scripts/dev.sh
```

| Service | URL |
|---|---|
| Web frontend (Vite) | <http://127.0.0.1:5173> |
| Backend API (Django) | <http://127.0.0.1:8000/api/v1/>, health at `/api/v1/health/` |
| Django admin | <http://127.0.0.1:8000/admin/> |

**One-time prerequisites.** The launcher checks these and stops with the exact fix if one is
missing. It never installs anything itself.

1. A Python virtual environment at `.venv` with the backend requirements (steps 1–2). An
   activated virtual environment (`VIRTUAL_ENV`) is used if `.venv` does not exist. A
   `.venv` created on Windows cannot be used on Linux, so create one per operating system.
2. A reachable database configured in `.env`: PostgreSQL by default ([§3](#3-database-postgresql-the-development-default)). For the Compose option, start it first with `docker compose up -d db`. The launcher never starts Docker or creates databases.
3. The database migrated: `python manage.py migrate` in `backend/`. The launcher never migrates; it warns when migrations are pending.
4. Node.js 22.13+ or 24 LTS on `PATH`, and the web dependencies installed with `npm ci` in `apps/web/`.
5. Ports 8000 and 5173 free.

**What it does.**
- Runs the prerequisite checks, including the read-only `manage.py dbstatus`:
  - it shows the database target, without the password;
  - it **refuses to start** if the database is unreachable or misconfigured, quoting the reason;
  - it **warns** about pending migrations;
  - it warns when the SQLite opt-in is active.
- Starts `python manage.py runserver 127.0.0.1:8000` in `backend/` and Vite on `127.0.0.1:5173` in `apps/web/`. Vite's `/api` proxy is pointed at that backend.
- Waits until the backend health check and the web app answer, then prints the URLs. If the health check returns 503, it warns that the database is unreachable.
- Shows both services' output live, prefixed `[api]` and `[web]`, and keeps it in `.dev/logs/` (git-ignored). The previous run's logs are kept as `*.previous.log`.
- Never shows the contents of `.env` or other secrets.

**Stopping.** Press **Ctrl+C** once. The launcher stops both services together with their
child processes (Django's autoreloader runs as a separate child process), waits until both
ports are free, and confirms. If one service crashes, the launcher stops the other one and
exits with an error.

**Options.**

| Windows | Linux | Effect |
|---|---|---|
| `-BackendPort 8001` | `--backend-port 8001` | Use another backend port; Vite's `/api` proxy follows it |
| `-WebPort 5174` | `--web-port 5174` | Use another web port |
| `-CheckOnly` | `--check` | Run the prerequisite, database and port checks only |
| `-Smoke` | `--smoke` | Start both, wait until they answer, stop them, and exit 0 on success |
| `-ReadyTimeoutSeconds 120` | `--timeout 120` | How long to wait for both services (default 60 s) |

The launcher never moves to another port on its own. If a port is taken, it names the
process holding it and stops.

**Troubleshooting.**

| Symptom | Fix |
|---|---|
| `running scripts is disabled on this system` (Windows) | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or run `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1` |
| `Permission denied` (Linux) | `chmod +x scripts/dev.sh`, or run `bash scripts/dev.sh` |
| `Port 8000 (Backend) is already in use by ...` | Stop the named process. It is often a server from an earlier run: Windows `taskkill /PID <pid> /T /F`, Linux `kill <pid>`. Or pass another port |
| `.venv was created on Windows` (Linux) | Create a Linux virtual environment as the message shows. The repository's `.venv` is per machine |
| `Web dependencies are not installed` | `cd apps/web` then `npm ci` |
| `Timed out ... waiting for the services` | Read the `[api]` / `[web]` lines above it, or `.dev/logs/`. Common causes are a syntax error in a settings change or a broken `node_modules` |
| `Database configuration: PostgreSQL is selected (the default) but POSTGRES_... are not set` | Create `.env` from `.env.example` and fill in the `POSTGRES_*` values ([§3](#3-database-postgresql-the-development-default)) |
| `Cannot use the database: ... port 55432 failed ...` | Start PostgreSQL (`docker compose up -d db` for the Compose option) or correct `POSTGRES_HOST` / `POSTGRES_PORT` |
| Warning: `pending migration(s)` | Review, then run `python manage.py migrate` in `backend/` yourself |
| Warning: health 503 | The database became unreachable after startup. Check that PostgreSQL is still running |
| Need `breakpoint()` / pdb in Django | The launcher gives services no interactive input. Run `python manage.py runserver` yourself in `backend/` for debugging sessions |

## Settings modules

| Module | Used by | Behaviour |
|--------|---------|-----------|
| `config.settings.development` | `manage.py` (default) | `DEBUG=True`; random per-process secret key if `DJANGO_SECRET_KEY` is unset; **PostgreSQL** from `POSTGRES_*` (fails clearly if unset; SQLite only with `FINLUME_DB_ENGINE=sqlite`, warning `finlume.W001`); browsable API enabled. |
| `config.settings.test` | pytest | Random secret; fast password hasher; throttling disabled; private storage at `backend/var/test-private`; database from `FINLUME_TEST_DB_ENGINE` (default SQLite in memory). |
| `config.settings.production` | ASGI/WSGI (default) | Refuses to start without a ≥50-character `DJANGO_SECRET_KEY` or a non-empty `DJANGO_ALLOWED_HOSTS`, or when the database is not PostgreSQL; secure cookies; HTTPS redirect. |

Select one explicitly with `DJANGO_SETTINGS_MODULE` or `--settings=...`.

## Environment variables

Every variable has a placeholder in [`.env.example`](../../.env.example). Never commit a real `.env`.

| Variable | Meaning | Default |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | Cryptographic signing key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. | dev/test: random per process; production: **required**, ≥ 50 chars |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names served. | dev: `localhost,127.0.0.1`; production: **required** |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated full origins (e.g. `https://finlume.example.org`). | empty |
| `FINLUME_DB_ENGINE` | Database for development and production: `postgresql` or `sqlite` (explicit opt-in, development only). | `postgresql`; production rejects `sqlite` |
| `FINLUME_TEST_DB_ENGINE` | Database for pytest, independent of `FINLUME_DB_ENGINE`. `postgresql` creates and drops `test_<POSTGRES_DB>`. | `sqlite` (in memory) |
| `FINLUME_REQUIRE_POSTGRES_TESTS` | When set (CI), pytest fails unless the tests use PostgreSQL. | unset |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database credentials; also read by `compose.yaml`. | required when the engine is `postgresql` |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Database address. `POSTGRES_PORT` is also the Compose container's host port. | `localhost`, `5432` (`.env.example` and `compose.yaml` use `55432`) |
| `POSTGRES_SSLMODE` | libpq `sslmode`. | `prefer` |
| `POSTGRES_CONN_MAX_AGE` | Persistent connection lifetime (seconds). | `60` |
| `FINLUME_PRIVATE_STORAGE_ROOT` | Absolute path for uploaded documents; must be outside web-served directories (enforced by check `finlume.E001`). | `backend/var/private` |
| `FINLUME_MAX_REQUEST_BYTES` | Maximum request body and non-file form data. It does **not** limit uploaded files; upload endpoints enforce their own limit. Also the size above which uploads spool to a temporary file. | `5242880` (5 MiB) |
| `FINLUME_LOG_LEVEL` | Root log level. | `INFO` |
| `FINLUME_ADMIN_URL_PATH` | URL prefix of the Django admin. | `admin/` |
| `FINLUME_THROTTLE_ANON`, `FINLUME_THROTTLE_USER` | DRF throttle rates. | `60/minute`, `1000/hour` |
| `FINLUME_SECURE_SSL_REDIRECT` | Production: redirect HTTP to HTTPS. | `true` |
| `FINLUME_TRUST_PROXY_SSL_HEADER` | Production: trust `X-Forwarded-Proto`. Enable **only** behind a TLS-terminating proxy. | `false` |
| `FINLUME_HSTS_SECONDS`, `FINLUME_HSTS_INCLUDE_SUBDOMAINS`, `FINLUME_HSTS_PRELOAD` | Production HSTS. Enable only after HTTPS works on every host; start small (e.g. `3600`). | `0`, `false`, `false` |

Booleans accept `1/0`, `true/false`, `yes/no`, `on/off`. Any other value stops startup with an error. The `.env` loader supports `KEY=VALUE`, `#` comments and quoted values; it does not support interpolation or multi-line values.

## Changing dependencies

Dependencies are declared in [`backend/pyproject.toml`](../../backend/pyproject.toml) and locked with uv (see [ADR-0004](../decisions/ADR-0004-dependency-management.md)):

```powershell
# in backend/, after editing pyproject.toml
python -m uv pip compile pyproject.toml --universal --python-version 3.12 --generate-hashes -o requirements/base.txt
python -m uv pip compile pyproject.toml --extra dev --universal --python-version 3.12 --generate-hashes -o requirements/dev.txt
python -m pip install --require-hashes -r requirements/dev.txt
```

To upgrade one package within its declared range, add `--upgrade-package <name>` to both compile commands. Commit `pyproject.toml` and both lock files together. CI fails if they disagree.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Couldn't import Django` | Activate `.venv` and install the requirements (step 2). |
| `PostgreSQL is selected (...) but POSTGRES_... not set` | Fill in the `POSTGRES_*` values in `.env` ([§3](#3-database-postgresql-the-development-default)). For a throwaway trial only, set `FINLUME_DB_ENGINE=sqlite`. |
| `connection ... failed` / health endpoint returns 503 | Database unreachable. Run `python manage.py dbstatus`, check `docker compose ps` and the `POSTGRES_*` values. |
| `bind: address already in use` from `docker compose up` | Another server holds `POSTGRES_PORT`. Choose a free port in `.env`. |
| `docker compose up` says `Set POSTGRES_PASSWORD in .env` | Create `.env` from `.env.example` and set the password. |
