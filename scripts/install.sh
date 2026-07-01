#!/bin/bash
set -e

echo "FFAStrans Linux Mimo - Installation Script"
echo "==========================================="

PYTHON_MIN="3.10"
PYTHON_CMD=""

for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3.10+ not found. Please install Python first."
    exit 1
fi

echo "Using: $($PYTHON_CMD --version)"

$PYTHON_CMD -m pip install --user -r requirements.txt 2>/dev/null || \
    $PYTHON_CMD -m venv venv && source venv/bin/activate && pip install -r requirements.txt

echo ""
echo "Installation complete!"
echo ""
echo "To start FFAStrans Linux Mimo:"
echo "  python -m ffastrans.main"
echo ""
echo "Or with Docker:"
echo "  docker-compose up -d"
echo ""
echo "Web GUI: http://localhost:8080"
echo ""
