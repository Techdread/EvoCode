#!/bin/bash
# Start Judge0 services with health checking

set -e
cd "$(dirname "$0")"

JUDGE0_URL="http://localhost:2358"
MAX_WAIT=120  # Maximum seconds to wait for Judge0
CHECK_INTERVAL=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Judge0 services...${NC}"

# Copy config to /tmp to avoid path issues with colons in directory names
# Remove any stale config first (might be a directory from failed Docker run)
if [ -d /tmp/judge0.conf ]; then
    echo -e "${YELLOW}Cleaning up stale config directory (may need sudo)...${NC}"
    sudo rm -rf /tmp/judge0.conf 2>/dev/null || {
        echo -e "${RED}Cannot remove /tmp/judge0.conf directory. Run: sudo rm -rf /tmp/judge0.conf${NC}"
        exit 1
    }
fi
rm -f /tmp/judge0.conf 2>/dev/null || true
cp judge0.conf /tmp/judge0.conf

# Check if already running
if curl -s --max-time 2 "${JUDGE0_URL}/about" > /dev/null 2>&1; then
    echo -e "${GREEN}Judge0 is already running at ${JUDGE0_URL}${NC}"
    exit 0
fi

# Stop any existing containers first (clean state)
docker compose down --remove-orphans 2>/dev/null || true

# Start services
echo "Starting Docker containers..."
docker compose up -d

# Wait for Judge0 API to be ready
echo ""
echo "Waiting for Judge0 API to be ready (max ${MAX_WAIT}s)..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    if curl -s --max-time 3 "${JUDGE0_URL}/about" > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Judge0 is ready!${NC}"
        echo ""

        # Show container status
        docker compose ps

        echo ""
        echo -e "${GREEN}Judge0 available at: ${JUDGE0_URL}${NC}"
        echo ""
        echo "Quick test:"
        echo "  curl ${JUDGE0_URL}/about"
        echo ""
        echo "Run verification:"
        echo "  ./venv/bin/python verify_judge0.py"
        exit 0
    fi

    # Show progress
    printf "."
    sleep $CHECK_INTERVAL
    waited=$((waited + CHECK_INTERVAL))
done

# Timeout - check what's wrong
echo ""
echo -e "${RED}✗ Judge0 failed to start within ${MAX_WAIT} seconds${NC}"
echo ""
echo "Container status:"
docker compose ps
echo ""
echo "Recent logs:"
docker compose logs --tail=50
echo ""
echo "Try running: docker compose logs -f"
exit 1
