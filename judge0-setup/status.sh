#!/bin/bash
# Check Judge0 status

cd "$(dirname "$0")"

JUDGE0_URL="http://localhost:2358"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Judge0 Status ==="
echo ""

# Check API
if curl -s --max-time 3 "${JUDGE0_URL}/about" > /dev/null 2>&1; then
    echo -e "API Status: ${GREEN}✓ Running${NC} at ${JUDGE0_URL}"

    # Get version info
    VERSION=$(curl -s --max-time 3 "${JUDGE0_URL}/about" | grep -o '"version":"[^"]*"' | head -1 || echo "unknown")
    echo "Version: $VERSION"
else
    echo -e "API Status: ${RED}✗ Not responding${NC}"
fi

echo ""
echo "=== Docker Containers ==="
docker compose ps 2>/dev/null || echo "Docker compose not available"

echo ""
echo "=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker compose ps -q 2>/dev/null) 2>/dev/null || echo "No containers running"
