#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then echo "Setting up for the first time..."; python3 -m venv .venv || exit 1; fi
source .venv/bin/activate
pip install -r requirements.txt --quiet
( sleep 2; (xdg-open http://127.0.0.1:5000 || open http://127.0.0.1:5000) >/dev/null 2>&1 ) &
python run.py
