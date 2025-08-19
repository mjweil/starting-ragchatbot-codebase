#!/bin/bash
set -e

echo "🔧 Formatting Python code with black..."
uv run black backend/ main.py

echo "📦 Sorting imports with isort..."
uv run isort backend/ main.py

echo "✅ Code formatting complete!"