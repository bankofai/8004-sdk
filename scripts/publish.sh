#!/usr/bin/env bash
#
# 发布 trc-8004-sdk 到 PyPI
#
# 使用:
#   ./scripts/publish.sh        # 发布到 PyPI
#   ./scripts/publish.sh test   # 发布到 TestPyPI
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 清理旧构建
rm -rf dist/ build/ *.egg-info src/*.egg-info

# 构建
echo "Building package..."
uv build --wheel --out-dir dist

# 发布
if [ "${1:-}" = "test" ]; then
    echo "Publishing to TestPyPI..."
    uv run twine upload --repository testpypi dist/*
    echo ""
    echo "安装测试:"
    echo "  pip install --index-url https://test.pypi.org/simple/ trc-8004-sdk"
else
    echo "Publishing to PyPI..."
    uv run twine upload dist/*
    echo ""
    echo "安装:"
    echo "  pip install trc-8004-sdk"
fi

echo ""
echo "✅ 发布完成!"
