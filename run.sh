#!/bin/bash
# Aktivera virtual environment och kör applikationen (för Git Bash)
# OBS: Detta script fungerar ENDAST i Git Bash, inte i PowerShell!

# Kontrollera om vi är i Git Bash
if [ -z "$BASH_VERSION" ]; then
    echo "Fel: Detta script kräver Git Bash eller bash."
    echo "I PowerShell, använd istället: .\run.ps1 eller .\run.bat"
    exit 1
fi

# Aktivera virtual environment
source .venv/Scripts/activate

# Lägg till Poppler till PATH om det finns
if [ -d "/c/poppler/Library/bin" ]; then
    export PATH="/c/poppler/Library/bin:$PATH"
    echo "Poppler hittad och lagd till PATH"
elif [ -d "C:/poppler/Library/bin" ]; then
    export PATH="C:/poppler/Library/bin:$PATH"
    echo "Poppler hittad och lagd till PATH"
else
    echo "Varning: Poppler hittades inte på C:\\poppler\\Library\\bin"
    echo "Se INSTALL_POPPLER.md för installationsinstruktioner"
fi

# Kör applikationen
python main.py
