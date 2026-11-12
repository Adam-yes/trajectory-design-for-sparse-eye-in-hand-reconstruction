@echo off
rem Windows: creates a virtual environment, installs the requirements, runs everything.
rem Pass --pdf to compile the paper as well (needs pdflatex on PATH).
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv || exit /b 1 )
call .venv\Scripts\activate.bat
python -m pip install --quiet -r requirements.txt || exit /b 1
python run_all.py %*
