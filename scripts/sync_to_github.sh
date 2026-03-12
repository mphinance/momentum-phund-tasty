#!/bin/bash
# Venus Sync Script: Vultr -> Venus -> GitHub
# Scheduled for 4:30 AM (30 mins after Vultr export)

set -e

# Configuration
# Setup path based on where we actually are
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DATA_FILE="$REPO_DIR/docs/data.json"
LOG_FILE="/tmp/sync_log.log"

echo "------------------------------------------" >> "$LOG_FILE"
echo "Starting sync on $(date)" >> "$LOG_FILE"

cd "$REPO_DIR"

# Source virtual environment to ensure we have tastytrade and dotenv
source "$REPO_DIR/.venv/bin/activate"

# 1. Processing Steps
echo "Running full data pipeline..." >> "$LOG_FILE"

echo "Running analytics..." >> "$LOG_FILE"
python "$REPO_DIR/run_analytics.py" >> "$LOG_FILE" 2>&1

echo "Exporting data from tastytrade..." >> "$LOG_FILE"
python "$REPO_DIR/export_data.py" >> "$LOG_FILE" 2>&1

WATCHLIST_JSON="$REPO_DIR/docs/watchlist.json"

echo "Generating watchlist JSON..." >> "$LOG_FILE"
python "$REPO_DIR/scripts/generate_watchlist.py" "$WATCHLIST_JSON" >> "$LOG_FILE" 2>&1
if [ -f "$WATCHLIST_JSON" ]; then
    echo "Watchlist JSON generated successfully." >> "$LOG_FILE"
else
    echo "Failed to generate watchlist JSON." >> "$LOG_FILE"
fi

# 2. Git Sync to GitHub via Local Temp Repo (Bypassing SMB indexing issues)
echo "Pushing data to GitHub..." >> "$LOG_FILE"
TEMP_GIT_DIR="/tmp/sync_repo_automation"

# Setup temp repo
rm -rf "$TEMP_GIT_DIR"
GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" git clone --depth 1 git@github.com:mphinance/momentum-phund-tasty.git "$TEMP_GIT_DIR" >> "$LOG_FILE" 2>&1

# Copy updated files
cp "$DATA_FILE" "$TEMP_GIT_DIR/docs/"
if [ -f "$WATCHLIST_JSON" ]; then
    cp "$WATCHLIST_JSON" "$TEMP_GIT_DIR/docs/"
fi

# Commit and Push
cd "$TEMP_GIT_DIR"
git add -f docs/data.json docs/watchlist.json
if git diff --cached --quiet; then
    echo "No changes in data.json, skipping push." >> "$LOG_FILE"
else
    git commit -m "Automated daily export via local sync" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    echo "Sync successful!" >> "$LOG_FILE"
fi

# Cleanup
rm -rf "$TEMP_GIT_DIR"
cd "$REPO_DIR"

echo "Finished sync on $(date)" >> "$LOG_FILE"
