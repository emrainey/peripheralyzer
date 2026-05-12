#!/usr/bin/env bash
# This script runs the pytest integration tests for the generate command.
# It compiles and runs generated C++ code as part of the test suite.
#
# Usage: ./test.sh
# Or from testing/ subdirectory: ../test.sh

set -e

# Determine script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "testing" ]; then
    # Running from testing/ subdirectory
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Running from project root
    PROJECT_ROOT="$SCRIPT_DIR"
fi

cd "$PROJECT_ROOT"

# Activate venv if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run the integration tests
# These tests will:
# 1. Generate C++ code from test YAML files
# 2. Format the code with clang-format (if available)
# 3. Compile it with g++ (if available)
# 4. Run the compiled executable (if available)
echo "Running pytest integration tests..."
python3 -m pytest tests/test_generate_integration.py -v "$@"

