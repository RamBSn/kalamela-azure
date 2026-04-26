#!/bin/bash
# Kalamela Management System — start script
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
fi

echo "Starting Association Kalamela Management System..."
echo "Open http://localhost:5000 in your browser"
venv/bin/python run.py
