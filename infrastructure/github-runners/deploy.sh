#!/bin/bash
set -euo pipefail

# Deploy GitHub Actions runner for ProxyCraft to WAW-02
#
# Usage:
#   ./deploy.sh                    # Build & start
#   ./deploy.sh rebuild            # Force rebuild image
#   ./deploy.sh stop               # Stop runner
#   ./deploy.sh logs               # Follow logs
#   ./deploy.sh status             # Check runner status
#   ./deploy.sh new-token          # Generate new registration token

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

REPO="spyrae/proxycraft"

new_token() {
    if ! command -v gh &>/dev/null; then
        echo "Error: gh CLI is required. Install: https://cli.github.com/"
        exit 1
    fi

    TOKEN=$(gh api -X POST "repos/${REPO}/actions/runners/registration-token" --jq .token)
    echo "RUNNER_TOKEN=${TOKEN}" > .env
    echo "GITHUB_REPO_URL=https://github.com/${REPO}" >> .env
    echo "Token saved to .env (valid for 1 hour)"
}

case "${1:-start}" in
    start)
        if [ ! -f .env ]; then
            echo "No .env file found. Generating token..."
            new_token
        fi
        docker compose up -d --build
        echo ""
        echo "Runner started. Check status:"
        echo "  docker compose ps"
        echo "  docker compose logs -f"
        ;;
    rebuild)
        if [ ! -f .env ]; then
            new_token
        fi
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        ;;
    stop)
        docker compose down
        echo "Runner stopped."
        ;;
    logs)
        docker compose logs -f
        ;;
    status)
        docker compose ps
        echo ""
        echo "GitHub runner status:"
        gh api "repos/${REPO}/actions/runners" --jq '.runners[] | "\(.name): \(.status) (\(.labels | map(.name) | join(", ")))"' 2>/dev/null || echo "(need gh auth)"
        ;;
    new-token)
        new_token
        ;;
    *)
        echo "Usage: $0 {start|rebuild|stop|logs|status|new-token}"
        exit 1
        ;;
esac
