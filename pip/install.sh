#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Installing RawView in editable mode from: $(pwd)"
pip install -e .
