# PowerShell script för att köra applikationen
# Aktivera virtual environment och kör applikationen

# Aktivera virtual environment
& .\.venv\Scripts\Activate.ps1

# Lägg till Poppler till PATH om det finns (för nuvarande session)
$popplerPath = "C:\poppler\Library\bin"
if (Test-Path $popplerPath) {
    $env:PATH = "$popplerPath;$env:PATH"
    Write-Host "Poppler hittad och lagd till PATH" -ForegroundColor Green
} else {
    Write-Host "Varning: Poppler hittades inte på $popplerPath" -ForegroundColor Yellow
    Write-Host "Se INSTALL_POPPLER.md för installationsinstruktioner" -ForegroundColor Yellow
}

# Kör applikationen
python main.py
