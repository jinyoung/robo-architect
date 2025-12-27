#!/bin/bash

# Development script for Event Storming Navigator VS Code Extension

set -e

echo "🚀 Starting Event Storming Navigator Development Environment..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing extension dependencies..."
    npm install
fi

if [ ! -d "webview/node_modules" ]; then
    echo "📦 Installing webview dependencies..."
    cd webview && npm install && cd ..
fi

# Start Python backend server
echo "🐍 Starting Python backend server..."
cd server
if [ -f "requirements.txt" ]; then
    # Check if virtual environment exists
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi
fi

# Start backend in background
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Cleanup function
cleanup() {
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start concurrent dev servers
echo "🔄 Starting development servers..."
npm run dev

# Wait for processes
wait

