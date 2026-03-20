#!/bin/bash
set -euo pipefail

# GitHub Actions Runner entrypoint
# Registers the runner on start, removes on stop (graceful shutdown)

REPO_URL="${GITHUB_REPO_URL:?GITHUB_REPO_URL is required}"
RUNNER_TOKEN="${RUNNER_TOKEN:?RUNNER_TOKEN is required}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,linux,x64,waw-02}"
RUNNER_WORKDIR="${RUNNER_WORKDIR:-_work}"

# Fix permissions on work directory (Docker volume may be owned by root)
sudo chown -R runner:runner "${RUNNER_WORKDIR}" 2>/dev/null || true
sudo chown -R runner:runner /home/runner 2>/dev/null || true

# Deregister runner on exit
cleanup() {
    echo "Removing runner..."
    ./config.sh remove --token "${RUNNER_TOKEN}" 2>/dev/null || true
}
trap cleanup EXIT SIGTERM SIGINT

# Configure runner (--replace in case container restarted with same name)
./config.sh \
    --url "${REPO_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "${RUNNER_WORKDIR}" \
    --unattended \
    --replace \
    --disableupdate

echo "Runner '${RUNNER_NAME}' registered. Starting..."

# Run (foreground, so Docker can manage the process)
exec ./run.sh
