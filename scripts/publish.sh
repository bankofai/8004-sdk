#!/usr/bin/env bash
#
# Publish tron-8004-sdk to PyPI
#
# Usage:
#   ./scripts/publish.sh        # Publish to PyPI
#   ./scripts/publish.sh test   # Publish to TestPyPI
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Clean old builds
rm -rf dist/ build/ *.egg-info src/*.egg-info

# Build
echo "Building package..."
uv build --wheel --out-dir dist

# Publish
if [ "${1:-}" = "test" ]; then
    echo "Publishing to TestPyPI..."
    uv run twine upload --repository testpypi dist/*
    echo ""
    echo "Installation Test:"
    echo "  pip install --index-url https://test.pypi.org/simple/ tron-8004-sdk"
else
    echo "Publishing to PyPI..."
    uv run twine upload dist/*
    echo ""
    echo "Installation:"
    echo "  pip install tron-8004-sdk"
fi

echo ""
echo "✅ Publish Complete!"
