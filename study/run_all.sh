#!/usr/bin/env bash
# Linux/macOS: creates a virtual environment, installs the requirements, runs everything.
# Pass --pdf to compile the paper as well (needs pdflatex on PATH).
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --quiet -r requirements.txt
python run_all.py "$@"
