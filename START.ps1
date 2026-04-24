# Tunisian Proverbs - Web Application Launcher

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Tunisian Proverbs - Web Application Launcher" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonExists = $null
try {
    $pythonExists = python --version 2>&1
    Write-Host "Python found: $pythonExists" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Check/Create venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install/Update requirements (always check to catch missing packages)
Write-Host "Checking and installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet 2>&1 | Where-Object { $_ -match "Successfully installed|Requirement already satisfied|ERROR" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency installation failed!" -ForegroundColor Red
    Write-Host "Run manually: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "Dependencies ready" -ForegroundColor Green

# Create required directories
Write-Host "Setting up directories..." -ForegroundColor Yellow
$dirs = @("data", "data/chromadb", "website/generated", "logs")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created: $dir" -ForegroundColor Green
    }
}

# Start server
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Starting FastAPI Server..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Visit: http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python run.py
