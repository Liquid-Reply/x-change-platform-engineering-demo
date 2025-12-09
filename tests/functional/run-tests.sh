#!/bin/bash
# Run Chainsaw functional tests
# Usage: ./run-tests.sh [test-number] [chainsaw-options]
#
# Examples:
#   ./run-tests.sh                    # Run all tests (verbose by default)
#   ./run-tests.sh 01                 # Run test 01 only
#   ./run-tests.sh --quiet            # Run all with minimal output
#   ./run-tests.sh 02 --fail-fast     # Run test 02, stop on first failure
#   ./run-tests.sh --report-format JSON --report-name results

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if chainsaw is installed
if ! command -v chainsaw &> /dev/null; then
    echo -e "${RED}Error: chainsaw is not installed${NC}"
    echo ""
    echo "Install with one of:"
    echo "  go install github.com/kyverno/chainsaw@latest"
    echo "  brew tap kyverno/chainsaw https://github.com/kyverno/chainsaw"
    echo "  kubectl krew install chainsaw"
    exit 1
fi

# Check if kubectl can connect
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster${NC}"
    echo "Ensure kubectl is configured and cluster is running"
    exit 1
fi

# Parse arguments
TEST_FILTER=""
EXTRA_ARGS=()

for arg in "$@"; do
    if [[ "$arg" =~ ^[0-9]+$ ]]; then
        # Numeric argument - filter to specific test
        TEST_FILTER=$(ls -d ${arg}* 2>/dev/null | head -1)
        if [ -z "$TEST_FILTER" ]; then
            echo -e "${RED}Error: No test matching '${arg}*' found${NC}"
            exit 1
        fi
    else
        EXTRA_ARGS+=("$arg")
    fi
done

echo -e "${GREEN}=== IDP Functional Tests ===${NC}"
echo ""
echo "Cluster: $(kubectl config current-context)"
echo "Tests:   ${TEST_FILTER:-all}"
echo ""

if [ -n "$TEST_FILTER" ]; then
    echo -e "${YELLOW}Running: $TEST_FILTER${NC}"
    chainsaw test "./$TEST_FILTER" "${EXTRA_ARGS[@]}"
else
    echo -e "${YELLOW}Running all tests...${NC}"
    chainsaw test . "${EXTRA_ARGS[@]}"
fi

echo ""
echo -e "${GREEN}Tests completed${NC}"
