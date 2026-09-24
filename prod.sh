#!/bin/bash
# Stop on any error
set -e

echo "=== Starting Full Production Deploy to OrbStack ==="

# 1. Resolve OrbStack and Docker paths
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.orbstack/bin:$PATH"

# 2. Ensure we are in the correct directory (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- BEGIN deploy guard ---
# Deploy only what is on GitHub: main, clean, and identical to origin/main.
# The image is built from this working tree, so anything else would ship code
# that matches no pushed commit.
if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
    echo "Error: not on main (on $(git rev-parse --abbrev-ref HEAD)). Check out main first."
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "Error: the working tree has uncommitted changes. Commit or stash them first:"
    git status --short
    exit 1
fi
git fetch --quiet origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
    echo "Error: main differs from origin/main. Push or pull first:"
    echo "  unpushed: $(git rev-list --count origin/main..HEAD) commit(s), unpulled: $(git rev-list --count HEAD..origin/main) commit(s)"
    exit 1
fi
DEPLOY_SHA="$(git rev-parse --short HEAD)"
echo "Deploying commit $DEPLOY_SHA: $(git log -1 --format=%s)"
# --- END deploy guard ---

# 3. Pre-flight check: Verify Docker (OrbStack) is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker (OrbStack) is not running. Please start OrbStack first."
    exit 1
fi

# 4. Build and deploy production containers
echo "Building production images and starting containers..."
docker compose -f docker-compose.yml up -d --build

# 5. Find the active container ID
CONTAINER_ID=$(docker compose -f docker-compose.yml ps -q api)

if [ -z "$CONTAINER_ID" ]; then
    echo "Error: Failed to find paperstore-api container."
    exit 1
fi

# 6. Post-deployment health check
echo "Waiting for paperstore-api to start and become healthy..."
max_attempts=15
attempt=1
success=false

while [ $attempt -le $max_attempts ]; do
    # Check if the container is running and responding on port 8000 internally
    # We use python's built-in urllib to check health to avoid needing curl in python-slim
    if docker exec "$CONTAINER_ID" python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/tags')" >/dev/null 2>&1; then
        success=true
        break
    fi
    echo "Attempt $attempt/$max_attempts: API is not ready yet. Waiting 2 seconds..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ "$success" = true ]; then
    echo "=== Production deploy of $DEPLOY_SHA completed successfully! ==="
    echo "API is healthy and online."
else
    echo "Warning: API container started but failed the health check."
    echo "Checking last 20 lines of container logs:"
    docker logs --tail 20 "$CONTAINER_ID"
    exit 1
fi
