#!/bin/bash
echo "🔄 Wellco Adult - Manuel Pipeline Çalıştırma"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR/backend"
source venv/bin/activate

python main.py "$@"
