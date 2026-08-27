$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$backend = Join-Path $repoRoot "backend"
$frontend = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$backendEnv = Join-Path $backend ".env"
$frontendEnv = Join-Path $frontend ".env"
$databasePath = Join-Path $backend "agentready_dev.db"

Push-Location $repoRoot
try {
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating backend virtual environment..."
        python -m venv (Join-Path $backend ".venv")
    }

    Write-Host "Installing backend dependencies..."
    & $venvPython -m pip install -e "${backend}[dev]"

    @"
DATABASE_URL=sqlite:///$($databasePath.Replace('\', '/'))
ENV=development
CORS_ORIGINS=http://localhost:5173
GEMINI_API_KEY=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
"@ | Set-Content -Path $backendEnv -Encoding ascii

    Write-Host "Seeding demo merchant and catalog..."
    & $venvPython (Join-Path $backend "scripts\seed_demo.py") --frontend-env $frontendEnv

    Push-Location $frontend
    try {
        Write-Host "Installing frontend dependencies..."
        npm install
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "AgentReady is bootstrapped. Run these commands in separate terminals:"
Write-Host "  cd `"$backend`"; & `"$venvPython`" -m uvicorn app.main:app --reload --port 8000"
Write-Host "  cd `"$frontend`"; npm run dev"