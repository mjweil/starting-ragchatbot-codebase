#!/bin/bash
set -e

echo "🔍 Checking code format with black..."
if ! uv run black --check backend/ main.py; then
    echo "❌ Code formatting issues found. Run 'npm run quality:fix' to fix them."
    exit 1
fi

echo "📦 Checking import sorting with isort..."
if ! uv run isort --check-only backend/ main.py; then
    echo "❌ Import sorting issues found. Run 'npm run quality:fix' to fix them."
    exit 1
fi

echo "🧹 Running linter with flake8..."
if ! uv run flake8 backend/ main.py; then
    echo "❌ Linting issues found. Please fix them manually."
    exit 1
fi

echo "✅ All quality checks passed!"