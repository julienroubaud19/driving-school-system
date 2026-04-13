#!/usr/bin/env bash
set -euo pipefail

UNIT_RESULT=0
API_RESULT=0

echo "========================================"
echo "  Running Unit Tests"
echo "========================================"
if python -m pytest unit_tests/ -v --tb=short; then
    UNIT_RESULT=0
    echo ""
    echo "[UNIT TESTS] PASSED"
else
    UNIT_RESULT=1
    echo ""
    echo "[UNIT TESTS] FAILED"
fi

echo ""
echo "========================================"
echo "  Running API Tests"
echo "========================================"
if python -m pytest API_tests/ -v --tb=short; then
    API_RESULT=0
    echo ""
    echo "[API TESTS] PASSED"
else
    API_RESULT=1
    echo ""
    echo "[API TESTS] FAILED"
fi

echo ""
echo "========================================"
echo "  Final Summary"
echo "========================================"
if [ $UNIT_RESULT -eq 0 ]; then
    echo "  Unit Tests:  PASSED"
else
    echo "  Unit Tests:  FAILED"
fi

if [ $API_RESULT -eq 0 ]; then
    echo "  API Tests:   PASSED"
else
    echo "  API Tests:   FAILED"
fi
echo "========================================"

if [ $UNIT_RESULT -ne 0 ] || [ $API_RESULT -ne 0 ]; then
    exit 1
fi

echo ""
echo "All tests passed."
exit 0
