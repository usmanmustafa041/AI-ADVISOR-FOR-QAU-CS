$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()

function Check($name, $condition, $detail) {
  if ($condition) { Write-Host "PASS  $name" -ForegroundColor Green }
  else { Write-Host "BLOCK $name - $detail" -ForegroundColor Yellow; $script:failures.Add($name) }
}

docker info 2>$null | Out-Null
Check 'Docker Desktop' ($LASTEXITCODE -eq 0) 'start Docker Desktop'
if ($LASTEXITCODE -eq 0) {
  $health = docker compose -f "$root\docker-compose.yml" -f "$root\docker-compose.dev.yml" ps postgres --format '{{.Health}}' 2>$null
  Check 'PostgreSQL container' ($health -match 'healthy') 'run the development compose stack'
}

Push-Location "$root\frontend"
npx --yes playwright install --dry-run chromium 2>$null | Out-Null
Check 'Playwright Chromium runtime' ($LASTEXITCODE -eq 0) 'run npm run test:e2e:install'
Pop-Location

Push-Location "$root\backend"
python scripts/validate_review_queue.py evaluation/review_queue_200.csv
Check 'Independent review gate' ($LASTEXITCODE -eq 0) 'two reviewers and one adjudicator must annotate every approved row'
Pop-Location

$checklist = Import-Csv "$root\academic-data\source-registry\step1_checklist.csv"
$missing = @($checklist | Where-Object { $_.status -eq 'missing' -and $_.priority -eq 'critical' })
Check 'Official critical data gate' ($missing.Count -eq 0) 'obtain and verify department-approved data'

$envFile = Join-Path $root '.env'
$envText = if (Test-Path $envFile) { Get-Content $envFile -Raw } else { '' }
Check 'Production provider decision' ($envText -match 'LLM_PROVIDER=(?!unconfigured\s*$).+' -and $envText -match 'EMBEDDING_PROVIDER=') 'set approved providers in a private .env'

if ($failures.Count -gt 0) { Write-Host "`nReadiness blocked by $($failures.Count) gate(s)."; exit 1 }
Write-Host "`nAll local readiness gates passed." -ForegroundColor Green
