#!/bin/bash
# Venus Sync Script: Vultr -> Venus -> GitHub
# Scheduled for 7:30 AM (30 mins after Vultr export)

set -e

# Configuration
REPO_DIR="/home/sam/Antigravity/momentum-phund-tasty"
DATA_FILE="$REPO_DIR/docs/data.json"
LOG_FILE="$REPO_DIR/scripts/sync_log.log"

echo "------------------------------------------" >> "$LOG_FILE"
echo "Starting sync on $(date)" >> "$LOG_FILE"

cd "$REPO_DIR"

# 1. Processing Steps
echo "Running intermediate processing steps (Watchlist Generation)..." >> "$LOG_FILE"

WATCHLIST_JSON="$REPO_DIR/docs/watchlist.json"

echo "Generating watchlist JSON..." >> "$LOG_FILE"
"$REPO_DIR/.venv/bin/python" "$REPO_DIR/scripts/generate_watchlist.py" "$WATCHLIST_JSON" >> "$LOG_FILE" 2>&1

if [ -f "$WATCHLIST_JSON" ]; then
    echo "Watchlist JSON generated successfully." >> "$LOG_FILE"
else
    echo "Failed to generate watchlist JSON." >> "$LOG_FILE"
fi

# 2. Git Sync to GitHub
echo "Pushing data to GitHub..." >> "$LOG_FILE"
git add "$DATA_FILE"
if [ -f "$WATCHLIST_JSON" ]; then
    git add "$WATCHLIST_JSON"
fi

# Only commit if there are changes
if git diff --cached --quiet; then
    echo "No changes in data.json, skipping commit." >> "$LOG_FILE"
else
    git commit -m "Automated daily export via Venus sync"
    git push origin main >> "$LOG_FILE" 2>&1
    echo "Sync successful!" >> "$LOG_FILE"
fi

echo "Finished sync on $(date)" >> "$LOG_FILE"
