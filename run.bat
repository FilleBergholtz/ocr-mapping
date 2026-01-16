@echo off
REM Aktivera virtual environment och kör applikationen
call .venv\Scripts\activate.bat

REM Lägg till Poppler till PATH om det finns
if exist "C:\poppler\Library\bin" (
    set "PATH=C:\poppler\Library\bin;%PATH%"
    echo Poppler hittad och lagd till PATH
) else (
    echo Varning: Poppler hittades inte på C:\poppler\Library\bin
    echo Se INSTALL_POPPLER.md för installationsinstruktioner
)

REM Kör applikationen
python main.py
