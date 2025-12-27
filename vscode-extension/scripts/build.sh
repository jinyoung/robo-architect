#!/bin/bash

# Build script for Event Storming Navigator VS Code Extension

set -e

echo "🔨 Building Event Storming Navigator Extension..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

# Install extension dependencies
echo "📦 Installing extension dependencies..."
npm install

# Build extension TypeScript
echo "🔧 Building extension..."
npm run build:extension

# Build webview
echo "🎨 Building webview..."
cd webview
npm install
npm run build
cd ..

echo "✅ Build complete!"
echo ""
echo "To test the extension:"
echo "  1. Open this folder in VS Code"
echo "  2. Press F5 to launch Extension Development Host"
echo ""
echo "To package for distribution:"
echo "  npm run package"

