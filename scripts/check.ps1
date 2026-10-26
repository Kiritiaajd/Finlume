# Runs the same backend quality gates as CI. Usage (repository root, venv active):
#   .\scripts\check.ps1
#
# Success is judged by each tool's exit code. $ErrorActionPreference stays at
# its default because Windows PowerShell 5.1 turns any native stderr output
# (e.g. harmless warnings) into a terminating error under "Stop".
Push-Location (Join-Path $PSScriptRoot "..\backend")
try {
    $steps = [ordered]@{
        "Formatting"               = { python -m ruff format --check . }
        "Lint"                     = { python -m ruff check . }
        "Type check"               = { python -m mypy . }
        "Django checks"            = { python manage.py check --fail-level WARNING --settings=config.settings.test }
        "Migrations"               = { python manage.py makemigrations --check --dry-run --settings=config.settings.test }
        "Tests"                    = { python -m pytest --cov }
        "Runtime dependency audit" = { python -m pip_audit -r requirements/base.txt --progress-spinner off }
    }
    foreach ($name in $steps.Keys) {
        Write-Host "==> $name" -ForegroundColor Cyan
        & $steps[$name]
        if ($LASTEXITCODE -ne 0) {
            Write-Host "$name failed (exit code $LASTEXITCODE)." -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
    Write-Host "All checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
