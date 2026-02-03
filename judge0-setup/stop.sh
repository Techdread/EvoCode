#!/bin/bash
# Stop Judge0 services gracefully

set -e
cd "$(dirname "$0")"

JUDGE0_URL="http://localhost:2358"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping Judge0 services...${NC}"

# Check if running
if ! docker compose ps --status running 2>/dev/null | grep -q "judge0"; then
    echo -e "${YELLOW}Judge0 services are not running.${NC}"
    # Clean up anyway
    docker compose down --remove-orphans 2>/dev/null || true
    exit 0
fi

# Stop containers gracefully
docker compose down --remove-orphans

# Verify stopped
sleep 2
if curl -s --max-time 2 "${JUDGE0_URL}/about" > /dev/null 2>&1; then
    echo -e "${RED}Warning: Judge0 may still be responding. Force stopping...${NC}"
    docker compose down --remove-orphans --timeout 10
fi

echo -e "${GREEN}✓ Judge0 services stopped.${NC}"
